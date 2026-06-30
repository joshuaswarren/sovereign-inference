# SPDX-License-Identifier: Apache-2.0
"""Tests for provider announce/discover over file and Arweave directories."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest

from sip_arweave import LocalAnchor
from sip_discovery import (
    ArweaveDirectory,
    DiscoveredProvider,
    DiscoveryError,
    FileDirectory,
    HttpDirectory,
)
from sip_protocol.manifests import sign_provider_manifest
from sip_protocol.signing import KeyPair


def _manifest(
    keypair: KeyPair,
    *,
    models: Sequence[str] = ("qwen-coder-7b",),
    base_url: str = "http://node.example",
    published_at: str = "2026-06-29T00:00:00Z",
) -> dict[str, Any]:
    manifest = {
        "schema": "sip-ai.provider_manifest.v1",
        "provider_pubkey": keypair.public_key_str,
        "node_type": "sovereign-node",
        "models": list(models),
        "runtime_adapters": ["ollama"],
        "pricing": {"unit": "usdc", "input_per_1m": 0.2, "output_per_1m": 0.6},
        "max_context": 8192,
        "logging_policy": "no_prompt_logging",
        "privacy_modes": ["direct"],
        "manifest_uri": base_url,
        "published_at": published_at,
    }
    return sign_provider_manifest(manifest, keypair)


# -- DiscoveredProvider ---------------------------------------------------------


def test_discovered_provider_accessors() -> None:
    kp = KeyPair.generate()
    manifest = _manifest(kp, models=["a", "b"])
    p = DiscoveredProvider(base_url="http://x", manifest=manifest)
    assert p.provider_pubkey == kp.public_key_str
    assert p.models == ["a", "b"]
    assert p.serves("a") and not p.serves("z")


# -- FileDirectory --------------------------------------------------------------


def test_file_directory_announce_and_discover_round_trip() -> None:
    kp = KeyPair.generate()
    with tempfile.TemporaryDirectory() as d:
        directory = FileDirectory(Path(d) / "providers.json")
        directory.announce(_manifest(kp, base_url="http://node-a"))
        found = directory.discover()
        assert len(found) == 1
        assert found[0].base_url == "http://node-a"
        assert found[0].provider_pubkey == kp.public_key_str


def test_file_directory_defaults_base_url_to_manifest_uri() -> None:
    kp = KeyPair.generate()
    with tempfile.TemporaryDirectory() as d:
        directory = FileDirectory(Path(d) / "p.json")
        directory.announce(_manifest(kp, base_url="http://from-manifest"))
        assert directory.discover()[0].base_url == "http://from-manifest"


def test_file_directory_rejects_base_url_not_matching_signed_manifest_uri() -> None:
    # An explicit base_url the signature does not cover must be refused — otherwise
    # a node could be announced at an endpoint its manifest never authorized.
    kp = KeyPair.generate()
    with tempfile.TemporaryDirectory() as d:
        directory = FileDirectory(Path(d) / "p.json")
        with pytest.raises(DiscoveryError):
            directory.announce(_manifest(kp, base_url="http://signed"), base_url="http://different")


def test_file_directory_ignores_injected_unsigned_base_url() -> None:
    # Directory poisoning: an attacker who can write the shared file injects an
    # unsigned base_url next to a victim's valid manifest. Routing must use the
    # SIGNED manifest_uri, never the unsigned wrapper field.
    kp = KeyPair.generate()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "p.json"
        directory = FileDirectory(path)
        directory.announce(_manifest(kp, base_url="http://honest-node"))
        raw = json.loads(path.read_text())
        entry = next(iter(raw.values()))
        entry["base_url"] = "http://attacker.evil/steal"  # inject an unsigned field
        path.write_text(json.dumps(raw))
        found = directory.discover()
        assert len(found) == 1
        assert found[0].base_url == "http://honest-node"  # the signed manifest_uri wins


def test_file_directory_rejects_invalid_manifest_on_announce() -> None:
    kp = KeyPair.generate()
    manifest = _manifest(kp)
    manifest["models"] = ["tampered"]  # breaks the signature
    with tempfile.TemporaryDirectory() as d:
        directory = FileDirectory(Path(d) / "p.json")
        with pytest.raises(DiscoveryError):
            directory.announce(manifest)


def test_file_directory_rejects_announce_without_base_url() -> None:
    kp = KeyPair.generate()
    manifest = _manifest(kp)
    del manifest["manifest_uri"]
    # re-sign so the only problem is the missing endpoint, not the signature
    manifest.pop("signature")
    manifest = sign_provider_manifest(manifest, kp)
    with tempfile.TemporaryDirectory() as d:
        directory = FileDirectory(Path(d) / "p.json")
        with pytest.raises(DiscoveryError):
            directory.announce(manifest)


def test_file_directory_filters_by_model() -> None:
    kp_a, kp_b = KeyPair.generate(), KeyPair.generate()
    with tempfile.TemporaryDirectory() as d:
        directory = FileDirectory(Path(d) / "p.json")
        directory.announce(_manifest(kp_a, models=["coder"], base_url="http://a"))
        directory.announce(_manifest(kp_b, models=["vision"], base_url="http://b"))
        coder = directory.discover(model="coder")
        assert [p.base_url for p in coder] == ["http://a"]


def test_file_directory_reannounce_updates_in_place() -> None:
    kp = KeyPair.generate()
    with tempfile.TemporaryDirectory() as d:
        directory = FileDirectory(Path(d) / "p.json")
        directory.announce(_manifest(kp, base_url="http://old", published_at="2026-06-29T00:00:00Z"))
        directory.announce(_manifest(kp, base_url="http://new", published_at="2026-06-30T00:00:00Z"))
        found = directory.discover()
        assert len(found) == 1  # one entry per provider key
        assert found[0].base_url == "http://new"


def test_file_directory_discover_skips_tampered_file_entry() -> None:
    kp = KeyPair.generate()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "p.json"
        directory = FileDirectory(path)
        directory.announce(_manifest(kp, base_url="http://a"))
        # Tamper with the on-disk manifest so its signature no longer verifies.
        raw = json.loads(path.read_text())
        entry = next(iter(raw.values()))
        entry["manifest"]["models"] = ["evil"]
        path.write_text(json.dumps(raw))
        assert directory.discover() == []


def test_file_directory_discover_empty_when_no_file() -> None:
    with tempfile.TemporaryDirectory() as d:
        directory = FileDirectory(Path(d) / "does-not-exist.json")
        assert directory.discover() == []


# -- ArweaveDirectory -----------------------------------------------------------


def _arweave_pair() -> tuple[ArweaveDirectory, list[str]]:
    """An ArweaveDirectory backed by a temp LocalAnchor + a query over announced uris."""
    anchor = LocalAnchor(tempfile.mkdtemp())
    announced: list[str] = []

    def query(_tags: dict[str, str]) -> list[str]:
        return list(announced)

    directory = ArweaveDirectory(anchor, query=query)
    return directory, announced


def test_arweave_directory_announce_and_discover_round_trip() -> None:
    kp = KeyPair.generate()
    directory, announced = _arweave_pair()
    uri = directory.announce(_manifest(kp, base_url="http://node-z"))
    announced.append(uri)
    found = directory.discover()
    assert len(found) == 1
    assert found[0].provider_pubkey == kp.public_key_str
    assert found[0].base_url == "http://node-z"


def test_arweave_directory_rejects_invalid_manifest() -> None:
    kp = KeyPair.generate()
    directory, _ = _arweave_pair()
    manifest = _manifest(kp)
    manifest["models"] = ["tampered"]
    with pytest.raises(DiscoveryError):
        directory.announce(manifest)


def test_arweave_directory_discover_without_query_raises() -> None:
    anchor = LocalAnchor(tempfile.mkdtemp())
    directory = ArweaveDirectory(anchor)
    with pytest.raises(DiscoveryError):
        directory.discover()


def test_arweave_directory_filters_by_model() -> None:
    kp_a, kp_b = KeyPair.generate(), KeyPair.generate()
    directory, announced = _arweave_pair()
    announced.append(directory.announce(_manifest(kp_a, models=["coder"], base_url="http://a")))
    announced.append(directory.announce(_manifest(kp_b, models=["vision"], base_url="http://b")))
    assert [p.base_url for p in directory.discover(model="vision")] == ["http://b"]


def test_arweave_directory_dedupes_by_pubkey_keeping_freshest() -> None:
    kp = KeyPair.generate()
    directory, announced = _arweave_pair()
    announced.append(directory.announce(_manifest(kp, base_url="http://old", published_at="2026-06-01T00:00:00Z")))
    announced.append(directory.announce(_manifest(kp, base_url="http://new", published_at="2026-06-29T00:00:00Z")))
    found = directory.discover()
    assert len(found) == 1
    assert found[0].base_url == "http://new"


def test_arweave_directory_discover_skips_unverifiable_manifest() -> None:
    kp = KeyPair.generate()
    anchor = LocalAnchor(tempfile.mkdtemp())
    # Plant a bytes blob that is a tampered (unverifiable) manifest, plus a good one.
    good = _manifest(kp, base_url="http://good")
    bad = _manifest(KeyPair.generate(), base_url="http://bad")
    bad["models"] = ["tampered"]
    from sip_protocol.canonical import canonical_json

    good_uri = anchor.put(canonical_json(good), content_type="application/json")
    bad_uri = anchor.put(canonical_json(bad), content_type="application/json")

    def query(_tags: dict[str, str]) -> list[str]:
        return [bad_uri, good_uri]

    directory = ArweaveDirectory(anchor, query=query)
    found = directory.discover()
    assert [p.base_url for p in found] == ["http://good"]


# -- HttpDirectory (client) -----------------------------------------------------


def _mock_http_directory(handler: Any, *, base_url: str = "http://relay") -> HttpDirectory:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return HttpDirectory(base_url, client=client)


def test_http_directory_announce_posts_signed_manifest() -> None:
    kp = KeyPair.generate()
    manifest = _manifest(kp, base_url="http://node")
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ref": manifest["provider_pubkey"]})

    directory = _mock_http_directory(handler)
    ref = directory.announce(manifest)
    assert ref == manifest["provider_pubkey"]
    assert captured["path"] == "/directory/announce"
    assert captured["body"] == manifest


def test_http_directory_announce_rejects_invalid_without_calling_server() -> None:
    kp = KeyPair.generate()
    manifest = _manifest(kp)
    manifest["models"] = ["tampered"]
    posted: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        posted.append(1)
        return httpx.Response(200, json={})

    directory = _mock_http_directory(handler)
    with pytest.raises(DiscoveryError):
        directory.announce(manifest)
    assert posted == []  # an invalid manifest never reaches the relay


def test_http_directory_discover_verifies_and_uses_signed_manifest_uri() -> None:
    kp = KeyPair.generate()
    good = _manifest(kp, base_url="http://honest-node")
    forged = _manifest(KeyPair.generate(), base_url="http://attacker")
    forged["models"] = ["tampered"]  # breaks the signature

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/directory/providers"
        return httpx.Response(200, json={"providers": [forged, good]})

    directory = _mock_http_directory(handler)
    found = directory.discover()
    # the relay cannot forge a manifest, and routing uses the signed manifest_uri
    assert [p.base_url for p in found] == ["http://honest-node"]


def test_http_directory_discover_passes_model_filter() -> None:
    kp = KeyPair.generate()
    manifest = _manifest(kp, models=["coder"], base_url="http://node")
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["model"] = request.url.params.get("model")
        return httpx.Response(200, json={"providers": [manifest]})

    directory = _mock_http_directory(handler)
    found = directory.discover(model="coder")
    assert seen["model"] == "coder"
    assert len(found) == 1


def test_http_directory_discover_http_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    directory = _mock_http_directory(handler)
    with pytest.raises(DiscoveryError):
        directory.discover()
