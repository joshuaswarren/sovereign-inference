# SPDX-License-Identifier: Apache-2.0
"""Tests for the Akash external-compute provider adapter."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
import yaml

from sip_compute import (
    ComputeError,
    Deployment,
    DeploymentStatus,
    InferenceSpec,
    get_provider_factory,
)
from sip_provider_akash import AkashProvider, build_sdl

SERVICE = "sip-gateway"


def _spec(**overrides: object) -> InferenceSpec:
    base: dict[str, object] = {
        "model": "qwen-coder-7b",
        "image": "ghcr.io/sovereign-inference/sip-gateway:latest",
        "port": 8080,
    }
    base.update(overrides)
    return InferenceSpec(**base)  # type: ignore[arg-type]


class _RouterCli:
    """Fake CLI that routes by a substring of the joined argv to canned JSON."""

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[list[str]] = []

    def __call__(self, argv: Sequence[str]) -> str:
        self.calls.append(list(argv))
        joined = " ".join(argv)
        for key, resp in self.responses.items():
            if key in joined:
                return resp
        return "{}"

    def saw(self, fragment: str) -> bool:
        return any(fragment in " ".join(call) for call in self.calls)


_CREATE_OK = json.dumps(
    {"txhash": "ABC", "code": 0, "logs": [{"events": [{"attributes": [{"key": "dseq", "value": "777"}]}]}]}
)
_BIDS_OK = json.dumps(
    {
        "bids": [
            {"bid": {"bid_id": {"provider": "akash1expensive"}, "price": {"amount": "50", "denom": "uakt"}}},
            {"bid": {"bid_id": {"provider": "akash1cheap"}, "price": {"amount": "5", "denom": "uakt"}}},
        ]
    }
)
_LEASE_OK = json.dumps({"txhash": "LEASE", "code": 0})
_MANIFEST_OK = "ok"


def _provider(responses: dict[str, str], **kwargs: object) -> tuple[AkashProvider, _RouterCli]:
    cli = _RouterCli(responses)
    provider = AkashProvider(wallet="mykey", owner="akash1owner", run=cli, **kwargs)  # type: ignore[arg-type]
    return provider, cli


# -- build_sdl ------------------------------------------------------------------


def test_build_sdl_is_v2_with_exposed_service() -> None:
    sdl = build_sdl(_spec(env={"SIP_TOKEN": "t"}))
    assert sdl["version"] == "2.0"
    svc = sdl["services"][SERVICE]
    assert svc["image"] == "ghcr.io/sovereign-inference/sip-gateway:latest"
    expose = svc["expose"][0]
    assert expose["port"] == 8080
    assert expose["to"] == [{"global": True}]
    assert svc["env"] == ["SIP_TOKEN=t"]


def test_build_sdl_requests_gpu_by_default() -> None:
    sdl = build_sdl(_spec())
    gpu = sdl["profiles"]["compute"][SERVICE]["resources"]["gpu"]
    assert gpu["units"] == 1


def test_build_sdl_omits_gpu_when_disabled() -> None:
    sdl = build_sdl(_spec(gpu=False))
    assert "gpu" not in sdl["profiles"]["compute"][SERVICE]["resources"]


def test_build_sdl_pins_gpu_model_when_given() -> None:
    sdl = build_sdl(_spec(gpu_model="rtx4090"))
    gpu = sdl["profiles"]["compute"][SERVICE]["resources"]["gpu"]
    vendor = gpu["attributes"]["vendor"]["nvidia"]
    assert {"model": "rtx4090"} in vendor


def test_build_sdl_wires_deployment_to_profile() -> None:
    sdl = build_sdl(_spec())
    placement = next(iter(sdl["deployment"][SERVICE]))
    assert sdl["deployment"][SERVICE][placement]["profile"] == SERVICE
    assert sdl["deployment"][SERVICE][placement]["count"] == 1
    assert placement in sdl["profiles"]["placement"]


def test_build_sdl_is_yaml_serializable() -> None:
    sdl = build_sdl(_spec(env={"A": "B"}))
    assert yaml.safe_load(yaml.safe_dump(sdl)) == sdl


# -- registry -------------------------------------------------------------------


def test_akash_registers_itself() -> None:
    factory = get_provider_factory("akash")
    provider = factory(wallet="w", owner="o", run=_RouterCli({}))
    assert provider.name == "akash"


# -- deploy ---------------------------------------------------------------------


def test_deploy_runs_full_lifecycle_and_picks_cheapest_bid() -> None:
    provider, cli = _provider(
        {
            "deployment create": _CREATE_OK,
            "bid list": _BIDS_OK,
            "lease create": _LEASE_OK,
            "send-manifest": _MANIFEST_OK,
        }
    )
    deployment = provider.deploy(_spec())
    assert deployment.provider == "akash"
    assert deployment.id == "777"
    assert deployment.status == DeploymentStatus.DEPLOYING
    assert deployment.raw["dseq"] == "777"
    assert deployment.raw["provider"] == "akash1cheap"  # cheapest bid won
    assert deployment.raw["owner"] == "akash1owner"
    # the lease + manifest steps targeted the winning provider
    assert cli.saw("lease create")
    assert cli.saw("send-manifest")
    assert cli.saw("akash1cheap")


def test_deploy_raises_when_no_dseq() -> None:
    provider, _ = _provider({"deployment create": json.dumps({"txhash": "X", "code": 0, "logs": []})})
    with pytest.raises(ComputeError):
        provider.deploy(_spec())


def test_deploy_raises_when_no_bids() -> None:
    provider, _ = _provider({"deployment create": _CREATE_OK, "bid list": json.dumps({"bids": []})})
    with pytest.raises(ComputeError):
        provider.deploy(_spec())


def test_deploy_stamps_spec_pricing_onto_deployment() -> None:
    provider, _ = _provider(
        {
            "deployment create": _CREATE_OK,
            "bid list": _BIDS_OK,
            "lease create": _LEASE_OK,
            "send-manifest": _MANIFEST_OK,
        }
    )
    deployment = provider.deploy(_spec(input_per_1m=0.3, output_per_1m=0.9, pricing_unit="usdc"))
    assert deployment.pricing_unit == "usdc"
    assert deployment.input_per_1m == 0.3
    assert deployment.output_per_1m == 0.9


def test_deploy_rejects_failed_deployment_create_tx() -> None:
    # A Cosmos-SDK tx exits 0 but carries a non-zero `code` on on-chain failure.
    failed = json.dumps({"txhash": "X", "code": 11, "raw_log": "insufficient funds", "logs": []})
    provider, _ = _provider({"deployment create": failed})
    with pytest.raises(ComputeError):
        provider.deploy(_spec())


def test_deploy_rejects_failed_lease_create_tx() -> None:
    failed_lease = json.dumps({"txhash": "L", "code": 5, "raw_log": "lease already exists"})
    provider, _ = _provider(
        {
            "deployment create": _CREATE_OK,
            "bid list": _BIDS_OK,
            "lease create": failed_lease,
            "send-manifest": _MANIFEST_OK,
        }
    )
    with pytest.raises(ComputeError):
        provider.deploy(_spec())


def test_deploy_cleans_up_temp_sdl_file_even_when_create_fails() -> None:
    seen: dict[str, object] = {}

    def run(argv: Sequence[str]) -> str:
        # The first call is `tx deployment create <sdl_path> ...`.
        sdl_path = argv[4]
        seen["path"] = sdl_path
        seen["existed_during_run"] = Path(sdl_path).exists()
        raise subprocess.CalledProcessError(1, list(argv))

    provider = AkashProvider(wallet="w", owner="o", run=run)
    with pytest.raises(subprocess.CalledProcessError):
        provider.deploy(_spec())
    assert seen["existed_during_run"] is True
    assert not Path(str(seen["path"])).exists()


# -- status ---------------------------------------------------------------------


def _running_deployment() -> Deployment:
    return Deployment(
        provider="akash",
        id="777",
        model="qwen-coder-7b",
        status=DeploymentStatus.DEPLOYING,
        raw={"owner": "akash1owner", "dseq": "777", "provider": "akash1cheap", "gseq": 1, "oseq": 1},
    )


def test_status_running_when_lease_has_uri() -> None:
    lease = json.dumps({"services": {SERVICE: {"uris": ["abc123.ingress.akash.example"], "available": 1, "total": 1}}})
    provider, cli = _provider({"lease-status": lease})
    refreshed = provider.status(_running_deployment())
    assert refreshed.status == DeploymentStatus.RUNNING
    assert refreshed.endpoint == "https://abc123.ingress.akash.example"
    assert refreshed.is_ready
    assert cli.saw("lease-status")


def test_status_deploying_when_not_yet_available() -> None:
    lease = json.dumps({"services": {SERVICE: {"uris": [], "available": 0, "total": 1}}})
    provider, _ = _provider({"lease-status": lease})
    refreshed = provider.status(_running_deployment())
    assert refreshed.status == DeploymentStatus.DEPLOYING
    assert refreshed.endpoint is None


def test_status_requires_lease_coordinates() -> None:
    provider, _ = _provider({"lease-status": "{}"})
    bare = Deployment(provider="akash", id="777", model="m", status=DeploymentStatus.DEPLOYING)
    with pytest.raises(ComputeError):
        provider.status(bare)


def test_status_not_ready_when_available_zero_despite_uri() -> None:
    # A URI can appear before the workload is actually available; the readiness
    # gate must require BOTH a URI and available>=1.
    lease = json.dumps({"services": {SERVICE: {"uris": ["host.akash.example"], "available": 0, "total": 1}}})
    provider, _ = _provider({"lease-status": lease})
    refreshed = provider.status(_running_deployment())
    assert refreshed.status == DeploymentStatus.DEPLOYING
    assert not refreshed.is_ready


def test_status_tolerates_malformed_available_value() -> None:
    lease = json.dumps({"services": {SERVICE: {"uris": ["host.akash.example"], "available": "oops"}}})
    provider, _ = _provider({"lease-status": lease})
    refreshed = provider.status(_running_deployment())  # must not raise
    assert refreshed.status == DeploymentStatus.DEPLOYING


# -- await_ready ----------------------------------------------------------------


def test_await_ready_polls_until_uri_appears() -> None:
    not_ready = json.dumps({"services": {SERVICE: {"uris": [], "available": 0, "total": 1}}})
    ready = json.dumps({"services": {SERVICE: {"uris": ["host.akash.example"], "available": 1, "total": 1}}})
    cli = _RouterCli({})
    # lease-status returns not-ready twice, then ready
    responses = [not_ready, not_ready, ready]

    def run(argv: Sequence[str]) -> str:
        cli.calls.append(list(argv))
        return responses.pop(0) if responses else ready

    provider = AkashProvider(wallet="w", owner="o", run=run, sleep=lambda _s: None)
    result = provider.await_ready(_running_deployment())
    assert result.is_ready
    assert result.endpoint == "https://host.akash.example"


def test_await_ready_gives_up_after_max_polls() -> None:
    not_ready = json.dumps({"services": {SERVICE: {"uris": [], "available": 0, "total": 1}}})
    provider, _ = _provider({"lease-status": not_ready}, sleep=lambda _s: None, max_polls=3)
    result = provider.await_ready(_running_deployment())
    assert not result.is_ready


# -- teardown -------------------------------------------------------------------


def test_teardown_closes_deployment() -> None:
    provider, cli = _provider({"deployment close": _LEASE_OK})
    provider.teardown(_running_deployment())
    assert cli.saw("deployment close")
    assert cli.saw("777")


def test_teardown_wraps_cli_errors_in_compute_error() -> None:
    def run(argv: Sequence[str]) -> str:
        raise subprocess.CalledProcessError(1, list(argv))

    provider = AkashProvider(wallet="w", owner="o", run=run)
    with pytest.raises(ComputeError):
        provider.teardown(_running_deployment())
