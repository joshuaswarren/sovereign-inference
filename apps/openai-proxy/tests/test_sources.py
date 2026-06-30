# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for turning untrusted provider input into trusted routing entries.

These guard the trust boundary the desktop admin API sits on: a provider is only
ever routed to if its manifest is validly signed AND the routing target is the
*signed* ``manifest_uri`` (never an attacker-chosen ``base_url``), and a remote
endpoint must be a safe public address (no SSRF pivot to loopback/metadata).
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from sip_openai_proxy.config import AppConfig
from sip_openai_proxy.sources import (
    UntrustedProvider,
    build_registry,
    is_safe_remote_url,
    merge_provider,
    trusted_provider_entry,
)
from sip_protocol import KeyPair, build_provider_manifest, sign_provider_manifest
from sip_router import ProviderEntry

MODEL = "qwen-coder-7b"


def _manifest(uri: str = "https://prov.example", kp: KeyPair | None = None) -> dict[str, Any]:
    kp = kp or KeyPair.generate()
    return sign_provider_manifest(
        build_provider_manifest(
            provider_pubkey=kp.public_key_str,
            models=[MODEL],
            runtime_adapters=["ollama"],
            pricing_unit="usdc",
            published_at="2026-06-30T00:00:00Z",
            manifest_uri=uri,
        ),
        kp,
    )


# -- is_safe_remote_url ---------------------------------------------------------


def test_safe_url_allows_public_https() -> None:
    assert is_safe_remote_url("https://prov.example/sip") is True


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11435",
        "http://localhost:8000",
        "http://169.254.169.254/latest/meta-data",  # cloud metadata
        "http://10.0.0.5",
        "http://192.168.1.10",
        "http://[::1]:9000",
        "ftp://prov.example",  # non-http scheme
        "not-a-url",
    ],
)
def test_safe_url_blocks_internal_and_non_http(url: str) -> None:
    assert is_safe_remote_url(url) is False


# -- trusted_provider_entry -----------------------------------------------------


def test_trusted_entry_accepts_valid_manifest_bound_to_its_uri() -> None:
    manifest = _manifest("https://prov.example")
    entry = trusted_provider_entry(manifest)
    assert entry.base_url == "https://prov.example"
    assert entry.manifest == manifest


def test_trusted_entry_rejects_tampered_signature() -> None:
    manifest = _manifest("https://prov.example")
    forged = copy.deepcopy(manifest)
    forged["models"] = ["evil-model"]  # body changed, signature now invalid
    with pytest.raises(UntrustedProvider):
        trusted_provider_entry(forged)


def test_trusted_entry_rejects_base_url_not_matching_signed_uri() -> None:
    # The core attack: a victim-signed manifest paired with an attacker base_url.
    manifest = _manifest("https://prov.example")
    with pytest.raises(UntrustedProvider):
        trusted_provider_entry(manifest, base_url="https://attacker.example")


def test_trusted_entry_rejects_missing_manifest_uri() -> None:
    kp = KeyPair.generate()
    manifest = sign_provider_manifest(
        build_provider_manifest(
            provider_pubkey=kp.public_key_str,
            models=[MODEL],
            runtime_adapters=["ollama"],
            pricing_unit="usdc",
            published_at="2026-06-30T00:00:00Z",
        ),
        kp,
    )
    with pytest.raises(UntrustedProvider):
        trusted_provider_entry(manifest)


def test_trusted_entry_rejects_ssrf_manifest_uri() -> None:
    manifest = _manifest("http://169.254.169.254")
    with pytest.raises(UntrustedProvider):
        trusted_provider_entry(manifest)


def test_trusted_entry_allows_loopback_uri_when_safe_url_not_required() -> None:
    # The local-use path fronts an in-process gateway; its sentinel URI is trusted.
    manifest = _manifest("http://127.0.0.1:0")
    entry = trusted_provider_entry(manifest, require_safe_url=False)
    assert entry.base_url == "http://127.0.0.1:0"


# -- merge_provider (dedupe + endpoint-hijack refusal) --------------------------


def test_merge_dedups_by_pubkey_keeping_newest() -> None:
    kp = KeyPair.generate()
    first = trusted_provider_entry(_manifest("https://prov.example", kp))
    second = trusted_provider_entry(_manifest("https://prov.example", kp))
    merged = merge_provider((first,), second)
    assert len(merged) == 1
    assert merged[0].manifest == second.manifest


def test_merge_refuses_endpoint_hijack_by_a_different_key() -> None:
    victim = trusted_provider_entry(_manifest("https://prov.example"))
    attacker = trusted_provider_entry(_manifest("https://prov.example"))  # same uri, new key
    with pytest.raises(UntrustedProvider):
        merge_provider((victim,), attacker)


# -- build_registry -------------------------------------------------------------


def test_build_registry_includes_valid_and_skips_untrusted(monkeypatch: pytest.MonkeyPatch) -> None:
    good = trusted_provider_entry(_manifest("https://good.example"))
    forged = copy.deepcopy(_manifest("https://bad.example"))
    forged["models"] = ["tampered"]
    cfg = AppConfig(providers=(good, ProviderEntry(base_url="https://bad.example", manifest=forged)))
    registry, warnings = build_registry(cfg)
    urls = {e.base_url for e in registry.all()}
    assert urls == {"https://good.example"}
    assert any("bad.example" in w for w in warnings)


def test_build_registry_pulls_from_directories_via_injected_resolver() -> None:
    disc_manifest = _manifest("https://dir-prov.example")

    class _FakeDirectory:
        def discover(self, *, model: str | None = None) -> list[Any]:
            from sip_discovery import DiscoveredProvider

            return [DiscoveredProvider(base_url="https://dir-prov.example", manifest=disc_manifest)]

    cfg = AppConfig(directories=("https://dir.example",))
    registry, warnings = build_registry(cfg, directory_for=lambda spec: _FakeDirectory())
    assert {e.base_url for e in registry.all()} == {"https://dir-prov.example"}
    assert warnings == []
