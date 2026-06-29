# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the reactive HTTP 402 payment flow in SovereignClient.

The network boundary is the only thing mocked: a fake ``client_factory`` hands
back real ``httpx.Client`` objects wired to ``httpx.MockTransport`` handlers, so
the SDK exercises real request building, real receipt verification (built with
sip_protocol), and a real ``sip_pic`` Issuer/Wallet/payment round-trip.

A paying gateway 402s the first completion with a ``sip_payment_required``
challenge, then serves a verified receipt on the retry that carries a valid
``sip_payment`` in the body.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from sip_pic import Issuer, Wallet, payment_required
from sip_protocol import (
    KeyPair,
    build_receipt,
    hash_response_body,
    model_manifest_hash,
    sign_provider_manifest,
    sign_receipt,
)
from sip_router import ProviderEntry, ProviderRegistry, SovereignClient

MODEL = "qwen-coder-7b"
MODEL_HASH = model_manifest_hash({"schema": "sip-ai.model_manifest.v1", "name": MODEL})
PRICE = "5"
UNIT = "pic"
MESSAGES = [{"role": "user", "content": "hi"}]


def _manifest(kp: KeyPair) -> dict[str, Any]:
    manifest = {
        "schema": "sip-ai.provider_manifest.v1",
        "provider_pubkey": kp.public_key_str,
        "node_type": "sovereign-node",
        "models": [MODEL],
        "runtime_adapters": ["llama.cpp"],
        "pricing": {"unit": "pic", "input_per_1m": 0.0, "output_per_1m": 0.0},
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
        price_units=UNIT,
        price_amount=PRICE,
        privacy_mode="direct",
        started_at=now,
        completed_at=now,
        response_hash=hash_response_body(content),
    )
    return sign_receipt(receipt, kp)


def _completion_body(kp: KeyPair, *, content: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "model": MODEL,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        "sip_receipt": _signed_receipt(kp, content=content),
    }


class PayingGateway:
    """A gateway that requires payment: 402 the first completion, then serve.

    Records every ``sip_payment`` body it receives so tests can assert the
    client actually paid on the retry.
    """

    def __init__(
        self,
        kp: KeyPair,
        *,
        content: str = "paid answer",
        accepted_schemes: list[str] | None = None,
        always_402: bool = False,
        paid_status: int = 200,
    ) -> None:
        self.kp = kp
        self.content = content
        self.accepted_schemes = accepted_schemes if accepted_schemes is not None else ["pic", "x402"]
        self.always_402 = always_402
        self.paid_status = paid_status
        self.manifest = _manifest(kp)
        self.completion_calls = 0
        self.payments_seen: list[dict[str, Any]] = []

    def _challenge(self) -> dict[str, Any]:
        return {
            "error": "payment required",
            "sip_payment_required": payment_required(
                price=PRICE,
                unit=UNIT,
                issuer_pubkeys=[self.kp.public_key_str],
                accept=self.accepted_schemes,
            ),
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/sip/v1/health":
            return httpx.Response(
                200, json={"status": "ok", "provider_pubkey": self.kp.public_key_str, "models": [MODEL]}
            )
        if path == "/v1/chat/completions":
            self.completion_calls += 1
            import json as _json

            body = _json.loads(request.content) if request.content else {}
            payment = body.get("sip_payment")
            if payment is None or self.always_402:
                return httpx.Response(402, json=self._challenge())
            self.payments_seen.append(payment)
            if self.paid_status != 200:
                return httpx.Response(self.paid_status, json={"error": "rejected"})
            return httpx.Response(200, json=_completion_body(self.kp, content=self.content))
        return httpx.Response(404, json={"error": "unknown path"})


class FreeGateway:
    """A gateway that serves without any payment (for failover targets)."""

    def __init__(self, kp: KeyPair, *, content: str = "free answer") -> None:
        self.kp = kp
        self.content = content
        self.manifest = _manifest(kp)
        self.completion_calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/sip/v1/health":
            return httpx.Response(
                200, json={"status": "ok", "provider_pubkey": self.kp.public_key_str, "models": [MODEL]}
            )
        if path == "/v1/chat/completions":
            self.completion_calls += 1
            return httpx.Response(200, json=_completion_body(self.kp, content=self.content))
        return httpx.Response(404, json={"error": "unknown path"})


def _factory(gateways: dict[str, Any]) -> Callable[[str], httpx.Client]:
    def make(base_url: str) -> httpx.Client:
        gateway = gateways[base_url]
        return httpx.Client(base_url=base_url, transport=httpx.MockTransport(gateway.handler))

    return make


def _entry(base_url: str, gateway: Any) -> ProviderEntry:
    return ProviderEntry(base_url=base_url, manifest=gateway.manifest)


def _registry(*entries: ProviderEntry) -> ProviderRegistry:
    registry = ProviderRegistry()
    for entry in entries:
        registry.add(entry)
    return registry


def _funded_wallet(provider_kp: KeyPair, *, denomination: str = "10") -> Wallet:
    """Mint real PIC vouchers from the provider (its own issuer) into a wallet."""
    issuer = Issuer(provider_kp, unit=UNIT)
    wallet = Wallet()
    wallet.add(*issuer.issue(denomination, count=1))
    return wallet


# --- happy path: 402 -> pay -> 200 -----------------------------------------


def test_pic_payment_402_then_paid_retry_succeeds() -> None:
    kp = KeyPair.generate()
    gateway = PayingGateway(kp, content="paid pic answer")
    wallet = _funded_wallet(kp, denomination="10")
    registry = _registry(_entry("http://pay", gateway))
    client = SovereignClient(registry, client_factory=_factory({"http://pay": gateway}))

    result = client.chat(MODEL, MESSAGES, wallet=wallet)

    assert result.content == "paid pic answer"
    assert result.base_url == "http://pay"
    assert result.receipt["request_id"] == "req-1"
    # The provider was hit exactly twice: the 402 challenge then the paid retry.
    assert gateway.completion_calls == 2
    # The retry carried a PIC payment.
    assert len(gateway.payments_seen) == 1
    assert gateway.payments_seen[0]["scheme"] == "pic"
    # Wallet was debited: started with a single 10-pic voucher, spent it on a 5 price.
    assert wallet.balance(UNIT) == Decimal("0")
    assert result.attempts[-1]["outcome"] == "ok"


def test_x402_payment_402_then_paid_retry_succeeds() -> None:
    kp = KeyPair.generate()
    x402_kp = KeyPair.generate()
    gateway = PayingGateway(kp, content="paid x402 answer", accepted_schemes=["x402"])
    registry = _registry(_entry("http://pay", gateway))
    client = SovereignClient(registry, client_factory=_factory({"http://pay": gateway}))

    result = client.chat(MODEL, MESSAGES, x402_keypair=x402_kp)

    assert result.content == "paid x402 answer"
    assert gateway.completion_calls == 2
    assert gateway.payments_seen[0]["scheme"] == "x402"


# --- no payment means available: fail over to a free provider --------------


def test_402_without_wallet_or_x402_fails_over_to_free_provider() -> None:
    pay_kp = KeyPair.generate()
    free_kp = KeyPair.generate()
    paying = PayingGateway(pay_kp, always_402=True)
    free = FreeGateway(free_kp, content="served free")
    registry = _registry(_entry("http://pay", paying), _entry("http://free", free))
    client = SovereignClient(registry, client_factory=_factory({"http://pay": paying, "http://free": free}))

    # No wallet, no x402 keypair: the 402 provider cannot be paid, fail over.
    result = client.chat(MODEL, MESSAGES)

    assert result.base_url == "http://free"
    assert result.content == "served free"
    assert result.attempts[0]["base_url"] == "http://pay"
    assert result.attempts[0]["outcome"] == "payment_required"
    # The paying provider was only asked once (the 402), never retried.
    assert paying.completion_calls == 1


# --- insufficient funds: fail over, wallet keeps every voucher -------------


def test_insufficient_wallet_fails_over_and_keeps_vouchers() -> None:
    pay_kp = KeyPair.generate()
    free_kp = KeyPair.generate()
    paying = PayingGateway(pay_kp, always_402=True)
    free = FreeGateway(free_kp, content="free fallback")
    # Wallet holds only 1 pic but the price is 5 -> InsufficientFunds on select.
    wallet = _funded_wallet(pay_kp, denomination="1")
    before = wallet.balance(UNIT)
    registry = _registry(_entry("http://pay", paying), _entry("http://free", free))
    client = SovereignClient(registry, client_factory=_factory({"http://pay": paying, "http://free": free}))

    result = client.chat(MODEL, MESSAGES, wallet=wallet)

    assert result.base_url == "http://free"
    assert result.content == "free fallback"
    assert result.attempts[0]["outcome"] == "insufficient_funds"
    # No vouchers were lost: the wallet still holds exactly what it started with.
    assert wallet.balance(UNIT) == before == Decimal("1")
    assert len(wallet.vouchers) == 1
    # The paying provider was never retried (no payment was attempted).
    assert paying.completion_calls == 1


# --- paid retry still fails: vouchers returned to wallet, fail over --------


def test_paid_retry_rejected_returns_vouchers_and_fails_over() -> None:
    pay_kp = KeyPair.generate()
    free_kp = KeyPair.generate()
    # The provider 402s, accepts the payment on retry, but then 500s anyway.
    paying = PayingGateway(pay_kp, paid_status=500)
    free = FreeGateway(free_kp, content="free after rejection")
    wallet = _funded_wallet(pay_kp, denomination="10")
    before = wallet.balance(UNIT)
    registry = _registry(_entry("http://pay", paying), _entry("http://free", free))
    client = SovereignClient(registry, client_factory=_factory({"http://pay": paying, "http://free": free}))

    result = client.chat(MODEL, MESSAGES, wallet=wallet)

    assert result.base_url == "http://free"
    assert result.content == "free after rejection"
    assert result.attempts[0]["outcome"] == "payment_rejected"
    # The vouchers selected for the rejected batch were returned to the wallet.
    assert wallet.balance(UNIT) == before == Decimal("10")
    assert len(wallet.vouchers) == 1
    # The provider saw the payment but the paid retry was rejected.
    assert paying.completion_calls == 2
    assert len(paying.payments_seen) == 1


# --- regression: no payment kwargs preserves existing behavior -------------


def test_no_payment_kwargs_does_not_send_payment_on_normal_provider() -> None:
    kp = KeyPair.generate()
    free = FreeGateway(kp, content="plain")
    registry = _registry(_entry("http://p", free))
    client = SovereignClient(registry, client_factory=_factory({"http://p": free}))

    result = client.chat(MODEL, MESSAGES)

    assert result.content == "plain"
    # Exactly one completion call, no challenge/retry dance.
    assert free.completion_calls == 1
