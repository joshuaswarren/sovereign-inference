# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for SovereignClient: happy path, health/quote checks, and failover.

The network boundary is the only thing mocked: a fake client_factory hands back
real ``httpx.Client`` objects wired to ``httpx.MockTransport`` handlers, one per
base_url, so the SDK exercises real request building and real receipt
verification (built with sip_protocol).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from sip_protocol import (
    KeyPair,
    build_quote,
    build_receipt,
    hash_response_body,
    model_manifest_hash,
    sign_provider_manifest,
    sign_quote,
    sign_receipt,
)
from sip_router import NoProviderAvailable, ProviderEntry, ProviderRegistry, SovereignClient

MODEL = "qwen-coder-7b"
MODEL_HASH = model_manifest_hash({"schema": "sip-ai.model_manifest.v1", "name": MODEL})


def _manifest(kp: KeyPair, *, models: list[str] | None = None) -> dict[str, Any]:
    manifest = {
        "schema": "sip-ai.provider_manifest.v1",
        "provider_pubkey": kp.public_key_str,
        "node_type": "sovereign-node",
        "models": models if models is not None else [MODEL],
        "runtime_adapters": ["llama.cpp"],
        "pricing": {"unit": "test", "input_per_1m": 0.0, "output_per_1m": 0.0},
        "max_context": 8192,
        "logging_policy": "no_prompt_logging",
        "privacy_modes": ["direct"],
        "published_at": "2026-06-29T00:00:00Z",
    }
    return sign_provider_manifest(manifest, kp)


def _signed_receipt(kp: KeyPair, *, content: str, request_id: str = "req-1") -> dict[str, Any]:
    now = datetime.now(UTC)
    receipt = build_receipt(
        request_id=request_id,
        provider_pubkey=kp.public_key_str,
        model_manifest_hash=MODEL_HASH,
        model_alias=MODEL,
        runtime="llama.cpp",
        input_tokens=5,
        output_tokens=len(content.split()),
        price_units="test",
        price_amount="0",
        privacy_mode="direct",
        started_at=now,
        completed_at=now,
        response_hash=hash_response_body(content),
    )
    return sign_receipt(receipt, kp)


def _signed_quote(kp: KeyPair, *, request_id: str = "req-1") -> dict[str, Any]:
    now = datetime.now(UTC)
    quote = build_quote(
        request_id=request_id,
        provider_pubkey=kp.public_key_str,
        model_alias=MODEL,
        price_units="test",
        input_per_1m="0",
        output_per_1m="0",
        max_output_tokens=256,
        max_price="0",
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        privacy_mode="direct",
    )
    return sign_quote(quote, kp)


def _completion_body(kp: KeyPair, *, content: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "model": MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        "sip_receipt": _signed_receipt(kp, content=content),
    }


class FakeGateway:
    """A scriptable in-memory gateway addressable by base_url via MockTransport."""

    def __init__(
        self,
        kp: KeyPair,
        *,
        content: str = "hello world",
        health_ok: bool = True,
        completion_status: int = 200,
        raise_transport_error: bool = False,
        receipt_override: dict[str, Any] | None = None,
        omit_receipt: bool = False,
        models: list[str] | None = None,
    ) -> None:
        self.kp = kp
        self.content = content
        self.health_ok = health_ok
        self.completion_status = completion_status
        self.raise_transport_error = raise_transport_error
        self.receipt_override = receipt_override
        self.omit_receipt = omit_receipt
        self.models = models if models is not None else [MODEL]
        self.completion_calls = 0
        self.manifest = _manifest(kp, models=self.models)

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/sip/v1/health":
            status = "ok" if self.health_ok else "degraded"
            return httpx.Response(
                200,
                json={
                    "status": status,
                    "provider_pubkey": self.kp.public_key_str,
                    "models": self.models,
                },
            )
        if path == "/sip/v1/quote":
            return httpx.Response(200, json=_signed_quote(self.kp))
        if path == "/v1/chat/completions":
            self.completion_calls += 1
            if self.raise_transport_error:
                raise httpx.ConnectError("boom", request=request)
            if self.completion_status != 200:
                return httpx.Response(self.completion_status, json={"error": "nope"})
            body = _completion_body(self.kp, content=self.content)
            if self.omit_receipt:
                del body["sip_receipt"]
            elif self.receipt_override is not None:
                body["sip_receipt"] = self.receipt_override
            return httpx.Response(200, json=body)
        return httpx.Response(404, json={"error": "unknown path"})


def _factory(gateways: dict[str, FakeGateway]) -> Callable[[str], httpx.Client]:
    def make(base_url: str) -> httpx.Client:
        gateway = gateways[base_url]
        return httpx.Client(base_url=base_url, transport=httpx.MockTransport(gateway.handler))

    return make


def _entry(base_url: str, gateway: FakeGateway) -> ProviderEntry:
    return ProviderEntry(base_url=base_url, manifest=gateway.manifest)


def _registry(*entries: ProviderEntry) -> ProviderRegistry:
    registry = ProviderRegistry()
    for entry in entries:
        registry.add(entry)
    return registry


MESSAGES = [{"role": "user", "content": "hi"}]


def test_happy_path_returns_verified_receipt() -> None:
    kp = KeyPair.generate()
    gateway = FakeGateway(kp, content="the answer is 42")
    registry = _registry(_entry("http://provider", gateway))
    client = SovereignClient(registry, token="secret", client_factory=_factory({"http://provider": gateway}))

    result = client.chat(MODEL, MESSAGES)

    assert result.content == "the answer is 42"
    assert result.provider_pubkey == kp.public_key_str
    assert result.base_url == "http://provider"
    assert result.receipt["request_id"] == "req-1"
    assert len(result.attempts) == 1
    assert result.attempts[0] == {"base_url": "http://provider", "outcome": "ok"}


def test_authorization_and_sip_headers_are_sent() -> None:
    kp = KeyPair.generate()
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sip/v1/health":
            return httpx.Response(
                200,
                json={"status": "ok", "provider_pubkey": kp.public_key_str, "models": [MODEL]},
            )
        captured["auth"] = request.headers.get("authorization")
        captured["request_id"] = request.headers.get("x-sip-request-id")
        captured["privacy"] = request.headers.get("x-sip-privacy-mode")
        return httpx.Response(200, json=_completion_body(kp, content="ok"))

    def factory(base_url: str) -> httpx.Client:
        return httpx.Client(base_url=base_url, transport=httpx.MockTransport(handler))

    registry = _registry(ProviderEntry(base_url="http://p", manifest=_manifest(kp)))
    client = SovereignClient(
        registry,
        token="topsecret",
        client_factory=factory,
        request_id_factory=lambda: "fixed-id",
    )
    client.chat(MODEL, MESSAGES, privacy_mode="relay")

    assert captured["auth"] == "Bearer topsecret"
    assert captured["request_id"] == "fixed-id"
    assert captured["privacy"] == "relay"


def test_failover_from_503_to_healthy_provider() -> None:
    bad_kp = KeyPair.generate()
    good_kp = KeyPair.generate()
    bad = FakeGateway(bad_kp, completion_status=503)
    good = FakeGateway(good_kp, content="served by B")
    # Rank the failing provider first by making it look cheaper/faster is unnecessary;
    # both score equally, so insertion order (bad, good) is preserved.
    registry = _registry(_entry("http://bad", bad), _entry("http://good", good))
    client = SovereignClient(
        registry,
        client_factory=_factory({"http://bad": bad, "http://good": good}),
    )

    result = client.chat(MODEL, MESSAGES)

    assert result.content == "served by B"
    assert result.base_url == "http://good"
    assert result.provider_pubkey == good_kp.public_key_str
    assert [a["base_url"] for a in result.attempts] == ["http://bad", "http://good"]
    assert result.attempts[0]["outcome"] != "ok"
    assert result.attempts[1]["outcome"] == "ok"


def test_failover_on_transport_error() -> None:
    bad_kp = KeyPair.generate()
    good_kp = KeyPair.generate()
    bad = FakeGateway(bad_kp, raise_transport_error=True)
    good = FakeGateway(good_kp, content="recovered")
    registry = _registry(_entry("http://bad", bad), _entry("http://good", good))
    client = SovereignClient(
        registry,
        client_factory=_factory({"http://bad": bad, "http://good": good}),
    )

    result = client.chat(MODEL, MESSAGES)
    assert result.base_url == "http://good"
    assert result.content == "recovered"


def test_failover_skips_unhealthy_provider() -> None:
    bad_kp = KeyPair.generate()
    good_kp = KeyPair.generate()
    bad = FakeGateway(bad_kp, health_ok=False)
    good = FakeGateway(good_kp, content="healthy one")
    registry = _registry(_entry("http://bad", bad), _entry("http://good", good))
    client = SovereignClient(
        registry,
        client_factory=_factory({"http://bad": bad, "http://good": good}),
    )

    result = client.chat(MODEL, MESSAGES)
    assert result.base_url == "http://good"
    # The unhealthy provider must never have been asked to serve a completion.
    assert bad.completion_calls == 0


def test_failover_on_bad_receipt_signature() -> None:
    bad_kp = KeyPair.generate()
    good_kp = KeyPair.generate()
    # bad provider returns a receipt signed by a DIFFERENT key than its manifest pubkey.
    impostor = KeyPair.generate()
    forged_receipt = _signed_receipt(impostor, content="hello world")
    bad = FakeGateway(bad_kp, receipt_override=forged_receipt)
    good = FakeGateway(good_kp, content="trustworthy")
    registry = _registry(_entry("http://bad", bad), _entry("http://good", good))
    client = SovereignClient(
        registry,
        client_factory=_factory({"http://bad": bad, "http://good": good}),
    )

    result = client.chat(MODEL, MESSAGES, verify_receipts=True)
    assert result.base_url == "http://good"
    assert result.content == "trustworthy"


def test_failover_on_missing_receipt() -> None:
    bad_kp = KeyPair.generate()
    good_kp = KeyPair.generate()
    bad = FakeGateway(bad_kp, omit_receipt=True)
    good = FakeGateway(good_kp, content="has receipt")
    registry = _registry(_entry("http://bad", bad), _entry("http://good", good))
    client = SovereignClient(
        registry,
        client_factory=_factory({"http://bad": bad, "http://good": good}),
    )
    result = client.chat(MODEL, MESSAGES, verify_receipts=True)
    assert result.base_url == "http://good"


def test_bad_receipt_accepted_when_verification_disabled() -> None:
    kp = KeyPair.generate()
    impostor = KeyPair.generate()
    forged = _signed_receipt(impostor, content="hello world")
    gateway = FakeGateway(kp, receipt_override=forged)
    registry = _registry(_entry("http://p", gateway))
    client = SovereignClient(registry, client_factory=_factory({"http://p": gateway}))

    result = client.chat(MODEL, MESSAGES, verify_receipts=False)
    assert result.base_url == "http://p"


def test_get_quote_attaches_verified_quote() -> None:
    kp = KeyPair.generate()
    gateway = FakeGateway(kp, content="quoted")
    registry = _registry(_entry("http://p", gateway))
    client = SovereignClient(registry, token="t", client_factory=_factory({"http://p": gateway}))

    result = client.chat(MODEL, MESSAGES, get_quote=True)
    assert result.quote is not None
    assert result.quote["model_alias"] == MODEL
    assert result.content == "quoted"


def test_no_quote_when_not_requested() -> None:
    kp = KeyPair.generate()
    gateway = FakeGateway(kp, content="x")
    registry = _registry(_entry("http://p", gateway))
    client = SovereignClient(registry, client_factory=_factory({"http://p": gateway}))
    result = client.chat(MODEL, MESSAGES, get_quote=False)
    assert result.quote is None


def test_all_providers_fail_raises_no_provider_available() -> None:
    a_kp = KeyPair.generate()
    b_kp = KeyPair.generate()
    a = FakeGateway(a_kp, completion_status=500)
    b = FakeGateway(b_kp, completion_status=429)
    registry = _registry(_entry("http://a", a), _entry("http://b", b))
    client = SovereignClient(registry, client_factory=_factory({"http://a": a, "http://b": b}))

    with pytest.raises(NoProviderAvailable) as excinfo:
        client.chat(MODEL, MESSAGES)

    attempts = excinfo.value.attempts
    assert {a["base_url"] for a in attempts} == {"http://a", "http://b"}


def test_no_candidates_raises_no_provider_available() -> None:
    registry = ProviderRegistry()
    client = SovereignClient(registry, client_factory=_factory({}))
    with pytest.raises(NoProviderAvailable):
        client.chat("absent-model", MESSAGES)


def test_max_providers_limits_attempts() -> None:
    a_kp = KeyPair.generate()
    b_kp = KeyPair.generate()
    a = FakeGateway(a_kp, completion_status=500)
    b = FakeGateway(b_kp, completion_status=500)
    registry = _registry(_entry("http://a", a), _entry("http://b", b))
    client = SovereignClient(registry, client_factory=_factory({"http://a": a, "http://b": b}))

    with pytest.raises(NoProviderAvailable) as excinfo:
        client.chat(MODEL, MESSAGES, max_providers=1)

    assert len(excinfo.value.attempts) == 1
