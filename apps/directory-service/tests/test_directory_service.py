# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the hosted directory service (client ↔ server round-trip)."""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from sip_directory_service import create_directory_app
from sip_discovery import FileDirectory, HttpDirectory
from sip_protocol.manifests import sign_provider_manifest
from sip_protocol.signing import KeyPair


def _manifest(
    keypair: KeyPair,
    *,
    models: Sequence[str] = ("qwen-coder-7b",),
    base_url: str = "http://node.example",
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
        "published_at": "2026-06-30T00:00:00Z",
    }
    return sign_provider_manifest(manifest, keypair)


def _client_directory(store_dir: str) -> tuple[HttpDirectory, TestClient]:
    app = create_directory_app(FileDirectory(Path(store_dir) / "store.json"))
    test_client = TestClient(app)
    return HttpDirectory("http://testserver", client=test_client), test_client


def test_announce_then_discover_round_trip_over_http() -> None:
    kp = KeyPair.generate()
    with tempfile.TemporaryDirectory() as d:
        directory, _ = _client_directory(d)
        directory.announce(_manifest(kp, base_url="http://node-a"))
        found = directory.discover()
        assert len(found) == 1
        assert found[0].base_url == "http://node-a"
        assert found[0].provider_pubkey == kp.public_key_str


def test_announce_rejects_forged_manifest_with_400() -> None:
    kp = KeyPair.generate()
    forged = _manifest(kp)
    forged["models"] = ["tampered"]  # breaks the signature
    with tempfile.TemporaryDirectory() as d:
        _, test_client = _client_directory(d)
        resp = test_client.post("/directory/announce", json=forged)
        assert resp.status_code == 400


def test_discover_filters_by_model_over_http() -> None:
    kp_a, kp_b = KeyPair.generate(), KeyPair.generate()
    with tempfile.TemporaryDirectory() as d:
        directory, _ = _client_directory(d)
        directory.announce(_manifest(kp_a, models=["coder"], base_url="http://a"))
        directory.announce(_manifest(kp_b, models=["vision"], base_url="http://b"))
        coder = directory.discover(model="coder")
        assert [p.base_url for p in coder] == ["http://a"]


def test_providers_endpoint_returns_plain_manifests() -> None:
    kp = KeyPair.generate()
    with tempfile.TemporaryDirectory() as d:
        directory, test_client = _client_directory(d)
        manifest = _manifest(kp, base_url="http://node-x")
        directory.announce(manifest)
        body = test_client.get("/directory/providers").json()
        assert body["providers"] == [manifest]


def test_announce_rejects_non_object_body_with_400() -> None:
    with tempfile.TemporaryDirectory() as d:
        _, test_client = _client_directory(d)
        resp = test_client.post("/directory/announce", json=["not", "a", "manifest"])
        assert resp.status_code == 400


def test_healthz_reports_ok() -> None:
    with tempfile.TemporaryDirectory() as d:
        _, test_client = _client_directory(d)
        assert test_client.get("/healthz").json()["status"] == "ok"
