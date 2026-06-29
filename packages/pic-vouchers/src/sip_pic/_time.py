# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared time helpers.

All wall-clock reads go through an injectable ``NowFn`` so behaviour is
deterministic in tests. ``utc_now`` is the production default.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

NowFn = Callable[[], datetime]


def utc_now() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)
