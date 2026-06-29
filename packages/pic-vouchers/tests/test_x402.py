# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the x402 direct-pay scheme."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sip_pic.x402 import build_x402_payment, verify_x402_payment
from sip_protocol import KeyPair

FIXED_NOW = datetime(2026, 6, 29, 12, 0, 0, tzinfo=UTC)


def _now() -> datetime:
    return FIXED_NOW


def test_build_shape() -> None:
    kp = KeyPair.generate()
    payment = build_x402_payment(payer_keypair=kp, amount="1.00", unit="usdc", now=_now)

    assert payment["scheme"] == "x402"
    inner = payment["payment"]
    assert inner["payer_pubkey"] == kp.public_key_str
    assert inner["amount"] == "1.00"
    assert inner["unit"] == "usdc"
    assert "issued_at" in inner
    assert "signature" in inner


def test_verify_happy_path() -> None:
    kp = KeyPair.generate()
    payment = build_x402_payment(payer_keypair=kp, amount="1.00", unit="usdc", now=_now)
    assert verify_x402_payment(payment, price="1.00", unit="usdc", now=FIXED_NOW) is True


def test_verify_accepts_overpayment() -> None:
    kp = KeyPair.generate()
    payment = build_x402_payment(payer_keypair=kp, amount="2.00", unit="usdc", now=_now)
    assert verify_x402_payment(payment, price="1.00", unit="usdc", now=FIXED_NOW) is True


def test_verify_rejects_underpayment() -> None:
    kp = KeyPair.generate()
    payment = build_x402_payment(payer_keypair=kp, amount="0.50", unit="usdc", now=_now)
    assert verify_x402_payment(payment, price="1.00", unit="usdc", now=FIXED_NOW) is False


def test_verify_rejects_wrong_unit() -> None:
    kp = KeyPair.generate()
    payment = build_x402_payment(payer_keypair=kp, amount="1.00", unit="usdc", now=_now)
    assert verify_x402_payment(payment, price="1.00", unit="pic", now=FIXED_NOW) is False


def test_verify_rejects_tampered_amount_bad_signature() -> None:
    kp = KeyPair.generate()
    payment = build_x402_payment(payer_keypair=kp, amount="1.00", unit="usdc", now=_now)
    # Tamper after signing: amount no longer matches the signed bytes.
    payment["payment"]["amount"] = "5.00"
    assert verify_x402_payment(payment, price="1.00", unit="usdc", now=FIXED_NOW) is False


def test_verify_rejects_stale_payment() -> None:
    kp = KeyPair.generate()
    payment = build_x402_payment(payer_keypair=kp, amount="1.00", unit="usdc", now=_now)
    later = FIXED_NOW + timedelta(seconds=301)
    assert verify_x402_payment(payment, price="1.00", unit="usdc", now=later, max_age_seconds=300) is False


def test_verify_within_max_age_ok() -> None:
    kp = KeyPair.generate()
    payment = build_x402_payment(payer_keypair=kp, amount="1.00", unit="usdc", now=_now)
    later = FIXED_NOW + timedelta(seconds=299)
    assert verify_x402_payment(payment, price="1.00", unit="usdc", now=later, max_age_seconds=300) is True


def test_verify_rejects_malformed_payment() -> None:
    assert verify_x402_payment({"scheme": "x402"}, price="1", unit="usdc", now=FIXED_NOW) is False
    assert verify_x402_payment({}, price="1", unit="usdc", now=FIXED_NOW) is False
