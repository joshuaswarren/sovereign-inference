# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the deterministic provider scoring and ranking."""

from __future__ import annotations

from typing import Any

from sip_protocol import KeyPair, sign_provider_manifest
from sip_router import ProviderEntry, rank_candidates, score_provider


def _entry(
    base_url: str,
    *,
    models: list[str],
    privacy_modes: list[str] | None = None,
    input_per_1m: float = 1.0,
    output_per_1m: float = 1.0,
    benchmark: dict[str, float] | None = None,
) -> ProviderEntry:
    kp = KeyPair.generate()
    manifest: dict[str, Any] = {
        "schema": "sip-ai.provider_manifest.v1",
        "provider_pubkey": kp.public_key_str,
        "node_type": "sovereign-node",
        "models": models,
        "runtime_adapters": ["llama.cpp"],
        "pricing": {
            "unit": "test",
            "input_per_1m": input_per_1m,
            "output_per_1m": output_per_1m,
        },
        "max_context": 8192,
        "logging_policy": "no_prompt_logging",
        "privacy_modes": privacy_modes if privacy_modes is not None else ["direct"],
        "published_at": "2026-06-29T00:00:00Z",
    }
    if benchmark is not None:
        manifest["benchmark"] = benchmark
    signed = sign_provider_manifest(manifest, kp)
    return ProviderEntry(base_url=base_url, manifest=signed)


def test_score_is_deterministic() -> None:
    entry = _entry("http://a", models=["m1"])
    first = score_provider(entry, privacy_mode="direct")
    second = score_provider(entry, privacy_mode="direct")
    assert first == second


def test_score_in_unit_range() -> None:
    entry = _entry("http://a", models=["m1"])
    score = score_provider(entry, privacy_mode="direct")
    assert 0.0 <= score <= 1.0


def test_model_not_supported_scores_lower() -> None:
    supported = _entry("http://a", models=["m1"])
    unsupported = _entry("http://b", models=["other"])
    # model_fit is only penalized when the caller requests an exact model match.
    assert score_provider(supported, privacy_mode="direct", model_id="m1") > score_provider(
        unsupported, privacy_mode="direct", model_id="m1"
    )


def test_faster_provider_scores_higher() -> None:
    fast = _entry(
        "http://fast",
        models=["m1"],
        benchmark={"ttft_ms": 50.0, "tokens_per_second": 200.0},
    )
    slow = _entry(
        "http://slow",
        models=["m1"],
        benchmark={"ttft_ms": 2000.0, "tokens_per_second": 5.0},
    )
    assert score_provider(fast, privacy_mode="direct") > score_provider(slow, privacy_mode="direct")


def test_cheaper_provider_scores_higher() -> None:
    cheap = _entry("http://cheap", models=["m1"], input_per_1m=0.1, output_per_1m=0.1)
    pricey = _entry("http://pricey", models=["m1"], input_per_1m=50.0, output_per_1m=50.0)
    assert score_provider(cheap, privacy_mode="direct") > score_provider(pricey, privacy_mode="direct")


def test_privacy_mode_match_scores_higher_than_mismatch() -> None:
    match = _entry("http://m", models=["m1"], privacy_modes=["direct", "relay"])
    mismatch = _entry("http://x", models=["m1"], privacy_modes=["direct"])
    assert score_provider(match, privacy_mode="relay") > score_provider(mismatch, privacy_mode="relay")


def test_measured_latency_overrides_benchmark() -> None:
    entry = _entry(
        "http://a",
        models=["m1"],
        benchmark={"ttft_ms": 2000.0, "tokens_per_second": 5.0},
    )
    measured_fast = score_provider(entry, privacy_mode="direct", measured_latency_ms=10.0)
    measured_slow = score_provider(entry, privacy_mode="direct", measured_latency_ms=5000.0)
    assert measured_fast > measured_slow


def test_weights_can_be_overridden() -> None:
    cheap = _entry("http://cheap", models=["m1"], input_per_1m=0.1, output_per_1m=0.1)
    pricey = _entry("http://pricey", models=["m1"], input_per_1m=50.0, output_per_1m=50.0)
    # With price weight zeroed (and the rest equal) the two should tie.
    weights = {
        "model_fit": 1.0,
        "expected_latency": 0.0,
        "price": 0.0,
        "receipt_trust": 0.0,
        "uptime": 0.0,
        "privacy_mode_match": 0.0,
    }
    assert score_provider(cheap, privacy_mode="direct", weights=weights) == score_provider(
        pricey, privacy_mode="direct", weights=weights
    )


def test_rank_candidates_orders_by_score_desc() -> None:
    cheap_fast = _entry(
        "http://best",
        models=["m1"],
        input_per_1m=0.1,
        output_per_1m=0.1,
        benchmark={"ttft_ms": 30.0, "tokens_per_second": 300.0},
    )
    pricey_slow = _entry(
        "http://worst",
        models=["m1"],
        input_per_1m=80.0,
        output_per_1m=80.0,
        benchmark={"ttft_ms": 3000.0, "tokens_per_second": 3.0},
    )
    ranked = rank_candidates([pricey_slow, cheap_fast], privacy_mode="direct")
    assert [e.base_url for e in ranked] == ["http://best", "http://worst"]


def test_rank_candidates_is_stable_for_ties() -> None:
    a = _entry("http://a", models=["m1"])
    b = _entry("http://b", models=["m1"])
    ranked = rank_candidates([a, b], privacy_mode="direct")
    assert [e.base_url for e in ranked] == ["http://a", "http://b"]
