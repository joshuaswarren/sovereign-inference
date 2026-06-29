# SPDX-License-Identifier: AGPL-3.0-or-later
"""Ledger — provider-side accounting of redeemed value.

Each redemption appends an entry crediting a provider with an amount in a unit,
referencing the voucher ids (or other settlement refs) it came from. The ledger
is in-memory by default, or JSON-file backed when a ``path`` is supplied.
"""

from __future__ import annotations

import json
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any


class Ledger:
    """Append-only record of value credited to providers."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._entries: list[dict[str, Any]] = self._load()

    def _load(self) -> list[dict[str, Any]]:
        if self._path is None or not self._path.exists():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(raw, list):
            return []
        return [entry for entry in raw if isinstance(entry, dict)]

    def _save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._entries)
        fd, tmp_name = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            Path(tmp_name).replace(self._path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def record(self, provider_pubkey: str, amount: str, unit: str, refs: list[str]) -> None:
        """Credit ``provider_pubkey`` with ``amount`` of ``unit``, citing ``refs``."""
        self._entries.append(
            {
                "provider_pubkey": provider_pubkey,
                "amount": amount,
                "unit": unit,
                "refs": list(refs),
            }
        )
        self._save()

    def balance(self, provider_pubkey: str, unit: str | None = None) -> Decimal:
        """Total credited to ``provider_pubkey``, optionally restricted to ``unit``."""
        total = Decimal("0")
        for entry in self._entries:
            if entry.get("provider_pubkey") != provider_pubkey:
                continue
            if unit is None or entry.get("unit") == unit:
                total += Decimal(entry["amount"])
        return total

    def total(self, unit: str | None = None) -> Decimal:
        """Total credited across all providers, optionally restricted to ``unit``."""
        total = Decimal("0")
        for entry in self._entries:
            if unit is None or entry.get("unit") == unit:
                total += Decimal(entry["amount"])
        return total
