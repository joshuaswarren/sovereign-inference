# SPDX-License-Identifier: AGPL-3.0-or-later
"""SpentSet — the atomic, cross-process double-spend guard for redemption.

A spend key (a voucher_id, a blind-credit serial key, or an x402 nonce key) is
recorded exactly once: the first ``spend()`` wins, any concurrent or later
``spend()`` of the same key returns ``False``. Backed by SQLite so the guarantee
holds across processes/containers sharing the file (not just within one
process); in-memory when no path is given. Atomicity comes from a
UNIQUE-constrained ``INSERT`` inside a transaction — a losing writer hits
``IntegrityError``, which is the double-spend signal — never from re-reading a
snapshot.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

_SCHEMA = "CREATE TABLE IF NOT EXISTS spent (spend_key TEXT PRIMARY KEY) WITHOUT ROWID"


class SpentSet:
    """Tracks spent keys with cross-process atomic compare-and-set."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else None
        # A single shared connection guarded by a lock. check_same_thread=False
        # lets FastAPI/uvicorn worker threads share it; the lock serializes our
        # own use so we never interleave statements on one connection. Cross-
        # PROCESS safety is SQLite's file lock, not this lock.
        self._lock = threading.Lock()
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        target = str(self._path) if self._path is not None else ":memory:"
        self._conn = self._open(target)

    def _open(self, target: str) -> sqlite3.Connection:
        """Open + configure the connection, recovering from a foreign/corrupt file.

        ``isolation_level=None`` puts the connection in autocommit mode so each
        ``INSERT``/``DELETE`` is its own committed transaction: a winning
        ``spend()`` is durable immediately and a loser sees the UNIQUE conflict.
        WAL + ``busy_timeout`` make concurrent writers wait (then retry under the
        file lock) instead of erroring, so a racing ``spend()`` blocks briefly
        then proceeds — and the UNIQUE constraint still picks exactly one winner.

        A pre-existing file that is not a valid SQLite database (e.g. a leftover
        store from the previous JSON format, or genuinely corrupted bytes) would
        raise ``DatabaseError`` on every statement and brick every redemption.
        We treat that as "empty" and start fresh, matching the prior
        recover-from-corruption contract rather than failing closed. A real
        SQLite file written by this class is never foreign, so this only fires
        on a format migration or true corruption.
        """
        conn = sqlite3.connect(target, check_same_thread=False, isolation_level=None)
        try:
            if self._path is not None:
                # WAL: concurrent readers don't block the writer; better
                # multi-process throughput. NORMAL sync is durable enough for a
                # spend log.
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                # Wait rather than immediately erroring when another process
                # holds the write lock, so a racing spend() blocks briefly then
                # proceeds.
                conn.execute("PRAGMA busy_timeout=5000")
            conn.execute(_SCHEMA)
            return conn
        except sqlite3.DatabaseError:
            conn.close()
            if self._path is not None and self._path.exists():
                # Foreign/corrupt file: replace with a clean database. Recurses
                # at most once because the file no longer exists after unlink.
                self._path.unlink()
                return self._open(target)
            raise

    def is_spent(self, voucher_id: str) -> bool:
        """True if ``voucher_id`` has already been spent (best-effort read)."""
        with self._lock:
            row = self._conn.execute("SELECT 1 FROM spent WHERE spend_key = ? LIMIT 1", (voucher_id,)).fetchone()
        return row is not None

    def spend(self, voucher_id: str) -> bool:
        """Atomically mark ``voucher_id`` spent across all processes.

        Returns ``True`` on the first successful spend, ``False`` if it was
        already spent (the double-spend signal). The UNIQUE constraint makes the
        winner unambiguous: a concurrent duplicate ``INSERT`` raises
        ``IntegrityError``.
        """
        with self._lock:
            try:
                self._conn.execute("INSERT INTO spent (spend_key) VALUES (?)", (voucher_id,))
            except sqlite3.IntegrityError:
                return False
            return True

    def unspend(self, voucher_id: str) -> None:
        """Remove ``voucher_id`` (rollback of a batch that failed downstream)."""
        with self._lock:
            self._conn.execute("DELETE FROM spent WHERE spend_key = ?", (voucher_id,))
