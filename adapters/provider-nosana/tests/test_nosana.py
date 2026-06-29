# SPDX-License-Identifier: Apache-2.0
"""Tests for the Nosana external-compute provider adapter."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from sip_compute import (
    ComputeError,
    Deployment,
    DeploymentStatus,
    InferenceSpec,
    get_provider_factory,
)
from sip_provider_nosana import NosanaProvider, build_job_definition


def _spec(**overrides: object) -> InferenceSpec:
    base: dict[str, object] = {
        "model": "qwen-coder-7b",
        "image": "ghcr.io/sovereign-inference/sip-gateway:latest",
        "port": 8080,
    }
    base.update(overrides)
    return InferenceSpec(**base)  # type: ignore[arg-type]


class _FakeCli:
    """Records argv and returns canned stdout for each successive call."""

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self.calls: list[list[str]] = []

    def __call__(self, argv: Sequence[str]) -> str:
        self.calls.append(list(argv))
        if not self._responses:
            return "{}"
        return self._responses.pop(0)


# -- build_job_definition -------------------------------------------------------


def test_build_job_definition_shapes_a_container_run_op() -> None:
    job = build_job_definition(_spec(env={"SIP_TOKEN": "abc"}, command=["serve"]))
    assert job["type"] == "container"
    assert isinstance(job["ops"], list) and len(job["ops"]) == 1
    op = job["ops"][0]
    assert op["type"] == "container/run"
    args = op["args"]
    assert args["image"] == "ghcr.io/sovereign-inference/sip-gateway:latest"
    assert args["gpu"] is True
    assert args["expose"] == 8080
    assert args["cmd"] == ["serve"]
    assert args["env"] == {"SIP_TOKEN": "abc"}


def test_build_job_definition_omits_optional_fields() -> None:
    job = build_job_definition(_spec())
    args = job["ops"][0]["args"]
    assert "cmd" not in args
    assert "env" not in args


def test_build_job_definition_is_json_serializable() -> None:
    job = build_job_definition(_spec(env={"K": "V"}))
    assert json.loads(json.dumps(job)) == job


# -- registry -------------------------------------------------------------------


def test_nosana_registers_itself() -> None:
    factory = get_provider_factory("nosana")
    provider = factory(market="nvidia-3090", run=_FakeCli([]))
    assert provider.name == "nosana"


# -- deploy ---------------------------------------------------------------------


def test_deploy_posts_job_and_returns_handle() -> None:
    cli = _FakeCli([json.dumps({"job": "JOBADDR1", "state": "QUEUED"})])
    provider = NosanaProvider(market="nvidia-3090", run=cli)
    deployment = provider.deploy(_spec())
    assert deployment.provider == "nosana"
    assert deployment.id == "JOBADDR1"
    assert deployment.model == "qwen-coder-7b"
    assert deployment.status == DeploymentStatus.PENDING
    # the post command targeted the configured market
    post = cli.calls[0]
    assert post[:3] == ["nosana", "job", "post"]
    assert "--market" in post and "nvidia-3090" in post


def test_deploy_raises_when_cli_returns_no_job_id() -> None:
    cli = _FakeCli([json.dumps({"state": "QUEUED"})])
    provider = NosanaProvider(market="m", run=cli)
    with pytest.raises(ComputeError):
        provider.deploy(_spec())


def test_deploy_raises_on_unparseable_output() -> None:
    cli = _FakeCli(["not json at all"])
    provider = NosanaProvider(market="m", run=cli)
    with pytest.raises(ComputeError):
        provider.deploy(_spec())


def test_deploy_stamps_spec_pricing_onto_deployment() -> None:
    cli = _FakeCli([json.dumps({"job": "J", "state": "QUEUED"})])
    provider = NosanaProvider(market="m", run=cli)
    deployment = provider.deploy(_spec(input_per_1m=0.2, output_per_1m=0.6, pricing_unit="usdc"))
    assert deployment.pricing_unit == "usdc"
    assert deployment.input_per_1m == 0.2
    assert deployment.output_per_1m == 0.6


def test_deploy_cleans_up_temp_job_file_even_when_post_fails() -> None:
    seen: dict[str, object] = {}

    def run(argv: Sequence[str]) -> str:
        path = argv[list(argv).index("--file") + 1]
        seen["path"] = path
        seen["existed_during_run"] = Path(path).exists()
        raise subprocess.CalledProcessError(1, list(argv))

    provider = NosanaProvider(market="m", run=run)
    with pytest.raises(subprocess.CalledProcessError):
        provider.deploy(_spec())
    assert seen["existed_during_run"] is True  # the job file was written before the call
    assert not Path(str(seen["path"])).exists()  # ...and cleaned up afterwards


# -- status ---------------------------------------------------------------------


def test_status_maps_running_state_and_endpoint() -> None:
    cli = _FakeCli([json.dumps({"job": "J", "state": "RUNNING", "serviceUrl": "https://j.node.nos.ci"})])
    provider = NosanaProvider(market="m", run=cli)
    base = Deployment(provider="nosana", id="J", model="m", status=DeploymentStatus.PENDING)
    refreshed = provider.status(base)
    assert refreshed.status == DeploymentStatus.RUNNING
    assert refreshed.endpoint == "https://j.node.nos.ci"
    assert refreshed.is_ready
    assert cli.calls[0][:3] == ["nosana", "job", "get"]


def test_status_maps_terminal_states() -> None:
    for state, expected in [
        ("COMPLETED", DeploymentStatus.CLOSED),
        ("STOPPED", DeploymentStatus.CLOSED),
        ("FAILED", DeploymentStatus.FAILED),
    ]:
        cli = _FakeCli([json.dumps({"job": "J", "state": state})])
        provider = NosanaProvider(market="m", run=cli)
        base = Deployment(provider="nosana", id="J", model="m", status=DeploymentStatus.RUNNING)
        assert provider.status(base).status == expected


def test_status_preserves_endpoint_when_absent_in_refresh() -> None:
    cli = _FakeCli([json.dumps({"job": "J", "state": "RUNNING"})])
    provider = NosanaProvider(market="m", run=cli)
    base = Deployment(
        provider="nosana",
        id="J",
        model="m",
        status=DeploymentStatus.PENDING,
        endpoint="https://known.example",
    )
    assert provider.status(base).endpoint == "https://known.example"


# -- await_ready ----------------------------------------------------------------


def test_await_ready_polls_until_running() -> None:
    cli = _FakeCli(
        [
            json.dumps({"job": "J", "state": "QUEUED"}),
            json.dumps({"job": "J", "state": "QUEUED"}),
            json.dumps({"job": "J", "state": "RUNNING", "serviceUrl": "https://j.example"}),
        ]
    )
    slept: list[float] = []
    provider = NosanaProvider(market="m", run=cli, sleep=slept.append, poll_interval=2.0)
    base = Deployment(provider="nosana", id="J", model="m", status=DeploymentStatus.PENDING)
    ready = provider.await_ready(base)
    assert ready.is_ready
    assert ready.endpoint == "https://j.example"
    assert slept == [2.0, 2.0]  # slept before each re-poll, not after success


def test_await_ready_stops_on_terminal_state() -> None:
    cli = _FakeCli([json.dumps({"job": "J", "state": "FAILED"})])
    provider = NosanaProvider(market="m", run=cli, sleep=lambda _s: None)
    base = Deployment(provider="nosana", id="J", model="m", status=DeploymentStatus.PENDING)
    result = provider.await_ready(base)
    assert result.status == DeploymentStatus.FAILED
    assert not result.is_ready


def test_await_ready_gives_up_after_max_polls() -> None:
    cli = _FakeCli([json.dumps({"job": "J", "state": "QUEUED"})] * 50)
    provider = NosanaProvider(market="m", run=cli, sleep=lambda _s: None, max_polls=3)
    base = Deployment(provider="nosana", id="J", model="m", status=DeploymentStatus.PENDING)
    result = provider.await_ready(base)
    assert not result.is_ready
    # one initial status + max_polls re-polls
    assert len([c for c in cli.calls if c[:3] == ["nosana", "job", "get"]]) == 4


# -- teardown -------------------------------------------------------------------


def test_teardown_stops_the_job() -> None:
    cli = _FakeCli(["stopped"])
    provider = NosanaProvider(market="m", run=cli)
    provider.teardown(Deployment(provider="nosana", id="JX", model="m", status=DeploymentStatus.RUNNING))
    assert cli.calls[-1][:3] == ["nosana", "job", "stop"]
    assert "JX" in cli.calls[-1]


def test_teardown_wraps_cli_errors_in_compute_error() -> None:
    def run(argv: Sequence[str]) -> str:
        raise subprocess.CalledProcessError(1, list(argv))

    provider = NosanaProvider(market="m", run=run)
    with pytest.raises(ComputeError):
        provider.teardown(Deployment(provider="nosana", id="JX", model="m", status=DeploymentStatus.RUNNING))
