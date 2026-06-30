# SPDX-License-Identifier: AGPL-3.0-or-later
"""sip-pic — Private Inference Credits (PIC).

Public API:
    Errors:      PicError, InsufficientFunds
    Issuance:    Issuer
    Holding:     Wallet
    Spend guard: SpentSet
    x402:        build_x402_payment, verify_x402_payment
    Payments:    build_pic_payment, RedeemResult, redeem_payment, payment_required
    Blind:       BlindIssuer, BlindCredit, blind_credit_request, finalize_blind_credit, redeem_blind_credit
    Settlement:  Ledger
"""

from __future__ import annotations

from .blind import (
    BlindCredit,
    BlindIssuer,
    BlindIssuerKey,
    blind_credit_request,
    finalize_blind_credit,
    redeem_blind_credit,
    verify_blind_credit,
)
from .errors import InsufficientFunds, PicError
from .issuer import Issuer
from .ledger import Ledger
from .payment import (
    RedeemResult,
    build_pic_payment,
    payment_required,
    redeem_payment,
)
from .spentset import SpentSet
from .wallet import Wallet
from .x402 import build_x402_payment, verify_x402_payment

__version__ = "0.1.2"

__all__ = [
    "BlindCredit",
    "BlindIssuer",
    "BlindIssuerKey",
    "InsufficientFunds",
    "Issuer",
    "Ledger",
    "PicError",
    "RedeemResult",
    "SpentSet",
    "Wallet",
    "__version__",
    "blind_credit_request",
    "build_pic_payment",
    "build_x402_payment",
    "finalize_blind_credit",
    "payment_required",
    "redeem_blind_credit",
    "redeem_payment",
    "verify_blind_credit",
    "verify_x402_payment",
]
