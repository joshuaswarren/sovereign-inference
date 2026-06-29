# SPDX-License-Identifier: AGPL-3.0-or-later
"""Payment construction, redemption, and the HTTP 402 challenge.

Two payment schemes are supported:

* ``pic``   — a batch of issuer-signed bearer vouchers, redeemed atomically with
  a double-spend guard. Either the whole batch is consumed or none of it is.
* ``x402``  — a single payer-signed direct-pay assertion (see :mod:`.x402`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sip_protocol import verify_voucher, voucher_is_expired

from .spentset import SpentSet
from .x402 import verify_x402_payment, x402_nonce


@dataclass(frozen=True)
class RedeemResult:
    """Outcome of a redemption attempt."""

    ok: bool
    scheme: str
    total: str
    reason: str


def build_pic_payment(vouchers: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap a batch of vouchers as a ``pic`` payment body."""
    return {"scheme": "pic", "vouchers": vouchers}


def payment_required(
    *,
    price: str,
    unit: str,
    issuer_pubkeys: list[str],
    accept: list[str],
) -> dict[str, Any]:
    """Build the body of an HTTP 402 ``payment required`` challenge."""
    return {
        "price_amount": price,
        "price_units": unit,
        "accepted_schemes": accept,
        "pic_issuers": issuer_pubkeys,
    }


def _validate_voucher(
    voucher: dict[str, Any],
    *,
    unit: str,
    issuer_pubkeys: list[str],
    now: datetime,
) -> str | None:
    """Return a failure reason for ``voucher``, or ``None`` if it is acceptable."""
    if not verify_voucher(voucher).valid:
        return "invalid_voucher"
    if voucher.get("unit") != unit:
        return "invalid_voucher"
    if voucher.get("issuer_pubkey") not in issuer_pubkeys:
        return "wrong_issuer"
    if voucher_is_expired(voucher, now):
        return "expired"
    return None


def _redeem_pic(
    payment: dict[str, Any],
    *,
    price: str,
    unit: str,
    issuer_pubkeys: list[str],
    spent_set: SpentSet,
    now: datetime,
    commit: bool,
) -> RedeemResult:
    vouchers = payment.get("vouchers")
    if not isinstance(vouchers, list) or not vouchers:
        return RedeemResult(ok=False, scheme="pic", total="0", reason="invalid_voucher")

    # Reject duplicate voucher_ids within a single payment (a self double-spend).
    seen: set[str] = set()
    for voucher in vouchers:
        voucher_id = voucher.get("voucher_id")
        if not isinstance(voucher_id, str) or voucher_id in seen:
            return RedeemResult(ok=False, scheme="pic", total="0", reason="double_spend")
        seen.add(voucher_id)

    # Validate every voucher (and reject any already spent) before consuming.
    total = Decimal("0")
    for voucher in vouchers:
        reason = _validate_voucher(voucher, unit=unit, issuer_pubkeys=issuer_pubkeys, now=now)
        if reason is not None:
            return RedeemResult(ok=False, scheme="pic", total="0", reason=reason)
        if spent_set.is_spent(voucher["voucher_id"]):
            return RedeemResult(ok=False, scheme="pic", total="0", reason="double_spend")
        try:
            total += Decimal(voucher["denomination"])
        except (InvalidOperation, KeyError, TypeError):
            return RedeemResult(ok=False, scheme="pic", total="0", reason="invalid_voucher")

    if total < Decimal(price):
        return RedeemResult(ok=False, scheme="pic", total=str(total), reason="insufficient")

    if not commit:
        # Verify only: do not consume (used to charge-on-success after serving).
        return RedeemResult(ok=True, scheme="pic", total=str(total), reason="")

    # Atomic spend: mark every id, rolling back the whole batch on any collision.
    spent_ids: list[str] = []
    for voucher in vouchers:
        voucher_id = voucher["voucher_id"]
        if spent_set.spend(voucher_id):
            spent_ids.append(voucher_id)
        else:
            for done in spent_ids:
                spent_set.unspend(done)
            return RedeemResult(ok=False, scheme="pic", total=str(total), reason="double_spend")

    return RedeemResult(ok=True, scheme="pic", total=str(total), reason="")


def redeem_payment(
    payment: dict[str, Any],
    *,
    price: str,
    unit: str,
    issuer_pubkeys: list[str],
    spent_set: SpentSet,
    now: datetime,
    commit: bool = True,
    provider_pubkey: str | None = None,
    request_id: str | None = None,
) -> RedeemResult:
    """Verify and (when ``commit``) consume ``payment`` against ``price``.

    With ``commit=False`` the payment is only validated (nothing is spent), so a
    caller can charge-on-success: verify before serving, then call again with
    ``commit=True`` to consume the credit only once a response is in hand. PIC
    redemption is all-or-nothing; x402 payments are single-use per ``nonce`` and
    bound to ``provider_pubkey`` / ``request_id`` when those are supplied. On any
    failure the result carries ``ok=False`` and a machine-readable ``reason``.
    """
    scheme = payment.get("scheme")
    if scheme == "pic":
        return _redeem_pic(
            payment,
            price=price,
            unit=unit,
            issuer_pubkeys=issuer_pubkeys,
            spent_set=spent_set,
            now=now,
            commit=commit,
        )
    if scheme == "x402":
        nonce = x402_nonce(payment)
        if nonce is None:
            return RedeemResult(ok=False, scheme="x402", total="0", reason="invalid_payment")
        if not verify_x402_payment(
            payment, price=price, unit=unit, now=now, provider_pubkey=provider_pubkey, request_id=request_id
        ):
            return RedeemResult(ok=False, scheme="x402", total="0", reason="insufficient")
        spent_key = "x402:" + nonce
        if spent_set.is_spent(spent_key):
            return RedeemResult(ok=False, scheme="x402", total="0", reason="double_spend")
        if commit and not spent_set.spend(spent_key):
            return RedeemResult(ok=False, scheme="x402", total="0", reason="double_spend")
        inner = payment.get("payment")
        amount = inner.get("amount", price) if isinstance(inner, dict) else price
        return RedeemResult(ok=True, scheme="x402", total=str(amount), reason="")
    return RedeemResult(ok=False, scheme=str(scheme), total="0", reason="unsupported_scheme")
