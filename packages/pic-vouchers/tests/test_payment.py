# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for payment building, redemption, and the 402 challenge."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from sip_pic.issuer import Issuer
from sip_pic.payment import (
    RedeemResult,
    build_pic_payment,
    payment_required,
    redeem_payment,
)
from sip_pic.spentset import SpentSet
from sip_pic.x402 import build_x402_payment
from sip_protocol import KeyPair

FIXED_NOW = datetime(2026, 6, 29, 12, 0, 0, tzinfo=UTC)


def _now() -> datetime:
    return FIXED_NOW


@pytest.fixture
def issuer() -> Issuer:
    return Issuer(KeyPair.generate())


def test_build_pic_payment_shape(issuer: Issuer) -> None:
    vouchers = issuer.issue("1.00", count=2, now=_now)
    payment = build_pic_payment(vouchers)
    assert payment == {"scheme": "pic", "vouchers": vouchers}


def test_x402_payment_is_single_use() -> None:
    # Regression: a captured x402 payment must not be replayable for free service.
    payer = KeyPair.generate()
    prov = KeyPair.generate()
    payment = build_x402_payment(
        payer_keypair=payer, amount="1.0", unit="pic", now=_now, provider_pubkey=prov.public_key_str, request_id="req-1"
    )
    spent = SpentSet()
    first = redeem_payment(
        payment,
        price="1.0",
        unit="pic",
        issuer_pubkeys=[],
        spent_set=spent,
        now=FIXED_NOW,
        provider_pubkey=prov.public_key_str,
        request_id="req-1",
    )
    assert first.ok
    second = redeem_payment(
        payment,
        price="1.0",
        unit="pic",
        issuer_pubkeys=[],
        spent_set=spent,
        now=FIXED_NOW,
        provider_pubkey=prov.public_key_str,
        request_id="req-1",
    )
    assert not second.ok
    assert second.reason == "double_spend"


def test_x402_payment_is_provider_and_request_bound() -> None:
    # Regression: an x402 payment is bound to one provider + request, so a captured
    # payment cannot be replayed to a different gateway or for a different call.
    payer = KeyPair.generate()
    prov = KeyPair.generate()
    other = KeyPair.generate()
    payment = build_x402_payment(
        payer_keypair=payer, amount="1.0", unit="pic", now=_now, provider_pubkey=prov.public_key_str, request_id="req-1"
    )
    wrong_provider = redeem_payment(
        payment,
        price="1.0",
        unit="pic",
        issuer_pubkeys=[],
        spent_set=SpentSet(),
        now=FIXED_NOW,
        provider_pubkey=other.public_key_str,
        request_id="req-1",
    )
    assert not wrong_provider.ok
    wrong_request = redeem_payment(
        payment,
        price="1.0",
        unit="pic",
        issuer_pubkeys=[],
        spent_set=SpentSet(),
        now=FIXED_NOW,
        provider_pubkey=prov.public_key_str,
        request_id="req-2",
    )
    assert not wrong_request.ok


def test_redeem_happy_path_marks_spent(issuer: Issuer) -> None:
    vouchers = issuer.issue("1.00", count=2, now=_now)
    payment = build_pic_payment(vouchers)
    spent = SpentSet()

    result = redeem_payment(
        payment,
        price="1.50",
        unit="pic",
        issuer_pubkeys=[issuer.pubkey],
        spent_set=spent,
        now=FIXED_NOW,
    )

    assert isinstance(result, RedeemResult)
    assert result.ok is True
    assert result.scheme == "pic"
    assert Decimal(result.total) == Decimal("2.00")
    for v in vouchers:
        assert spent.is_spent(v["voucher_id"])


def test_redeem_exact_price_ok(issuer: Issuer) -> None:
    vouchers = issuer.issue("1.00", count=1, now=_now)
    result = redeem_payment(
        build_pic_payment(vouchers),
        price="1.00",
        unit="pic",
        issuer_pubkeys=[issuer.pubkey],
        spent_set=SpentSet(),
        now=FIXED_NOW,
    )
    assert result.ok is True


def test_redeem_insufficient_total_rejected(issuer: Issuer) -> None:
    vouchers = issuer.issue("1.00", count=1, now=_now)
    spent = SpentSet()
    result = redeem_payment(
        build_pic_payment(vouchers),
        price="2.00",
        unit="pic",
        issuer_pubkeys=[issuer.pubkey],
        spent_set=spent,
        now=FIXED_NOW,
    )
    assert result.ok is False
    assert result.reason == "insufficient"
    # Nothing consumed on a rejected batch.
    assert spent.is_spent(vouchers[0]["voucher_id"]) is False


def test_redeem_double_spend_of_already_spent_voucher(issuer: Issuer) -> None:
    vouchers = issuer.issue("2.00", count=1, now=_now)
    spent = SpentSet()
    spent.spend(vouchers[0]["voucher_id"])  # already redeemed earlier

    result = redeem_payment(
        build_pic_payment(vouchers),
        price="1.00",
        unit="pic",
        issuer_pubkeys=[issuer.pubkey],
        spent_set=spent,
        now=FIXED_NOW,
    )
    assert result.ok is False
    assert result.reason == "double_spend"


def test_redeem_batch_with_one_spent_voucher_rolls_back(issuer: Issuer) -> None:
    good = issuer.issue("1.00", count=1, now=_now)[0]
    already = issuer.issue("1.00", count=1, now=_now)[0]
    spent = SpentSet()
    spent.spend(already["voucher_id"])  # pre-spent

    result = redeem_payment(
        build_pic_payment([good, already]),
        price="1.00",
        unit="pic",
        issuer_pubkeys=[issuer.pubkey],
        spent_set=spent,
        now=FIXED_NOW,
    )

    assert result.ok is False
    assert result.reason == "double_spend"
    # All-or-nothing: the good voucher must NOT be consumed (credit not burned).
    assert spent.is_spent(good["voucher_id"]) is False
    # The pre-spent one stays spent.
    assert spent.is_spent(already["voucher_id"]) is True


def test_redeem_duplicate_voucher_ids_in_one_payment_rejected(issuer: Issuer) -> None:
    voucher = issuer.issue("2.00", count=1, now=_now)[0]
    spent = SpentSet()

    result = redeem_payment(
        build_pic_payment([voucher, voucher]),  # same id twice
        price="1.00",
        unit="pic",
        issuer_pubkeys=[issuer.pubkey],
        spent_set=spent,
        now=FIXED_NOW,
    )

    assert result.ok is False
    assert result.reason == "double_spend"
    assert spent.is_spent(voucher["voucher_id"]) is False  # rolled back


def test_redeem_expired_voucher_rejected(issuer: Issuer) -> None:
    vouchers = issuer.issue("2.00", count=1, ttl_seconds=3600, now=_now)
    spent = SpentSet()
    later = FIXED_NOW + timedelta(seconds=3601)

    result = redeem_payment(
        build_pic_payment(vouchers),
        price="1.00",
        unit="pic",
        issuer_pubkeys=[issuer.pubkey],
        spent_set=spent,
        now=later,
    )
    assert result.ok is False
    assert result.reason == "expired"
    assert spent.is_spent(vouchers[0]["voucher_id"]) is False


def test_redeem_wrong_issuer_rejected(issuer: Issuer) -> None:
    vouchers = issuer.issue("2.00", count=1, now=_now)
    other = Issuer(KeyPair.generate())
    spent = SpentSet()

    result = redeem_payment(
        build_pic_payment(vouchers),
        price="1.00",
        unit="pic",
        issuer_pubkeys=[other.pubkey],  # voucher's issuer not trusted
        spent_set=spent,
        now=FIXED_NOW,
    )
    assert result.ok is False
    assert result.reason == "wrong_issuer"
    assert spent.is_spent(vouchers[0]["voucher_id"]) is False


def test_redeem_wrong_unit_rejected(issuer: Issuer) -> None:
    vouchers = issuer.issue("2.00", count=1, now=_now)  # unit "pic"
    result = redeem_payment(
        build_pic_payment(vouchers),
        price="1.00",
        unit="usdc",
        issuer_pubkeys=[issuer.pubkey],
        spent_set=SpentSet(),
        now=FIXED_NOW,
    )
    assert result.ok is False
    assert result.reason == "invalid_voucher"


def test_redeem_tampered_voucher_rejected(issuer: Issuer) -> None:
    vouchers = issuer.issue("1.00", count=1, now=_now)
    vouchers[0]["denomination"] = "9999.00"  # break the signature
    spent = SpentSet()
    result = redeem_payment(
        build_pic_payment(vouchers),
        price="1.00",
        unit="pic",
        issuer_pubkeys=[issuer.pubkey],
        spent_set=spent,
        now=FIXED_NOW,
    )
    assert result.ok is False
    assert result.reason == "invalid_voucher"
    assert spent.is_spent(vouchers[0]["voucher_id"]) is False


def test_redeem_x402_happy_path() -> None:
    kp = KeyPair.generate()
    payment = build_x402_payment(payer_keypair=kp, amount="1.00", unit="usdc", now=_now)
    result = redeem_payment(
        payment,
        price="1.00",
        unit="usdc",
        issuer_pubkeys=[],
        spent_set=SpentSet(),
        now=FIXED_NOW,
    )
    assert result.ok is True
    assert result.scheme == "x402"
    assert Decimal(result.total) == Decimal("1.00")


def test_redeem_x402_underpayment_rejected() -> None:
    kp = KeyPair.generate()
    payment = build_x402_payment(payer_keypair=kp, amount="0.50", unit="usdc", now=_now)
    result = redeem_payment(
        payment,
        price="1.00",
        unit="usdc",
        issuer_pubkeys=[],
        spent_set=SpentSet(),
        now=FIXED_NOW,
    )
    assert result.ok is False
    assert result.reason == "insufficient"


def test_redeem_unsupported_scheme() -> None:
    result = redeem_payment(
        {"scheme": "bitcoin"},
        price="1.00",
        unit="pic",
        issuer_pubkeys=[],
        spent_set=SpentSet(),
        now=FIXED_NOW,
    )
    assert result.ok is False
    assert result.reason == "unsupported_scheme"


def test_payment_required_shape() -> None:
    challenge = payment_required(
        price="0.25",
        unit="pic",
        issuer_pubkeys=["ed25519:abc"],
        accept=["pic", "x402"],
    )
    assert challenge == {
        "price_amount": "0.25",
        "price_units": "pic",
        "accepted_schemes": ["pic", "x402"],
        "pic_issuers": ["ed25519:abc"],
    }
