# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for Issuer — minting fresh signed PIC vouchers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sip_pic.issuer import Issuer
from sip_protocol import KeyPair, verify_voucher, voucher_is_expired

FIXED_NOW = datetime(2026, 6, 29, 12, 0, 0, tzinfo=UTC)


def _now() -> datetime:
    return FIXED_NOW


def test_pubkey_property_matches_keypair() -> None:
    kp = KeyPair.generate()
    issuer = Issuer(kp)
    assert issuer.pubkey == kp.public_key_str


def test_issue_returns_n_distinct_valid_signed_vouchers() -> None:
    kp = KeyPair.generate()
    issuer = Issuer(kp)

    vouchers = issuer.issue("1.00", count=3, now=_now)

    assert len(vouchers) == 3
    ids = {v["voucher_id"] for v in vouchers}
    assert len(ids) == 3  # all distinct bearer secrets
    for v in vouchers:
        result = verify_voucher(v)
        assert result.valid, result.errors
        assert v["denomination"] == "1.00"
        assert v["unit"] == "pic"
        assert v["issuer_pubkey"] == kp.public_key_str


def test_issue_defaults_to_count_one() -> None:
    issuer = Issuer(KeyPair.generate())
    vouchers = issuer.issue("5", now=_now)
    assert len(vouchers) == 1


def test_issue_respects_unit_override() -> None:
    issuer = Issuer(KeyPair.generate(), unit="test")
    vouchers = issuer.issue("2.5", now=_now)
    assert vouchers[0]["unit"] == "test"
    assert verify_voucher(vouchers[0]).valid


def test_issue_sets_expiry_from_ttl_and_is_not_expired_at_now() -> None:
    issuer = Issuer(KeyPair.generate())
    vouchers = issuer.issue("1", ttl_seconds=3600, now=_now)
    v = vouchers[0]

    assert not voucher_is_expired(v, FIXED_NOW)
    # Just at expiry boundary -> expired.
    assert voucher_is_expired(v, FIXED_NOW + timedelta(seconds=3600))


def test_issue_uses_default_now_when_not_injected() -> None:
    issuer = Issuer(KeyPair.generate())
    before = datetime.now(UTC)
    vouchers = issuer.issue("1", ttl_seconds=3600)
    after = datetime.now(UTC)

    issued = datetime.fromisoformat(vouchers[0]["issued_at"].replace("Z", "+00:00"))
    assert before.replace(microsecond=0) <= issued <= after + timedelta(seconds=1)
