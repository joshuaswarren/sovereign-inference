# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the parent-death watchdog (no orphaned sidecar when the app dies)."""

from __future__ import annotations

from sip_openai_proxy.server import watch_parent_once


def test_watch_returns_false_while_parent_is_alive() -> None:
    exited = []
    alive = watch_parent_once(123, is_alive=lambda _pid: True, on_dead=lambda: exited.append(True))
    assert alive is True
    assert exited == []


def test_watch_fires_on_dead_when_parent_is_gone() -> None:
    exited = []
    alive = watch_parent_once(123, is_alive=lambda _pid: False, on_dead=lambda: exited.append(True))
    assert alive is False
    assert exited == [True]
