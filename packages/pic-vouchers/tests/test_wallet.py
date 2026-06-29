# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for Wallet — holding, balance, and greedy selection of vouchers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from sip_pic.errors import InsufficientFunds
from sip_pic.issuer import Issuer
from sip_pic.wallet import Wallet
from sip_protocol import KeyPair

FIXED_NOW = datetime(2026, 6, 29, 12, 0, 0, tzinfo=UTC)


def _now() -> datetime:
    return FIXED_NOW


@pytest.fixture
def issuer() -> Issuer:
    return Issuer(KeyPair.generate())


def test_empty_wallet_balance_is_zero() -> None:
    wallet = Wallet()
    assert wallet.balance("pic") == Decimal("0")
    assert wallet.vouchers == []


def test_add_and_balance_sums_denominations_for_unit(issuer: Issuer) -> None:
    wallet = Wallet()
    wallet.add(*issuer.issue("1.50", count=2, now=_now))
    assert wallet.balance("pic") == Decimal("3.00")


def test_balance_without_unit_sums_everything(issuer: Issuer) -> None:
    test_issuer = Issuer(KeyPair.generate(), unit="test")
    wallet = Wallet(issuer.issue("2", now=_now))
    wallet.add(*test_issuer.issue("3", now=_now))
    assert wallet.balance() == Decimal("5")


def test_balance_filters_by_unit(issuer: Issuer) -> None:
    test_issuer = Issuer(KeyPair.generate(), unit="test")
    wallet = Wallet(issuer.issue("2", now=_now))
    wallet.add(*test_issuer.issue("3", now=_now))
    assert wallet.balance("pic") == Decimal("2")
    assert wallet.balance("test") == Decimal("3")


def test_select_returns_vouchers_summing_to_at_least_amount_and_debits(issuer: Issuer) -> None:
    wallet = Wallet(issuer.issue("1.00", count=3, now=_now))
    assert wallet.balance("pic") == Decimal("3.00")

    picked = wallet.select("2.00", "pic")

    assert sum(Decimal(v["denomination"]) for v in picked) >= Decimal("2.00")
    # Selected vouchers are removed from the wallet.
    assert wallet.balance("pic") == Decimal("3.00") - sum(Decimal(v["denomination"]) for v in picked)
    picked_ids = {v["voucher_id"] for v in picked}
    held_ids = {v["voucher_id"] for v in wallet.vouchers}
    assert picked_ids.isdisjoint(held_ids)


def test_select_exact_amount_consumes_minimum_vouchers(issuer: Issuer) -> None:
    wallet = Wallet(issuer.issue("1.00", count=3, now=_now))
    picked = wallet.select("2.00", "pic")
    assert len(picked) == 2
    assert wallet.balance("pic") == Decimal("1.00")


def test_select_only_picks_matching_unit(issuer: Issuer) -> None:
    test_issuer = Issuer(KeyPair.generate(), unit="test")
    wallet = Wallet(issuer.issue("1", count=2, now=_now))
    wallet.add(*test_issuer.issue("5", now=_now))

    picked = wallet.select("2", "pic")

    assert all(v["unit"] == "pic" for v in picked)
    assert wallet.balance("test") == Decimal("5")  # untouched


def test_select_raises_insufficient_funds_when_short(issuer: Issuer) -> None:
    wallet = Wallet(issuer.issue("1.00", count=1, now=_now))
    with pytest.raises(InsufficientFunds):
        wallet.select("2.00", "pic")
    # Wallet is left intact on failure.
    assert wallet.balance("pic") == Decimal("1.00")


def test_select_raises_when_unit_absent(issuer: Issuer) -> None:
    wallet = Wallet(issuer.issue("5", count=1, now=_now))
    with pytest.raises(InsufficientFunds):
        wallet.select("1", "test")
