# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the desktop app's persisted onboarding/runtime configuration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sip_openai_proxy.config import AppConfig, LocalUse, config_path, load_config, save_config
from sip_protocol import KeyPair, build_provider_manifest, sign_provider_manifest
from sip_router import ProviderEntry

MODEL = "qwen-coder-7b"


def _entry(base_url: str = "http://node") -> ProviderEntry:
    kp = KeyPair.generate()
    manifest = sign_provider_manifest(
        build_provider_manifest(
            provider_pubkey=kp.public_key_str,
            models=[MODEL],
            runtime_adapters=["ollama"],
            pricing_unit="usdc",
            published_at="2026-06-30T00:00:00Z",
            manifest_uri=base_url,
        ),
        kp,
    )
    return ProviderEntry(base_url=base_url, manifest=manifest)


def test_default_config_is_empty_and_not_onboarded() -> None:
    cfg = AppConfig()
    assert cfg.providers == ()
    assert cfg.directories == ()
    assert cfg.onboarding_complete is False
    assert cfg.local_use is None
    assert cfg.api_key is None


def test_load_missing_returns_default(tmp_path: Path) -> None:
    cfg = load_config(tmp_path)
    assert cfg == AppConfig()


def test_save_then_load_roundtrips_all_fields(tmp_path: Path) -> None:
    entry = _entry()
    cfg = AppConfig(
        providers=(entry,),
        directories=("https://dir.example/sip", "/home/u/.sin/directory.json"),
        api_key="sk-local-abc",
        token="bearer-xyz",
        onboarding_complete=True,
        local_use=LocalUse(runtime="ollama", model=MODEL),
    )
    save_config(tmp_path, cfg)
    loaded = load_config(tmp_path)
    assert loaded == cfg
    # provider manifest survives intact (signature bytes preserved)
    assert loaded.providers[0].manifest == entry.manifest
    assert loaded.local_use == LocalUse(runtime="ollama", model=MODEL)


def test_save_creates_parent_dirs_and_writes_pretty_json(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "appdata"
    cfg = AppConfig(api_key="sk-1", onboarding_complete=True)
    save_config(nested, cfg)
    written = config_path(nested)
    assert written.is_file()
    data = json.loads(written.read_text())
    assert data["version"] == 1
    assert data["onboarding_complete"] is True


def test_save_is_atomic_no_tmp_left_behind(tmp_path: Path) -> None:
    save_config(tmp_path, AppConfig(api_key="sk-1"))
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "config.json"]
    assert leftovers == []


def test_load_corrupt_raises_valueerror(tmp_path: Path) -> None:
    config_path(tmp_path).write_text("{not valid json")
    with pytest.raises(ValueError):
        load_config(tmp_path)


def test_save_overwrites_existing(tmp_path: Path) -> None:
    save_config(tmp_path, AppConfig(api_key="first", onboarding_complete=False))
    save_config(tmp_path, AppConfig(api_key="second", onboarding_complete=True))
    loaded = load_config(tmp_path)
    assert loaded.api_key == "second"
    assert loaded.onboarding_complete is True
