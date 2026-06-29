# SPDX-License-Identifier: AGPL-3.0-or-later
"""SpentSet — the atomic double-spend guard for voucher redemption.

A voucher's ``voucher_id`` is its double-spend key: redeeming a voucher marks
its id spent, and a second redemption of the same id must fail. The set is
in-memory by default, or JSON-file backed when a ``path`` is supplied so the
guard survives a process restart. File writes are load-modify-save and tolerate
a missing or corrupt file (treated as empty).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


class SpentSet:
    """Tracks spent voucher ids; optionally persisted to a JSON file."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._spent: set[str] = self._load()

    def _load(self) -> set[str]:
        if self._path is None or not self._path.exists():
            return set()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Missing/corrupt/unreadable file -> start empty.
            return set()
        if not isinstance(raw, list):
            return set()
        return {item for item in raw if isinstance(item, str)}

    def _save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(sorted(self._spent))
        # Atomic replace so a crash mid-write cannot corrupt the live file.
        fd, tmp_name = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            Path(tmp_name).replace(self._path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def is_spent(self, voucher_id: str) -> bool:
        """True if ``voucher_id`` has already been spent."""
        return voucher_id in self._spent

    def spend(self, voucher_id: str) -> bool:
        """Atomically mark ``voucher_id`` spent.

        Returns True on first spend, False if it was already spent (the
        double-spend signal). Persists to disk when a path is configured.
        """
        if voucher_id in self._spent:
            return False
        self._spent.add(voucher_id)
        self._save()
        return True

    def unspend(self, voucher_id: str) -> None:
        """Remove ``voucher_id`` from the spent set (rollback). A no-op if absent."""
        if voucher_id in self._spent:
            self._spent.discard(voucher_id)
            self._save()
