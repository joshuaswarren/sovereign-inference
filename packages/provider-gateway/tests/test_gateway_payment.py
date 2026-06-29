# SPDX-License-Identifier: AGPL-3.0-or-later
"""Payment-enforcement tests for the provider gateway.

These exercise the HTTP 402 payment wire on ``/v1/chat/completions`` against a
real ``FastAPI`` app driven by ``TestClient``. Payments are built with the real
``sip_pic`` public API (``Issuer``/``Wallet``/``build_pic_payment``/
``build_x402_payment``); the only mocked boundary is the model runtime adapter.

The pricing is configured so a single request has a non-trivial, deterministic
required price, which lets us assert the 402 challenge carries the EXACT price,
that a sufficient PIC voucher payment is accepted (and recorded in the ledger),
that replaying a voucher is blocked as a double-spend, that an under-priced
voucher is rejected, and that an x402 payment >= price is accepted.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import sip_pic
from sip_gateway import MockAdapter, create_app
from sip_protocol import KeyPair, verify_receipt

ALLOWED = ["echo-model"]
# Price input at 1e6 per 1M tokens so price == billed_input words exactly.
INPUT_PER_1M = "1000000"


@pytest.fixture
def provider_keypair() -> KeyPair:
    return KeyPair.generate()


@pytest.fixture
def issuer() -> sip_pic.Issuer:
    return sip_pic.Issuer(KeyPair.generate(), unit="pic")


def make_paid_client(
    provider_keypair: KeyPair,
    issuer: sip_pic.Issuer,
    *,
    spent_set: sip_pic.SpentSet | None = None,
    ledger: sip_pic.Ledger | None = None,
    accept_schemes: list[str] | None = None,
) -> TestClient:
    kwargs: dict[str, object] = {
        "require_payment": True,
        "pic_issuers": [issuer.pubkey],
        "price_units": "pic",
        "input_per_1m": INPUT_PER_1M,
        "output_per_1m": "0",
    }
    if spent_set is not None:
        kwargs["spent_set"] = spent_set
    if ledger is not None:
        kwargs["ledger"] = ledger
    if accept_schemes is not None:
        kwargs["accept_schemes"] = accept_schemes
    app = create_app(
        adapter=MockAdapter(),
        keypair=provider_keypair,
        allowed_models=ALLOWED,
        **kwargs,  # type: ignore[arg-type]
    )
    return TestClient(app)


# Two whitespace-delimited words -> billed_input == 2 -> required price "2".
PROMPT = {"role": "user", "content": "ping pong"}
EXPECTED_PRICE = "2"


# --------------------------------------------------------------------------- #
# Missing payment -> 402 challenge
# --------------------------------------------------------------------------- #
def test_require_payment_without_payment_returns_402_challenge(
    provider_keypair: KeyPair, issuer: sip_pic.Issuer
) -> None:
    client = make_paid_client(provider_keypair, issuer)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "echo-model", "messages": [PROMPT], "max_tokens": 16},
    )
    assert resp.status_code == 402
    body = resp.json()
    assert body["error"] == "payment required"
    challenge = body["sip_payment_required"]
    assert challenge["price_amount"] == EXPECTED_PRICE
    assert challenge["price_units"] == "pic"
    assert challenge["pic_issuers"] == [issuer.pubkey]
    assert set(challenge["accepted_schemes"]) == {"pic", "x402"}


# --------------------------------------------------------------------------- #
# Valid PIC voucher payment -> 200 + receipt + ledger credit
# --------------------------------------------------------------------------- #
def test_valid_pic_payment_serves_and_records_ledger(provider_keypair: KeyPair, issuer: sip_pic.Issuer) -> None:
    ledger = sip_pic.Ledger()
    client = make_paid_client(provider_keypair, issuer, ledger=ledger)

    wallet = sip_pic.Wallet(issuer.issue(EXPECTED_PRICE, count=1))
    payment = sip_pic.build_pic_payment(wallet.select(EXPECTED_PRICE, "pic"))

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "echo-model",
            "messages": [PROMPT],
            "max_tokens": 16,
            "sip_payment": payment,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["choices"][0]["message"]["content"] == "echo: ping pong"
    assert verify_receipt(body["sip_receipt"]).valid is True
    assert ledger.balance(provider_keypair.public_key_str, "pic") == Decimal(EXPECTED_PRICE)


# --------------------------------------------------------------------------- #
# Replaying the same voucher -> 402 (double-spend blocked)
# --------------------------------------------------------------------------- #
def test_replaying_voucher_is_blocked_as_double_spend(provider_keypair: KeyPair, issuer: sip_pic.Issuer) -> None:
    client = make_paid_client(provider_keypair, issuer)

    wallet = sip_pic.Wallet(issuer.issue(EXPECTED_PRICE, count=1))
    payment = sip_pic.build_pic_payment(wallet.select(EXPECTED_PRICE, "pic"))

    first = client.post(
        "/v1/chat/completions",
        json={
            "model": "echo-model",
            "messages": [PROMPT],
            "max_tokens": 16,
            "sip_payment": payment,
        },
    )
    assert first.status_code == 200, first.text

    # Re-presenting the identical voucher must be rejected.
    second = client.post(
        "/v1/chat/completions",
        json={
            "model": "echo-model",
            "messages": [PROMPT],
            "max_tokens": 16,
            "sip_payment": payment,
        },
    )
    assert second.status_code == 402
    assert second.json()["error"] == "payment required"


# --------------------------------------------------------------------------- #
# Under-priced voucher -> 402
# --------------------------------------------------------------------------- #
def test_insufficient_denomination_returns_402(provider_keypair: KeyPair, issuer: sip_pic.Issuer) -> None:
    client = make_paid_client(provider_keypair, issuer)

    # required price is "2"; pay with a single "1" voucher.
    wallet = sip_pic.Wallet(issuer.issue("1", count=1))
    payment = sip_pic.build_pic_payment(wallet.select("1", "pic"))

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "echo-model",
            "messages": [PROMPT],
            "max_tokens": 16,
            "sip_payment": payment,
        },
    )
    assert resp.status_code == 402


# --------------------------------------------------------------------------- #
# x402 payment >= price -> 200
# --------------------------------------------------------------------------- #
def test_x402_payment_at_or_above_price_serves(provider_keypair: KeyPair, issuer: sip_pic.Issuer) -> None:
    ledger = sip_pic.Ledger()
    client = make_paid_client(provider_keypair, issuer, ledger=ledger)

    payer = KeyPair.generate()
    payment = sip_pic.build_x402_payment(
        payer_keypair=payer,
        amount=EXPECTED_PRICE,
        unit="pic",
        provider_pubkey=provider_keypair.public_key_str,
        request_id="req-x402",
    )

    resp = client.post(
        "/v1/chat/completions",
        headers={"x-sip-request-id": "req-x402"},
        json={
            "model": "echo-model",
            "messages": [PROMPT],
            "max_tokens": 16,
            "sip_payment": payment,
        },
    )
    assert resp.status_code == 200, resp.text
    assert verify_receipt(resp.json()["sip_receipt"]).valid is True
    assert ledger.balance(provider_keypair.public_key_str, "pic") == Decimal(EXPECTED_PRICE)


# --------------------------------------------------------------------------- #
# require_payment=False is unchanged (no payment needed)
# --------------------------------------------------------------------------- #
def test_payment_not_required_serves_without_payment(provider_keypair: KeyPair) -> None:
    app = create_app(
        adapter=MockAdapter(),
        keypair=provider_keypair,
        allowed_models=ALLOWED,
        price_units="pic",
        input_per_1m=INPUT_PER_1M,
    )
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "echo-model", "messages": [PROMPT], "max_tokens": 16},
    )
    assert resp.status_code == 200
    assert verify_receipt(resp.json()["sip_receipt"]).valid is True


# --------------------------------------------------------------------------- #
# regression: a runtime error must NOT consume the payment (charge-on-success)
# --------------------------------------------------------------------------- #
class _RaisingAdapter:
    name = "llama.cpp"

    def chat(self, model: str, messages: list[dict[str, str]], *, max_tokens: int = 256, **kwargs: object) -> object:
        raise RuntimeError("model runtime exploded")


def test_runtime_error_does_not_consume_payment(provider_keypair: KeyPair, issuer: sip_pic.Issuer) -> None:
    spent = sip_pic.SpentSet()
    app = create_app(
        adapter=_RaisingAdapter(),
        keypair=provider_keypair,
        allowed_models=ALLOWED,
        require_payment=True,
        pic_issuers=[issuer.pubkey],
        price_units="pic",
        input_per_1m=INPUT_PER_1M,
        output_per_1m="0",
        spent_set=spent,
    )
    client = TestClient(app, raise_server_exceptions=False)
    wallet = sip_pic.Wallet()
    wallet.add(*issuer.issue("5", count=1))
    vouchers = wallet.select(EXPECTED_PRICE, "pic")

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "echo-model",
            "messages": [PROMPT],
            "max_tokens": 16,
            "sip_payment": sip_pic.build_pic_payment(vouchers),
        },
    )
    assert resp.status_code == 502
    # The credit must NOT have been consumed — the request was never served.
    assert spent.is_spent(vouchers[0]["voucher_id"]) is False


# --------------------------------------------------------------------------- #
# regression: the signed receipt attests the price actually charged
# --------------------------------------------------------------------------- #
def test_receipt_price_equals_charged_with_nonzero_output_price(
    provider_keypair: KeyPair, issuer: sip_pic.Issuer
) -> None:
    ledger = sip_pic.Ledger()
    app = create_app(
        adapter=MockAdapter(),
        keypair=provider_keypair,
        allowed_models=ALLOWED,
        require_payment=True,
        pic_issuers=[issuer.pubkey],
        price_units="pic",
        input_per_1m=INPUT_PER_1M,
        output_per_1m="1000000",  # NONZERO output price -> charged != token-based receipt
        ledger=ledger,
    )
    client = TestClient(app)
    wallet = sip_pic.Wallet()
    wallet.add(*issuer.issue("1000", count=1))

    challenge = client.post(
        "/v1/chat/completions",
        json={"model": "echo-model", "messages": [PROMPT], "max_tokens": 16},
    ).json()["sip_payment_required"]
    required = challenge["price_amount"]
    vouchers = wallet.select(required, "pic")

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "echo-model",
            "messages": [PROMPT],
            "max_tokens": 16,
            "sip_payment": sip_pic.build_pic_payment(vouchers),
        },
    )
    assert resp.status_code == 200
    receipt = resp.json()["sip_receipt"]
    # receipt price == the amount actually charged == the ledger credit.
    assert receipt["price_amount"] == required
    assert ledger.balance(provider_keypair.public_key_str, "pic") == Decimal(required)
