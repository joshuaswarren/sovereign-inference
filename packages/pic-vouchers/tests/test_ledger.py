# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the provider-side settlement Ledger."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from sip_pic.ledger import Ledger

PROVIDER_A = "ed25519:providerA"
PROVIDER_B = "ed25519:providerB"


def test_empty_ledger_balances_are_zero() -> None:
    ledger = Ledger()
    assert ledger.balance(PROVIDER_A) == Decimal("0")
    assert ledger.total() == Decimal("0")


def test_record_and_balance_for_provider() -> None:
    ledger = Ledger()
    ledger.record(PROVIDER_A, "1.50", "pic", ["v1"])
    ledger.record(PROVIDER_A, "0.50", "pic", ["v2"])
    assert ledger.balance(PROVIDER_A) == Decimal("2.00")


def test_balance_is_per_provider() -> None:
    ledger = Ledger()
    ledger.record(PROVIDER_A, "1.00", "pic", ["v1"])
    ledger.record(PROVIDER_B, "3.00", "pic", ["v2"])
    assert ledger.balance(PROVIDER_A) == Decimal("1.00")
    assert ledger.balance(PROVIDER_B) == Decimal("3.00")


def test_balance_filters_by_unit() -> None:
    ledger = Ledger()
    ledger.record(PROVIDER_A, "1.00", "pic", ["v1"])
    ledger.record(PROVIDER_A, "2.00", "usdc", ["v2"])
    assert ledger.balance(PROVIDER_A, "pic") == Decimal("1.00")
    assert ledger.balance(PROVIDER_A, "usdc") == Decimal("2.00")
    assert ledger.balance(PROVIDER_A) == Decimal("3.00")


def test_total_across_all_providers() -> None:
    ledger = Ledger()
    ledger.record(PROVIDER_A, "1.00", "pic", ["v1"])
    ledger.record(PROVIDER_B, "2.00", "pic", ["v2"])
    ledger.record(PROVIDER_B, "5.00", "usdc", ["v3"])
    assert ledger.total() == Decimal("8.00")
    assert ledger.total("pic") == Decimal("3.00")
    assert ledger.total("usdc") == Decimal("5.00")


def test_ledger_persists_across_reopen(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    first = Ledger(path)
    first.record(PROVIDER_A, "2.50", "pic", ["v1", "v2"])

    reopened = Ledger(path)
    assert reopened.balance(PROVIDER_A) == Decimal("2.50")
    assert reopened.total() == Decimal("2.50")


def test_missing_ledger_file_is_empty(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "nope.json")
    assert ledger.total() == Decimal("0")


def test_corrupt_ledger_file_is_empty(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.json"
    path.write_text("not json", encoding="utf-8")
    ledger = Ledger(path)
    assert ledger.total() == Decimal("0")
    ledger.record(PROVIDER_A, "1.00", "pic", ["v1"])
    assert Ledger(path).balance(PROVIDER_A) == Decimal("1.00")
