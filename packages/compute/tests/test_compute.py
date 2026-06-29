# SPDX-License-Identifier: Apache-2.0
"""Tests for the shared external-compute contract."""

from __future__ import annotations

from dataclasses import replace

import pytest

from sip_compute import (
    ComputeError,
    Deployment,
    DeploymentStatus,
    InferenceSpec,
    available_providers,
    get_provider_factory,
    provider_manifest_for,
    register_provider,
)
from sip_protocol.manifests import verify_provider_manifest
from sip_protocol.signing import KeyPair


def _spec(**overrides: object) -> InferenceSpec:
    base: dict[str, object] = {
        "model": "qwen-coder-7b",
        "image": "ghcr.io/sovereign-inference/sip-gateway:latest",
        "port": 8080,
    }
    base.update(overrides)
    return InferenceSpec(**base)  # type: ignore[arg-type]


# -- InferenceSpec --------------------------------------------------------------


def test_inference_spec_defaults() -> None:
    spec = _spec()
    assert spec.gpu is True
    assert spec.env == {}
    assert spec.command is None
    assert spec.cpu == "1"
    assert spec.memory == "8Gi"


def test_inference_spec_is_frozen() -> None:
    spec = _spec()
    with pytest.raises(Exception):  # noqa: B017 - dataclass FrozenInstanceError
        spec.model = "other"  # type: ignore[misc]


def test_inference_spec_env_is_isolated_per_instance() -> None:
    a = _spec()
    b = _spec()
    a.env["X"] = "1"
    assert b.env == {}


def test_inference_spec_rejects_blank_model() -> None:
    with pytest.raises(ComputeError):
        _spec(model="  ")


def test_inference_spec_rejects_bad_port() -> None:
    with pytest.raises(ComputeError):
        _spec(port=0)
    with pytest.raises(ComputeError):
        _spec(port=70_000)


# -- DeploymentStatus -----------------------------------------------------------


def test_deployment_status_is_string_enum() -> None:
    assert DeploymentStatus.RUNNING == "running"
    assert DeploymentStatus("failed") is DeploymentStatus.FAILED


def test_deployment_status_terminal_and_ready() -> None:
    assert DeploymentStatus.RUNNING.is_ready
    assert not DeploymentStatus.PENDING.is_ready
    assert DeploymentStatus.FAILED.is_terminal
    assert DeploymentStatus.CLOSED.is_terminal
    assert not DeploymentStatus.RUNNING.is_terminal


# -- Deployment -----------------------------------------------------------------


def test_deployment_ready_requires_running_and_endpoint() -> None:
    pending = Deployment(provider="nosana", id="job1", model="m", status=DeploymentStatus.PENDING)
    assert not pending.is_ready
    running_no_url = replace(pending, status=DeploymentStatus.RUNNING)
    assert not running_no_url.is_ready
    ready = replace(running_no_url, endpoint="https://node.example/sip")
    assert ready.is_ready


def test_deployment_raw_defaults_isolated() -> None:
    a = Deployment(provider="p", id="1", model="m", status=DeploymentStatus.PENDING)
    b = Deployment(provider="p", id="2", model="m", status=DeploymentStatus.PENDING)
    a.raw["k"] = "v"
    assert b.raw == {}


def test_deployment_carries_optional_pricing() -> None:
    d = Deployment(
        provider="nosana",
        id="1",
        model="m",
        status=DeploymentStatus.RUNNING,
        endpoint="https://x",
        pricing_unit="usdc",
        input_per_1m=0.2,
        output_per_1m=0.6,
    )
    assert d.pricing_unit == "usdc"
    assert d.input_per_1m == 0.2
    assert d.output_per_1m == 0.6


def test_deployment_pricing_defaults_to_none() -> None:
    d = Deployment(provider="p", id="1", model="m", status=DeploymentStatus.PENDING)
    assert d.pricing_unit is None
    assert d.input_per_1m is None
    assert d.output_per_1m is None


# -- registry -------------------------------------------------------------------


def test_register_and_resolve_provider_factory() -> None:
    sentinel = object()

    def factory(**_kwargs: object) -> object:
        return sentinel

    register_provider("dummy-prov", factory)
    assert "dummy-prov" in available_providers()
    assert get_provider_factory("dummy-prov") is factory
    assert get_provider_factory("dummy-prov")() is sentinel


def test_get_unknown_provider_raises() -> None:
    with pytest.raises(ComputeError):
        get_provider_factory("does-not-exist-xyz")


# -- provider_manifest_for ------------------------------------------------------


def test_provider_manifest_for_builds_signed_external_manifest() -> None:
    keypair = KeyPair.generate()
    deployment = Deployment(
        provider="nosana",
        id="job-123",
        model="qwen-coder-7b",
        status=DeploymentStatus.RUNNING,
        endpoint="https://node.nosana.io/sip",
    )
    manifest = provider_manifest_for(
        deployment,
        keypair=keypair,
        input_per_1m=0.5,
        output_per_1m=1.5,
        pricing_unit="usdc",
    )
    assert manifest["schema"] == "sip-ai.provider_manifest.v1"
    assert manifest["node_type"] == "external-adapter"
    assert manifest["provider_pubkey"] == keypair.public_key_str
    assert manifest["models"] == ["qwen-coder-7b"]
    assert manifest["runtime_adapters"] == ["nosana"]
    assert manifest["manifest_uri"] == "https://node.nosana.io/sip"
    assert manifest["pricing"] == {"unit": "usdc", "input_per_1m": 0.5, "output_per_1m": 1.5}
    assert verify_provider_manifest(manifest) is True


def test_provider_manifest_for_defaults_pricing_from_deployment() -> None:
    keypair = KeyPair.generate()
    deployment = Deployment(
        provider="nosana",
        id="job-1",
        model="qwen-coder-7b",
        status=DeploymentStatus.RUNNING,
        endpoint="https://node.nosana.io/sip",
        pricing_unit="usdc",
        input_per_1m=0.2,
        output_per_1m=0.6,
    )
    # No explicit pricing passed -> the manifest advertises the spec/deployment price.
    manifest = provider_manifest_for(deployment, keypair=keypair)
    assert manifest["pricing"] == {"unit": "usdc", "input_per_1m": 0.2, "output_per_1m": 0.6}
    assert verify_provider_manifest(manifest) is True


def test_provider_manifest_for_explicit_pricing_overrides_deployment() -> None:
    keypair = KeyPair.generate()
    deployment = Deployment(
        provider="nosana",
        id="job-1",
        model="m",
        status=DeploymentStatus.RUNNING,
        endpoint="https://node",
        pricing_unit="usdc",
        input_per_1m=0.2,
        output_per_1m=0.6,
    )
    manifest = provider_manifest_for(
        deployment, keypair=keypair, pricing_unit="pic", input_per_1m=1.0, output_per_1m=2.0
    )
    assert manifest["pricing"] == {"unit": "pic", "input_per_1m": 1.0, "output_per_1m": 2.0}


def test_provider_manifest_for_requires_endpoint() -> None:
    keypair = KeyPair.generate()
    deployment = Deployment(
        provider="akash",
        id="dseq-1",
        model="m",
        status=DeploymentStatus.PENDING,
    )
    with pytest.raises(ComputeError):
        provider_manifest_for(deployment, keypair=keypair)


def test_provider_manifest_for_honours_overrides() -> None:
    keypair = KeyPair.generate()
    deployment = Deployment(
        provider="akash",
        id="dseq-7",
        model="qwen-coder-7b",
        status=DeploymentStatus.RUNNING,
        endpoint="https://lease.akash.io",
    )
    manifest = provider_manifest_for(
        deployment,
        keypair=keypair,
        models=["qwen-coder-7b", "qwen-coder-7b-instruct"],
        max_context=8192,
        logging_policy="metadata_only",
        privacy_modes=["direct", "private-payment"],
        published_at="2026-06-29T00:00:00Z",
    )
    assert manifest["models"] == ["qwen-coder-7b", "qwen-coder-7b-instruct"]
    assert manifest["max_context"] == 8192
    assert manifest["logging_policy"] == "metadata_only"
    assert manifest["privacy_modes"] == ["direct", "private-payment"]
    assert manifest["published_at"] == "2026-06-29T00:00:00Z"
    assert verify_provider_manifest(manifest) is True
