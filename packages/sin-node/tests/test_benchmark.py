# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the benchmark runner: endpoint timing, context probing, manifest."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from sin_node.benchmark import (
    benchmark_endpoint,
    probe_max_stable_context,
    to_provider_manifest,
)
from sin_node.models import (
    Accelerator,
    BenchmarkResult,
    CPUInfo,
    HardwareProfile,
    RuntimeInfo,
)
from sip_protocol import KeyPair, verify_provider_manifest


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _profile() -> HardwareProfile:
    return HardwareProfile(
        os="Darwin",
        os_version="15.0",
        arch="arm64",
        cpu=CPUInfo(arch="arm64", model="Apple M3 Max", physical_cores=14, logical_cores=14),
        ram_total_gb=64.0,
        ram_available_gb=40.0,
        disk_free_gb=500.0,
        gpus=[],
        accelerator=Accelerator.metal,
        unified_memory=True,
        runtimes=[
            RuntimeInfo(name="ollama", available=True, version="0.1.0"),
            RuntimeInfo(name="llamacpp", available=False),
        ],
    )


# --- benchmark_endpoint -----------------------------------------------------


def test_benchmark_endpoint_measures_ttft_and_tps() -> None:
    sse = "".join(
        [
            'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n',
            'data: {"choices":[{"delta":{"content":"Salt"}}]}\n\n',
            'data: {"choices":[{"delta":{"content":" spray"}}]}\n\n',
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
            '"usage":{"prompt_tokens":7,"completion_tokens":40}}\n\n',
            "data: [DONE]\n\n",
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        assert body["stream"] is True
        assert body["max_tokens"] == 64
        return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})

    # start, first-content-token, end
    clock_values = iter([0.0, 0.25, 4.25])
    result = benchmark_endpoint(
        "http://node",
        "qwen-coder-7b",
        runtime="ollama",
        max_tokens=64,
        client=_client(handler),
        clock=lambda: next(clock_values),
        now=lambda: "2026-06-29T12:00:00Z",
    )
    assert isinstance(result, BenchmarkResult)
    assert result.model_alias == "qwen-coder-7b"
    assert result.runtime == "ollama"
    assert result.ttft_ms == pytest.approx(250.0)  # 0.25 s -> 250 ms
    assert result.output_tokens == 40
    # tps = 40 / (4.25 - 0.25) = 10
    assert result.tokens_per_second == pytest.approx(10.0)
    assert result.measured_at == "2026-06-29T12:00:00Z"


def test_benchmark_endpoint_default_now_is_iso_utc() -> None:
    sse = (
        'data: {"choices":[{"delta":{"content":"x"}}]}\n\n'
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
        '"usage":{"prompt_tokens":1,"completion_tokens":1}}\n\n'
        "data: [DONE]\n\n"
    )
    clock_values = iter([0.0, 0.1, 0.2])
    result = benchmark_endpoint(
        "http://node",
        "m",
        client=_client(lambda r: httpx.Response(200, text=sse)),
        clock=lambda: next(clock_values),
    )
    # Default measured_at is an ISO-8601 UTC timestamp.
    assert result.measured_at is not None
    assert result.measured_at.endswith("Z") or "+00:00" in result.measured_at
    assert result.runtime == "unknown"


# --- probe_max_stable_context ----------------------------------------------


def test_probe_returns_largest_passing_context() -> None:
    # Succeeds at 2048 and 4096, fails at 8192.
    def prober(context: int) -> bool:
        return context <= 4096

    contexts = [2048, 4096, 8192, 16384]
    assert probe_max_stable_context(contexts, prober) == 4096


def test_probe_stops_at_first_failure_even_if_later_would_pass() -> None:
    calls: list[int] = []

    def prober(context: int) -> bool:
        calls.append(context)
        return context != 4096  # 4096 fails, but 8192 "would" pass

    contexts = [2048, 4096, 8192]
    assert probe_max_stable_context(contexts, prober) == 2048
    # We must stop probing after the first failure.
    assert calls == [2048, 4096]


def test_probe_returns_none_when_nothing_passes() -> None:
    assert probe_max_stable_context([2048, 4096], lambda c: False) is None


def test_probe_returns_none_for_empty_contexts() -> None:
    assert probe_max_stable_context([], lambda c: True) is None


# --- to_provider_manifest ---------------------------------------------------


def _bench_result() -> BenchmarkResult:
    return BenchmarkResult(
        model_alias="qwen-coder-7b",
        runtime="ollama",
        ttft_ms=253.7,
        tokens_per_second=42.345,
        output_tokens=128,
        input_tokens=12,
        max_stable_context=8192,
        measured_at="2026-06-29T12:00:00Z",
    )


def test_manifest_verifies_and_embeds_benchmark() -> None:
    keypair = KeyPair.generate()
    manifest = to_provider_manifest(
        _profile(),
        models=["qwen-coder-7b"],
        result=_bench_result(),
        pricing={"unit": "test"},
        privacy_modes=["direct"],
        keypair=keypair,
        published_at="2026-06-29T12:00:00Z",
    )
    assert manifest["schema"] == "sip-ai.provider_manifest.v1"
    assert manifest["provider_pubkey"] == keypair.public_key_str
    assert manifest["node_type"] == "sovereign-node"
    assert manifest["models"] == ["qwen-coder-7b"]
    # runtime_adapters derives from available runtimes on the profile.
    assert "ollama" in manifest["runtime_adapters"]
    assert manifest["max_context"] == 8192
    # benchmark embedded with sensibly rounded numbers.
    assert manifest["benchmark"]["tokens_per_second"] == pytest.approx(42.3)
    assert manifest["benchmark"]["ttft_ms"] == pytest.approx(254.0)
    # The signed manifest must verify against the schema + signature.
    assert verify_provider_manifest(manifest) is True


def test_manifest_respects_node_type_and_pricing() -> None:
    keypair = KeyPair.generate()
    manifest = to_provider_manifest(
        _profile(),
        models=["m1", "m2"],
        result=_bench_result(),
        pricing={"unit": "usdc", "input_per_1m": 0.5, "output_per_1m": 1.5},
        privacy_modes=["direct", "relay"],
        keypair=keypair,
        node_type="vllm-server",
        published_at="2026-06-29T12:00:00Z",
    )
    assert manifest["node_type"] == "vllm-server"
    assert manifest["pricing"]["output_per_1m"] == 1.5
    assert manifest["privacy_modes"] == ["direct", "relay"]
    assert verify_provider_manifest(manifest) is True


def test_manifest_falls_back_to_result_runtime_when_no_runtimes() -> None:
    profile = _profile()
    profile.runtimes = []
    keypair = KeyPair.generate()
    manifest = to_provider_manifest(
        profile,
        models=["m"],
        result=_bench_result(),
        pricing={"unit": "test"},
        privacy_modes=["direct"],
        keypair=keypair,
        published_at="2026-06-29T12:00:00Z",
    )
    # With no detected runtimes, fall back to the benchmark's runtime.
    assert manifest["runtime_adapters"] == ["ollama"]
    assert verify_provider_manifest(manifest) is True
