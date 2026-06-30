# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the unified desktop app server (proxy + node status + onboarding admin)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from sip_gateway import MockAdapter
from sip_openai_proxy.config import load_config
from sip_openai_proxy.local_use import front_local_model
from sip_openai_proxy.server import create_app_server
from sip_protocol import KeyPair, build_provider_manifest, sign_provider_manifest

MODEL = "qwen-coder-7b"
TOKEN = "tok-secret"


def _signed_manifest(uri: str = "https://prov.example") -> dict[str, Any]:
    kp = KeyPair.generate()
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


def _fake_scan() -> Any:
    from sin_node.models import CPUInfo, HardwareProfile

    return HardwareProfile(
        os="testos",
        os_version="1.0",
        arch="arm64",
        cpu=CPUInfo(arch="arm64", model="TestCPU"),
        ram_total_gb=16.0,
        ram_available_gb=8.0,
        disk_free_gb=100.0,
    )


def _server(tmp_path: Path, **kw: Any) -> TestClient:
    app = create_app_server(
        tmp_path,
        admin_token=TOKEN,
        scan=_fake_scan,
        detect=lambda: [],
        start_local=lambda runtime, model: front_local_model(model, adapter=MockAdapter()),
        **kw,
    )
    return TestClient(app)


def _auth() -> dict[str, str]:
    return {"X-Sovereign-Token": TOKEN}


# -- onboarding gate + auth -----------------------------------------------------


def test_fresh_config_reports_not_onboarded_and_no_models(tmp_path: Path) -> None:
    client = _server(tmp_path)
    body = client.get("/api/config", headers=_auth()).json()
    assert body["onboarding_complete"] is False
    assert body["providers"] == []
    assert body["models"] == []
    assert body["local_use"] is None
    # no secrets leak through the state endpoint
    assert "token" not in body
    assert "api_key" not in body


def test_mutations_require_the_admin_token(tmp_path: Path) -> None:
    client = _server(tmp_path)
    # missing token -> 401
    assert client.post("/api/providers", json={"manifest": _signed_manifest()}).status_code == 401
    assert client.post("/api/onboarding/complete").status_code == 401


def test_healthz_is_open(tmp_path: Path) -> None:
    client = _server(tmp_path)
    assert client.get("/healthz").status_code == 200


# -- add a network provider -> live models --------------------------------------


def test_add_provider_updates_models_and_persists(tmp_path: Path) -> None:
    client = _server(tmp_path)
    manifest = _signed_manifest("https://prov.example")
    resp = client.post("/api/providers", json={"manifest": manifest}, headers=_auth())
    assert resp.status_code == 200
    # the model is now advertised on the OpenAI surface, live (no restart)
    models = [m["id"] for m in client.get("/v1/models").json()["data"]]
    assert MODEL in models
    # config persisted to disk
    saved = load_config(tmp_path)
    assert saved.providers[0].manifest["provider_pubkey"] == manifest["provider_pubkey"]


def test_add_forged_provider_is_rejected(tmp_path: Path) -> None:
    client = _server(tmp_path)
    forged = _signed_manifest("https://prov.example")
    forged["models"] = ["tampered"]  # invalidates the signature
    resp = client.post("/api/providers", json={"manifest": forged}, headers=_auth())
    assert resp.status_code == 400
    assert client.get("/v1/models").json()["data"] == []


def test_add_provider_with_mismatched_base_url_is_rejected(tmp_path: Path) -> None:
    client = _server(tmp_path)
    manifest = _signed_manifest("https://prov.example")
    resp = client.post(
        "/api/providers",
        json={"manifest": manifest, "base_url": "https://attacker.example"},
        headers=_auth(),
    )
    assert resp.status_code == 400


# -- local-use -> verified in-process chat --------------------------------------


def test_local_use_serves_a_verified_chat_and_persists(tmp_path: Path) -> None:
    client = _server(tmp_path)
    resp = client.post("/api/local-use", json={"runtime": "ollama", "model": MODEL}, headers=_auth())
    assert resp.status_code == 200
    assert MODEL in [m["id"] for m in client.get("/v1/models").json()["data"]]

    chat = client.post(
        "/v1/chat/completions",
        json={"model": MODEL, "messages": [{"role": "user", "content": "hello"}]},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert "echo: hello" in body["choices"][0]["message"]["content"]
    assert body["sip"]["receipt_verified"] is True

    # local-use is remembered for restore-on-boot
    assert load_config(tmp_path).local_use is not None
    assert client.get("/api/config", headers=_auth()).json()["local_use"]["model"] == MODEL


def test_local_use_restored_on_restart(tmp_path: Path) -> None:
    first = _server(tmp_path)
    first.post("/api/local-use", json={"runtime": "ollama", "model": MODEL}, headers=_auth())
    # a brand-new server over the same config dir re-fronts the local model
    second = _server(tmp_path)
    assert MODEL in [m["id"] for m in second.get("/v1/models").json()["data"]]


# -- onboarding completion + node status ----------------------------------------


def test_onboarding_complete_persists(tmp_path: Path) -> None:
    client = _server(tmp_path)
    assert client.post("/api/onboarding/complete", headers=_auth()).status_code == 200
    assert client.get("/api/config", headers=_auth()).json()["onboarding_complete"] is True
    assert load_config(tmp_path).onboarding_complete is True


def test_status_and_scan_endpoints_work(tmp_path: Path) -> None:
    client = _server(tmp_path)
    assert client.get("/api/status", headers=_auth()).json()["version"]
    assert client.get("/api/scan", headers=_auth()).json()["os"] == "testos"


# -- directory mutation efficiency / idempotency (review fixes) ------------------


class _CountingDirectory:
    """A directory whose discover() returns nothing but counts how often it ran."""

    def __init__(self, counter: dict[str, int]) -> None:
        self._counter = counter

    def discover(self, *, model: str | None = None) -> list[Any]:
        self._counter["n"] += 1
        return []


def test_adding_the_same_directory_twice_does_not_refetch(tmp_path: Path) -> None:
    counter = {"n": 0}
    client = _server(tmp_path, directory_for=lambda _spec: _CountingDirectory(counter))
    client.post("/api/directory", json={"spec": "https://dir.example"}, headers=_auth())
    after_first = counter["n"]
    # re-adding the same spec is a no-op: no persist, no rebuild, no re-fetch
    body = client.post("/api/directory", json={"spec": "https://dir.example"}, headers=_auth()).json()
    assert counter["n"] == after_first
    assert body["directories"].count("https://dir.example") == 1


def test_removing_an_unknown_directory_does_not_refetch(tmp_path: Path) -> None:
    counter = {"n": 0}
    client = _server(tmp_path, directory_for=lambda _spec: _CountingDirectory(counter))
    client.post("/api/directory", json={"spec": "https://dir.example"}, headers=_auth())
    after_add = counter["n"]
    # deleting a spec that isn't configured changes nothing and doesn't re-fetch
    resp = client.request("DELETE", "/api/directory", params={"spec": "https://other.example"}, headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["directories"] == ["https://dir.example"]
    assert counter["n"] == after_add


def test_cors_regex_accepts_app_origins_and_rejects_bad_ports() -> None:
    import re

    from sip_openai_proxy.server import _ALLOW_ORIGIN_REGEX

    assert re.match(_ALLOW_ORIGIN_REGEX, "http://127.0.0.1:11435")
    assert re.match(_ALLOW_ORIGIN_REGEX, "http://localhost")
    assert re.match(_ALLOW_ORIGIN_REGEX, "tauri://localhost")
    assert re.match(_ALLOW_ORIGIN_REGEX, "https://tauri.localhost")
    assert not re.match(_ALLOW_ORIGIN_REGEX, "http://127.0.0.1:99999")  # port > 65535
    assert not re.match(_ALLOW_ORIGIN_REGEX, "http://evil.example")
