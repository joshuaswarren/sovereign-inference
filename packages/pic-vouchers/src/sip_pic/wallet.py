# SPDX-License-Identifier: AGPL-3.0-or-later
"""Wallet — a holder of bearer vouchers with balance and greedy selection."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .errors import InsufficientFunds


class Wallet:
    """Holds vouchers and selects subsets to spend.

    ``select`` is destructive: chosen vouchers are removed from the wallet and
    returned to the caller (they are now in flight as a payment).
    """

    def __init__(self, vouchers: list[dict[str, Any]] | None = None) -> None:
        self._vouchers: list[dict[str, Any]] = list(vouchers) if vouchers else []

    def add(self, *vouchers: dict[str, Any]) -> None:
        """Add one or more vouchers to the wallet."""
        self._vouchers.extend(vouchers)

    @property
    def vouchers(self) -> list[dict[str, Any]]:
        """The vouchers currently held (a copy, so the wallet stays encapsulated)."""
        return list(self._vouchers)

    def balance(self, unit: str | None = None) -> Decimal:
        """Total face value held, optionally restricted to a single ``unit``."""
        total = Decimal("0")
        for voucher in self._vouchers:
            if unit is None or voucher.get("unit") == unit:
                total += Decimal(voucher["denomination"])
        return total

    def select(self, amount: str, unit: str) -> list[dict[str, Any]]:
        """Greedily pick held ``unit`` vouchers summing to >= ``amount``.

        The chosen vouchers are removed from the wallet and returned. Raises
        :class:`InsufficientFunds` if the held balance in ``unit`` is below
        ``amount``; the wallet is left untouched in that case.
        """
        target = Decimal(amount)
        if self.balance(unit) < target:
            raise InsufficientFunds(f"need {amount} {unit}, have {self.balance(unit)}")

        picked: list[dict[str, Any]] = []
        accumulated = Decimal("0")
        for voucher in self._vouchers:
            if accumulated >= target:
                break
            if voucher.get("unit") == unit:
                picked.append(voucher)
                accumulated += Decimal(voucher["denomination"])

        picked_ids = {id(v) for v in picked}
        self._vouchers = [v for v in self._vouchers if id(v) not in picked_ids]
        return picked
