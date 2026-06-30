# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the SIP-AI privacy relay (forward + untrusted-for-integrity)."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi.testclient import TestClient

from sip_gateway import MockAdapter, create_app
from sip_protocol import (
    KeyPair,
    build_provider_manifest,
    sign_provider_manifest,
    verify_receipt,
)
from sip_relay import create_relay_app, relay_chat

MODEL = "qwen-coder-7b"
NODE_URL = "http://node"


def _provider() -> tuple[Any, dict[str, Any]]:
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


def _relay_client(node_app: Any) -> TestClient:
    def client_factory(_base_url: str) -> Any:
        return TestClient(node_app)

    return TestClient(create_relay_app(client_factory=client_factory))


def _completion() -> dict[str, Any]:
    return {"model": MODEL, "messages": [{"role": "user", "content": "hello"}]}


# -- forwarding -----------------------------------------------------------------


def test_relay_forwards_and_returns_a_verified_receipt() -> None:
    node_app, manifest = _provider()
    relay = _relay_client(node_app)
    result = relay_chat(relay, target={"base_url": NODE_URL, "manifest": manifest}, completion=_completion())
    assert "echo: hello" in result.content
    assert result.verified is True
    assert verify_receipt(result.receipt).valid


def test_relay_rejects_forged_target_manifest() -> None:
    node_app, manifest = _provider()
    forged = dict(manifest)
    forged["models"] = ["evil"]  # breaks the signature
    relay = _relay_client(node_app)
    resp = relay.post(
        "/sip/v1/relay", json={"target": {"base_url": NODE_URL, "manifest": forged}, "completion": _completion()}
    )
    assert resp.status_code == 400


def test_relay_routes_only_to_signed_manifest_uri() -> None:
    node_app, manifest = _provider()
    relay = _relay_client(node_app)
    # base_url differs from the signed manifest_uri -> the relay must refuse
    resp = relay.post(
        "/sip/v1/relay",
        json={"target": {"base_url": "http://attacker", "manifest": manifest}, "completion": _completion()},
    )
    assert resp.status_code == 400


def test_relay_healthz() -> None:
    node_app, _ = _provider()
    assert _relay_client(node_app).get("/healthz").json()["status"] == "ok"


# -- integrity (relay is untrusted) ---------------------------------------------


def test_relay_chat_detects_tampered_content() -> None:
    # Obtain a genuine receipt, then simulate a relay that alters the answer.
    node_app, manifest = _provider()
    good = relay_chat(
        _relay_client(node_app), target={"base_url": NODE_URL, "manifest": manifest}, completion=_completion()
    )

    def tampering_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "TAMPERED ANSWER"}}],
                "sip_receipt": good.receipt,  # the real receipt, but for the original answer
            },
        )

    malicious = httpx.Client(transport=httpx.MockTransport(tampering_handler), base_url="http://relay")
    result = relay_chat(malicious, target={"base_url": NODE_URL, "manifest": manifest}, completion=_completion())
    assert result.content == "TAMPERED ANSWER"
    assert result.verified is False  # response_hash no longer matches the content


def test_relay_chat_rejects_receipt_for_a_different_request() -> None:
    # A relay substitutes a genuine (content, receipt) pair produced for a
    # DIFFERENT prompt. The receipt's request_hash binds it to prompt A, so the
    # client detects the substitution when it asked for prompt B.
    node_app, manifest = _provider()
    target = {"base_url": NODE_URL, "manifest": manifest}
    a = relay_chat(
        _relay_client(node_app),
        target=target,
        completion={"model": MODEL, "messages": [{"role": "user", "content": "prompt A"}]},
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"index": 0, "message": {"role": "assistant", "content": a.content}}],
                "sip_receipt": a.receipt,
            },
        )

    malicious = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://relay")
    result = relay_chat(
        malicious, target=target, completion={"model": MODEL, "messages": [{"role": "user", "content": "prompt B"}]}
    )
    assert result.content == a.content
    assert result.verified is False  # request_hash is for prompt A, not B


def test_relay_refuses_ssrf_to_link_local_metadata_address() -> None:
    kp = KeyPair.generate()
    evil = sign_provider_manifest(
        build_provider_manifest(
            provider_pubkey=kp.public_key_str,
            models=[MODEL],
            runtime_adapters=["x"],
            pricing_unit="test",
            published_at="2026-06-30T00:00:00Z",
            manifest_uri="http://169.254.169.254/latest/meta-data",
        ),
        kp,
    )
    node_app, _ = _provider()
    resp = _relay_client(node_app).post(
        "/sip/v1/relay",
        json={
            "target": {"base_url": "http://169.254.169.254/latest/meta-data", "manifest": evil},
            "completion": _completion(),
        },
    )
    assert resp.status_code == 400  # SSRF to a link-local/metadata address is refused


def test_relay_chat_tolerates_non_dict_receipt() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "x"}}],
                "sip_receipt": "not-an-object",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://relay")
    result = relay_chat(client, target={"base_url": NODE_URL, "manifest": {}}, completion=_completion())
    assert result.verified is False  # must not raise on a non-dict receipt
