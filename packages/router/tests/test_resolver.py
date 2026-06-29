# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for resolve(): filter by model, rank, and (optionally) drop bad manifests."""

from __future__ import annotations

from typing import Any

from sip_protocol import KeyPair, sign_provider_manifest
from sip_router import ProviderEntry, ProviderRegistry, resolve


def _signed_entry(
    base_url: str,
    *,
    models: list[str],
    input_per_1m: float = 1.0,
    benchmark: dict[str, float] | None = None,
) -> ProviderEntry:
    kp = KeyPair.generate()
    manifest: dict[str, Any] = {
        "schema": "sip-ai.provider_manifest.v1",
        "provider_pubkey": kp.public_key_str,
        "node_type": "sovereign-node",
        "models": models,
        "runtime_adapters": ["llama.cpp"],
        "pricing": {"unit": "test", "input_per_1m": input_per_1m, "output_per_1m": input_per_1m},
        "max_context": 8192,
        "logging_policy": "no_prompt_logging",
        "privacy_modes": ["direct"],
        "published_at": "2026-06-29T00:00:00Z",
    }
    if benchmark is not None:
        manifest["benchmark"] = benchmark
    return ProviderEntry(base_url=base_url, manifest=sign_provider_manifest(manifest, kp))


def _tampered_entry(base_url: str, *, models: list[str]) -> ProviderEntry:
    """A signed entry whose manifest is mutated after signing -> fails verification."""
    entry = _signed_entry(base_url, models=models)
    broken = dict(entry.manifest)
    broken["max_context"] = 4096  # mutate a signed field
    return ProviderEntry(base_url=base_url, manifest=broken)


def test_resolve_filters_to_matching_model() -> None:
    registry = ProviderRegistry()
    registry.add(_signed_entry("http://a", models=["m1"]))
    registry.add(_signed_entry("http://b", models=["m2"]))
    resolved = resolve(registry, "m1")
    assert [e.base_url for e in resolved] == ["http://a"]


def test_resolve_ranks_candidates() -> None:
    registry = ProviderRegistry()
    registry.add(
        _signed_entry(
            "http://slow",
            models=["m1"],
            input_per_1m=50.0,
            benchmark={"ttft_ms": 3000.0, "tokens_per_second": 3.0},
        )
    )
    registry.add(
        _signed_entry(
            "http://fast",
            models=["m1"],
            input_per_1m=0.1,
            benchmark={"ttft_ms": 30.0, "tokens_per_second": 300.0},
        )
    )
    resolved = resolve(registry, "m1", privacy_mode="direct")
    assert [e.base_url for e in resolved] == ["http://fast", "http://slow"]


def test_resolve_keeps_valid_manifests_when_verifying() -> None:
    registry = ProviderRegistry()
    registry.add(_signed_entry("http://good", models=["m1"]))
    resolved = resolve(registry, "m1", verify_manifests=True)
    assert [e.base_url for e in resolved] == ["http://good"]


def test_resolve_drops_invalid_manifests_when_verifying() -> None:
    registry = ProviderRegistry()
    registry.add(_signed_entry("http://good", models=["m1"]))
    registry.add(_tampered_entry("http://tampered", models=["m1"]))
    resolved = resolve(registry, "m1", verify_manifests=True)
    assert [e.base_url for e in resolved] == ["http://good"]


def test_resolve_keeps_invalid_manifests_when_not_verifying() -> None:
    registry = ProviderRegistry()
    registry.add(_tampered_entry("http://tampered", models=["m1"]))
    resolved = resolve(registry, "m1", verify_manifests=False)
    assert [e.base_url for e in resolved] == ["http://tampered"]


def test_resolve_empty_for_unknown_model() -> None:
    registry = ProviderRegistry()
    registry.add(_signed_entry("http://a", models=["m1"]))
    assert resolve(registry, "absent") == []
