# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for SpentSet — the atomic double-spend guard."""

from __future__ import annotations

import multiprocessing as mp
import sqlite3
import threading
from pathlib import Path

from sip_pic.spentset import SpentSet


def test_in_memory_spend_then_replay() -> None:
    spent = SpentSet()
    assert spent.is_spent("v1") is False
    assert spent.spend("v1") is True  # first spend succeeds
    assert spent.is_spent("v1") is True
    assert spent.spend("v1") is False  # replay is rejected


def test_unspend_rolls_back() -> None:
    spent = SpentSet()
    assert spent.spend("v1") is True
    spent.unspend("v1")
    assert spent.is_spent("v1") is False
    assert spent.spend("v1") is True  # spendable again after rollback


def test_unspend_unknown_id_is_noop() -> None:
    spent = SpentSet()
    spent.unspend("never-seen")  # must not raise
    assert spent.is_spent("never-seen") is False


def test_persists_across_reopen_of_same_path(tmp_path: Path) -> None:
    path = tmp_path / "spent.json"
    first = SpentSet(path)
    assert first.spend("v1") is True

    reopened = SpentSet(path)
    assert reopened.is_spent("v1") is True
    assert reopened.spend("v1") is False  # double-spend guard survives restart


def test_unspend_persists_to_disk(tmp_path: Path) -> None:
    path = tmp_path / "spent.json"
    first = SpentSet(path)
    first.spend("v1")
    first.unspend("v1")

    reopened = SpentSet(path)
    assert reopened.is_spent("v1") is False


def test_accepts_str_path(tmp_path: Path) -> None:
    path = str(tmp_path / "spent.json")
    spent = SpentSet(path)
    assert spent.spend("v1") is True
    assert SpentSet(path).is_spent("v1") is True


def test_missing_file_is_treated_as_empty(tmp_path: Path) -> None:
    path = tmp_path / "does-not-exist.json"
    spent = SpentSet(path)
    assert spent.is_spent("anything") is False


def test_corrupt_file_is_treated_as_empty(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.json"
    path.write_text("{not valid json", encoding="utf-8")
    spent = SpentSet(path)
    assert spent.is_spent("v1") is False
    assert spent.spend("v1") is True  # recovers and writes a clean file
    assert SpentSet(path).is_spent("v1") is True


# --- cross-process / cross-thread atomicity (issue #24 regression) ----------


def _mp_spend_worker(db_path: str, key: str, barrier: object, queue: object) -> None:
    """Module-level worker so a multiprocessing context can target it."""
    from sip_pic.spentset import SpentSet

    barrier.wait()  # type: ignore[attr-defined]  # all processes load together, then race
    queue.put(SpentSet(db_path).spend(key))  # type: ignore[attr-defined]


def test_concurrent_processes_single_winner(tmp_path: Path) -> None:
    # The primary regression: N processes each load their OWN snapshot and race
    # the SAME key. With the old load-check-rewrite store this is last-writer-
    # wins, so several processes see the key unspent and return True (double
    # spend). The atomic INSERT must make exactly one the winner.
    db = str(tmp_path / "spent.db")
    # Pre-create the DB + schema with a fully CLOSED connection so the forked
    # workers each open an independent connection with no inherited WAL
    # shared-memory mapping (forking an open WAL connection can corrupt the DB).
    pre = sqlite3.connect(db)
    pre.execute("PRAGMA journal_mode=WAL")
    pre.execute("CREATE TABLE IF NOT EXISTS spent (spend_key TEXT PRIMARY KEY) WITHOUT ROWID")
    pre.close()
    # ``fork`` (the POSIX default) inherits already-imported modules, so the
    # module-level worker is resolvable in the child without re-importing the
    # (non-importable by dotted path) test module.
    ctx = mp.get_context("fork")
    n = 8
    barrier: object = ctx.Barrier(n)
    queue: object = ctx.Queue()
    procs = [ctx.Process(target=_mp_spend_worker, args=(db, "v1", barrier, queue)) for _ in range(n)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
        assert p.exitcode == 0, f"worker died with {p.exitcode}"
    results = [queue.get(timeout=5) for _ in procs]  # type: ignore[attr-defined]
    assert results.count(True) == 1
    assert results.count(False) == n - 1
    # The store reflects the single winner.
    assert SpentSet(db).is_spent("v1") is True


def test_concurrent_threads_single_winner(tmp_path: Path) -> None:
    # Companion: many threads, each opening its OWN SpentSet (its own snapshot),
    # gated by a Barrier so they all load before any can write. Separate
    # instances (not one shared object) are what exposes the read-modify-write
    # race — the GIL would mask it on a single shared in-memory set.
    path = tmp_path / "spent.db"
    n = 16
    barrier = threading.Barrier(n)
    outcomes: list[bool] = []
    lock = threading.Lock()

    def racer() -> None:
        barrier.wait()
        won = SpentSet(path).spend("v1")  # fresh load per thread
        with lock:
            outcomes.append(won)

    threads = [threading.Thread(target=racer) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes.count(True) == 1
    assert outcomes.count(False) == n - 1


def test_x402_nonce_replay_blocked_across_reopen(tmp_path: Path) -> None:
    # Encodes the restart-replay fix: a spent x402 nonce survives reopen, so the
    # same nonce cannot redeem again after a gateway restart.
    path = tmp_path / "spent.db"
    first = SpentSet(path)
    assert first.spend("x402:abc") is True

    reopened = SpentSet(path)
    assert reopened.is_spent("x402:abc") is True
    assert reopened.spend("x402:abc") is False  # replay rejected across restart
