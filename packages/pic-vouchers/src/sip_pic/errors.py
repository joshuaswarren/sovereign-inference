# SPDX-License-Identifier: AGPL-3.0-or-later
"""Error hierarchy for Private Inference Credits (PIC)."""

from __future__ import annotations


class PicError(Exception):
    """Base class for all sip_pic errors."""


class InsufficientFunds(PicError):
    """Raised when a wallet cannot cover a requested amount in a given unit."""
