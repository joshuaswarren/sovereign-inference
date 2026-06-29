# SPDX-License-Identifier: AGPL-3.0-or-later
"""x402 direct-pay scheme — a signed, freshness-bounded payment assertion.

Unlike PIC vouchers (issuer-signed bearer credits), an x402 payment is signed by
the *payer* and carries an amount and unit. The provider verifies the signature,
that the amount covers the price, that the unit matches, and that the assertion
is fresh (not stale).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sip_protocol import KeyPair, sign_document, verify_document

from ._time import NowFn, utc_now


def _utc_iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_x402_payment(
    *,
    payer_keypair: KeyPair,
    amount: str,
    unit: str,
    now: NowFn = utc_now,
) -> dict[str, Any]:
    """Build a payer-signed x402 payment for ``amount`` of ``unit``."""
    inner = {
        "payer_pubkey": payer_keypair.public_key_str,
        "amount": amount,
        "unit": unit,
        "issued_at": _utc_iso(now()),
    }
    signed = sign_document(inner, payer_keypair)
    return {"scheme": "x402", "payment": signed}


def verify_x402_payment(
    payment: dict[str, Any],
    *,
    price: str,
    unit: str,
    now: datetime,
    max_age_seconds: int = 300,
) -> bool:
    """Return True iff ``payment`` is a valid, sufficient, fresh x402 payment.

    Checks: payer signature is valid, ``amount >= price``, ``unit`` matches, and
    the assertion is no older than ``max_age_seconds`` relative to ``now``.
    """
    if payment.get("scheme") != "x402":
        return False
    inner = payment.get("payment")
    if not isinstance(inner, dict):
        return False

    if inner.get("unit") != unit:
        return False

    try:
        if Decimal(str(inner.get("amount"))) < Decimal(price):
            return False
    except (InvalidOperation, TypeError):
        return False

    if not verify_document(inner, pubkey_field="payer_pubkey"):
        return False

    raw_issued = inner.get("issued_at")
    if not isinstance(raw_issued, str):
        return False
    try:
        issued = datetime.fromisoformat(raw_issued.replace("Z", "+00:00"))
    except ValueError:
        return False
    age = (now.astimezone(UTC) - issued.astimezone(UTC)).total_seconds()
    return age <= max_age_seconds
