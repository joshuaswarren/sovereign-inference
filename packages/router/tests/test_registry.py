# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the provider registry: model filtering and JSON load/save roundtrip."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sip_protocol import KeyPair, sign_provider_manifest
from sip_router import ProviderEntry, ProviderRegistry


def _manifest(*, models: list[str], pubkey: str) -> dict[str, Any]:
    return {
        "schema": "sip-ai.provider_manifest.v1",
        "provider_pubkey": pubkey,
        "node_type": "sovereign-node",
        "models": models,
        "runtime_adapters": ["llama.cpp"],
        "pricing": {"unit": "test", "input_per_1m": 0.0, "output_per_1m": 0.0},
        "max_context": 8192,
        "logging_policy": "no_prompt_logging",
        "privacy_modes": ["direct"],
        "published_at": "2026-06-29T00:00:00Z",
    }


def _entry(base_url: str, models: list[str]) -> ProviderEntry:
    kp = KeyPair.generate()
    manifest = sign_provider_manifest(_manifest(models=models, pubkey=kp.public_key_str), kp)
    return ProviderEntry(base_url=base_url, manifest=manifest)


def test_add_and_all_returns_every_entry() -> None:
    registry = ProviderRegistry()
    a = _entry("http://a", ["m1"])
    b = _entry("http://b", ["m2"])
    registry.add(a)
    registry.add(b)
    assert registry.all() == [a, b]


def test_for_model_filters_by_manifest_models() -> None:
    registry = ProviderRegistry()
    a = _entry("http://a", ["m1", "shared"])
    b = _entry("http://b", ["m2"])
    c = _entry("http://c", ["shared"])
    for entry in (a, b, c):
        registry.add(entry)

    matched = registry.for_model("shared")
    assert {e.base_url for e in matched} == {"http://a", "http://c"}
    assert registry.for_model("m2") == [b]
    assert registry.for_model("absent") == []


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    registry = ProviderRegistry()
    a = _entry("http://a", ["m1"])
    b = _entry("http://b", ["m2"])
    registry.add(a)
    registry.add(b)

    path = tmp_path / "providers.json"
    registry.save(path)

    # The on-disk format is a JSON list of {base_url, manifest}.
    raw = json.loads(path.read_text())
    assert isinstance(raw, list)
    assert raw[0]["base_url"] == "http://a"
    assert raw[0]["manifest"]["models"] == ["m1"]

    loaded = ProviderRegistry.load(path)
    assert [e.base_url for e in loaded.all()] == ["http://a", "http://b"]
    assert loaded.all()[0].manifest == a.manifest


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    loaded = ProviderRegistry.load(tmp_path / "nope.json")
    assert loaded.all() == []


def test_load_corrupt_file_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not valid json")
    loaded = ProviderRegistry.load(path)
    assert loaded.all() == []


def test_load_non_list_payload_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "obj.json"
    path.write_text(json.dumps({"base_url": "http://a"}))
    loaded = ProviderRegistry.load(path)
    assert loaded.all() == []


def test_save_and_load_accept_str_path(tmp_path: Path) -> None:
    registry = ProviderRegistry()
    registry.add(_entry("http://a", ["m1"]))
    path = tmp_path / "providers.json"
    registry.save(str(path))
    assert path.exists()
    loaded = ProviderRegistry.load(str(path))
    assert [e.base_url for e in loaded.all()] == ["http://a"]
