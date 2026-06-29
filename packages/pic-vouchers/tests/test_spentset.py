# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for SpentSet — the atomic double-spend guard."""

from __future__ import annotations

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
