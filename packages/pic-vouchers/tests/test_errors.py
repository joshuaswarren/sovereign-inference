# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the sip_pic error hierarchy."""

from __future__ import annotations

from sip_pic.errors import InsufficientFunds, PicError


def test_pic_error_is_exception() -> None:
    assert issubclass(PicError, Exception)


def test_insufficient_funds_is_pic_error() -> None:
    assert issubclass(InsufficientFunds, PicError)


def test_insufficient_funds_can_be_raised_and_caught_as_pic_error() -> None:
    try:
        raise InsufficientFunds("short by 1.0 pic")
    except PicError as exc:
        assert "short by 1.0 pic" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("InsufficientFunds was not raised")
