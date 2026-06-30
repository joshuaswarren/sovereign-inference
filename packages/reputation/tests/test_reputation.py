# SPDX-License-Identifier: Apache-2.0
"""Tests for provider health probing, reputation tracking, and ranking."""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest

from sip_discovery import DiscoveredProvider
from sip_protocol.manifests import sign_provider_manifest
from sip_protocol.signing import KeyPair
from sip_reputation import (
    HealthProbe,
    ReputationStore,
    rank_providers,
)


def _provider(
    keypair: KeyPair,
    *,
    base_url: str = "http://node",
    models: Sequence[str] = ("qwen-coder-7b",),
    tps: float = 30.0,
) -> DiscoveredProvider:
    manifest = sign_provider_manifest(
        {
            "schema": "sip-ai.provider_manifest.v1",
            "provider_pubkey": keypair.public_key_str,
            "node_type": "sovereign-node",
            "models": list(models),
            "runtime_adapters": ["ollama"],
            "pricing": {"unit": "usdc", "input_per_1m": 0.2, "output_per_1m": 0.6},
            "max_context": 8192,
            "logging_policy": "no_prompt_logging",
            "privacy_modes": ["direct"],
            "benchmark": {"tokens_per_second": tps, "ttft_ms": 500},
            "manifest_uri": base_url,
            "published_at": "2026-06-30T00:00:00Z",
        },
        keypair,
    )
    return DiscoveredProvider(base_url=base_url, manifest=manifest)


# -- HealthProbe ----------------------------------------------------------------


def _probe_for(handler: Any, *, clock: Any = None) -> HealthProbe:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    if clock is None:
        ticks = iter([1.0, 1.040])  # 40ms
        return HealthProbe(client=client, clock=lambda: next(ticks))
    return HealthProbe(client=client, clock=clock)


def test_health_probe_ok_when_live_and_matching() -> None:
    kp = KeyPair.generate()
    provider = _provider(kp)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sip/v1/health"
        return httpx.Response(
            200, json={"status": "ok", "provider_pubkey": kp.public_key_str, "models": ["qwen-coder-7b"]}
        )

    status = _probe_for(handler).check(provider)
    assert status.reachable and status.pubkey_match and status.model_match
    assert status.ok
    assert status.latency_ms == pytest.approx(40.0, abs=1.0)


def test_health_probe_pubkey_mismatch_is_not_ok() -> None:
    kp = KeyPair.generate()
    provider = _provider(kp)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": "ok", "provider_pubkey": "ed25519:someoneelse", "models": ["qwen-coder-7b"]}
        )

    status = _probe_for(handler).check(provider)
    assert not status.pubkey_match
    assert not status.ok


def test_health_probe_model_mismatch_is_not_ok() -> None:
    kp = KeyPair.generate()
    provider = _provider(kp, models=["qwen-coder-7b"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": "ok", "provider_pubkey": kp.public_key_str, "models": ["something-else"]}
        )

    status = _probe_for(handler).check(provider)
    assert not status.model_match
    assert not status.ok


def test_health_probe_unreachable_is_not_ok() -> None:
    kp = KeyPair.generate()
    provider = _provider(kp)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    status = _probe_for(handler).check(provider)
    assert not status.reachable
    assert not status.ok
    assert status.latency_ms is None


# -- ReputationStore ------------------------------------------------------------


def test_reputation_unknown_provider_is_neutral() -> None:
    with tempfile.TemporaryDirectory() as d:
        store = ReputationStore(Path(d) / "rep.json")
        score = store.score("ed25519:unknown")
        assert score.samples == 0
        assert score.score == pytest.approx(0.5)  # cold start: neutral, not starved


def test_reputation_aggregates_outcomes() -> None:
    with tempfile.TemporaryDirectory() as d:
        store = ReputationStore(Path(d) / "rep.json")
        pk = "ed25519:abc"
        store.record(pk, success=True, latency_ms=100.0, receipt_valid=True)
        store.record(pk, success=True, latency_ms=200.0, receipt_valid=True)
        store.record(pk, success=True, latency_ms=300.0, receipt_valid=False)
        store.record(pk, success=False, receipt_valid=False)
        score = store.score(pk)
        assert score.samples == 4
        assert score.success_rate == pytest.approx(0.75)
        assert score.receipt_valid_rate == pytest.approx(0.5)
        assert score.avg_latency_ms == pytest.approx(200.0)  # over the 3 with latency
        assert 0.0 < score.score < 1.0


def test_reputation_persists_across_instances() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "rep.json"
        ReputationStore(path).record("ed25519:p", success=True, receipt_valid=True)
        reloaded = ReputationStore(path).score("ed25519:p")
        assert reloaded.samples == 1
        assert reloaded.success_rate == pytest.approx(1.0)


# -- rank_providers -------------------------------------------------------------


def test_rank_orders_by_reputation() -> None:
    kp_good, kp_bad = KeyPair.generate(), KeyPair.generate()
    good, bad = _provider(kp_good, base_url="http://good"), _provider(kp_bad, base_url="http://bad")
    with tempfile.TemporaryDirectory() as d:
        store = ReputationStore(Path(d) / "rep.json")
        for _ in range(5):
            store.record(kp_good.public_key_str, success=True, receipt_valid=True, latency_ms=50.0)
        for _ in range(5):
            store.record(kp_bad.public_key_str, success=False)
        ranked = rank_providers([bad, good], store=store)
        assert [r.provider.base_url for r in ranked] == ["http://good", "http://bad"]
        assert ranked[0].score > ranked[1].score


def test_rank_drops_unreachable_when_probed() -> None:
    kp_up, kp_down = KeyPair.generate(), KeyPair.generate()
    up = _provider(kp_up, base_url="http://up")
    down = _provider(kp_down, base_url="http://down")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "up":
            return httpx.Response(
                200, json={"status": "ok", "provider_pubkey": kp_up.public_key_str, "models": ["qwen-coder-7b"]}
            )
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    ticks = iter([0.0, 0.01] * 10)
    probe = HealthProbe(client=client, clock=lambda: next(ticks))
    with tempfile.TemporaryDirectory() as d:
        store = ReputationStore(Path(d) / "rep.json")
        ranked = rank_providers([up, down], store=store, probe=probe)
        assert [r.provider.base_url for r in ranked] == ["http://up"]  # dead node dropped


def test_rank_tie_breaks_by_advertised_tps_when_no_latency() -> None:
    # Two providers with identical (neutral) reputation and no latency; tps decides.
    kp_fast, kp_slow = KeyPair.generate(), KeyPair.generate()
    fast = _provider(kp_fast, base_url="http://fast", tps=80.0)
    slow = _provider(kp_slow, base_url="http://slow", tps=10.0)
    with tempfile.TemporaryDirectory() as d:
        store = ReputationStore(Path(d) / "rep.json")
        ranked = rank_providers([slow, fast], store=store)
        assert [r.provider.base_url for r in ranked] == ["http://fast", "http://slow"]


def test_rank_tie_breaks_by_latency_before_benchmark() -> None:
    # Equal reputation; the lower recorded latency wins even if its advertised tps
    # is worse — latency is the first tie-breaker, ahead of benchmark.
    kp_low, kp_high = KeyPair.generate(), KeyPair.generate()
    low_latency = _provider(kp_low, base_url="http://low-latency", tps=10.0)
    high_latency = _provider(kp_high, base_url="http://high-latency", tps=80.0)
    with tempfile.TemporaryDirectory() as d:
        store = ReputationStore(Path(d) / "rep.json")
        # Identical reputation score (one clean success each), differing latency.
        store.record(kp_low.public_key_str, success=True, receipt_valid=True, latency_ms=20.0)
        store.record(kp_high.public_key_str, success=True, receipt_valid=True, latency_ms=500.0)
        ranked = rank_providers([high_latency, low_latency], store=store)
        assert ranked[0].reputation.score == pytest.approx(ranked[1].reputation.score)
        assert [r.provider.base_url for r in ranked] == ["http://low-latency", "http://high-latency"]
