# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the local OpenAI-compatible proxy."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from sip_gateway import MockAdapter, create_app
from sip_openai_proxy import build_backend, create_proxy_app
from sip_policy import Policy
from sip_protocol import KeyPair, build_provider_manifest, sign_provider_manifest
from sip_router import ProviderEntry, ProviderRegistry

MODEL = "qwen-coder-7b"
NODE_URL = "http://node"


def _node() -> tuple[Any, dict[str, Any]]:
    kp = KeyPair.generate()
    manifest = sign_provider_manifest(
        build_provider_manifest(
            provider_pubkey=kp.public_key_str,
            models=[MODEL],
            runtime_adapters=["llama.cpp"],
            pricing_unit="test",
            published_at="2026-06-30T00:00:00Z",
            manifest_uri=NODE_URL,
        ),
        kp,
    )
    app = create_app(adapter=MockAdapter(), keypair=kp, allowed_models=[MODEL], token=None, provider_manifest=manifest)
    return app, manifest


def _proxy(*, policy: Policy | None = None, api_key: str | None = None) -> tuple[TestClient, dict[str, Any]]:
    node_app, manifest = _node()
    registry = ProviderRegistry()
    registry.add(ProviderEntry(base_url=NODE_URL, manifest=manifest))
    node_client = TestClient(node_app)
    backend = build_backend(registry, policy=policy, client_factory=lambda _base: node_client)
    return TestClient(create_proxy_app(backend, api_key=api_key)), manifest


# -- /v1/models -----------------------------------------------------------------


def test_models_endpoint_lists_available_models() -> None:
    proxy, _ = _proxy()
    body = proxy.get("/v1/models").json()
    assert body["object"] == "list"
    assert [m["id"] for m in body["data"]] == [MODEL]
    assert body["data"][0]["owned_by"] == "sovereign-inference"


# -- /v1/chat/completions (non-streaming) ---------------------------------------


def test_chat_completions_routes_and_returns_openai_shape() -> None:
    proxy, _ = _proxy()
    resp = proxy.post(
        "/v1/chat/completions",
        json={"model": MODEL, "messages": [{"role": "user", "content": "hello"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == MODEL
    assert "echo: hello" in body["choices"][0]["message"]["content"]
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["usage"]["total_tokens"] >= 1
    # a verified signed receipt rides along under a sip extension
    assert body["sip"]["receipt_verified"] is True
    assert body["sip"]["base_url"] == NODE_URL


def test_chat_completions_ignores_unknown_openai_fields() -> None:
    proxy, _ = _proxy()
    resp = proxy.post(
        "/v1/chat/completions",
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.7,
            "top_p": 0.9,
            "stop": ["\n"],
        },
    )
    assert resp.status_code == 200


def test_chat_completions_unknown_model_errors() -> None:
    proxy, _ = _proxy()
    resp = proxy.post(
        "/v1/chat/completions",
        json={"model": "no-such-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 502
    assert resp.json()["error"]["type"] == "no_provider"


# -- streaming ------------------------------------------------------------------


def test_chat_completions_streaming_emits_sse_then_done() -> None:
    proxy, _ = _proxy()
    with proxy.stream(
        "POST",
        "/v1/chat/completions",
        json={"model": MODEL, "messages": [{"role": "user", "content": "hello"}], "stream": True},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        raw = "".join(resp.iter_text())
    assert "chat.completion.chunk" in raw
    chunks = [line[len("data: ") :] for line in raw.splitlines() if line.startswith("data: ")]
    assert chunks[-1] == "[DONE]"
    # the assembled deltas reproduce the answer
    content = "".join(json.loads(c)["choices"][0]["delta"].get("content", "") for c in chunks[:-1])
    assert "echo: hello" in content


# -- auth -----------------------------------------------------------------------


def test_api_key_required_when_configured() -> None:
    proxy, _ = _proxy(api_key="sk-secret")
    body = {"model": MODEL, "messages": [{"role": "user", "content": "hi"}]}
    assert proxy.post("/v1/chat/completions", json=body).status_code == 401
    ok = proxy.post("/v1/chat/completions", json=body, headers={"Authorization": "Bearer sk-secret"})
    assert ok.status_code == 200


# -- policy integration ---------------------------------------------------------


def test_policy_excludes_denied_provider_from_models_and_routing() -> None:
    node_app, manifest = _node()
    registry = ProviderRegistry()
    registry.add(ProviderEntry(base_url=NODE_URL, manifest=manifest))
    policy = Policy(deny_providers=(manifest["provider_pubkey"],))
    backend = build_backend(registry, policy=policy, client_factory=lambda _b: TestClient(node_app))
    proxy = TestClient(create_proxy_app(backend))
    assert proxy.get("/v1/models").json()["data"] == []  # denied -> no models
    resp = proxy.post("/v1/chat/completions", json={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 502  # nothing to route to


# -- OpenAI compatibility hardening (review fixes) ------------------------------


def test_chat_accepts_null_and_array_part_content() -> None:
    proxy, _ = _proxy()
    resp = proxy.post(
        "/v1/chat/completions",
        json={
            "model": MODEL,
            "messages": [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": None, "tool_calls": []},
                {"role": "user", "content": [{"type": "text", "text": "again"}]},
            ],
        },
    )
    assert resp.status_code == 200  # tool-call (null) + array-of-parts content tolerated


def test_validation_error_uses_openai_envelope() -> None:
    proxy, _ = _proxy()
    resp = proxy.post("/v1/chat/completions", json={"model": MODEL})  # missing messages
    assert resp.status_code == 400
    assert resp.json()["error"]["type"] == "invalid_request_error"


def test_negative_max_tokens_is_rejected() -> None:
    proxy, _ = _proxy()
    resp = proxy.post(
        "/v1/chat/completions",
        json={"model": MODEL, "messages": [{"role": "user", "content": "hi"}], "max_tokens": -5},
    )
    assert resp.status_code == 400


def test_non_ascii_api_key_does_not_500() -> None:
    # A raw client can put high latin-1 bytes in the header; the server must fail
    # closed (401), not raise TypeError from hmac.compare_digest on a non-ASCII str.
    proxy, _ = _proxy(api_key="sk-secret")
    resp = proxy.post(
        "/v1/chat/completions",
        json={"model": MODEL, "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": b"Bearer \xef\xbf-not-the-key"},
    )
    assert resp.status_code == 401  # rejected cleanly, not a 500
