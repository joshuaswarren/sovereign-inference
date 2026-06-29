# SPDX-License-Identifier: Apache-2.0
"""Signed Private Inference Credits (PIC vouchers).

A voucher is an issuer-signed **bearer credit**: whoever holds it (with its
secret ``voucher_id``) may redeem it for inference. Like receipts and quotes it
is a detached-signature artifact — the signature covers the canonical voucher
with the ``signature`` field removed.

This is the v1 credit format. It delivers *bearer* privacy (the voucher carries
no buyer identity, so a provider that redeems it learns nothing about who bought
it). It does NOT by itself give issuer-unlinkability — the issuer sees the same
``voucher_id`` at issuance and settlement. The documented upgrade path is blind
signatures (Chaumian ecash / Privacy Pass), which keep this same artifact shape
at the redemption boundary. See docs/spec/private-inference-credits.md.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .documents import sign_document, verify_document
from .schemas import iter_errors
from .signing import KeyPair

VOUCHER_VERSION = "sip-ai.voucher.v1"


@dataclass(frozen=True)
class VoucherVerification:
    valid: bool
    schema_ok: bool
    signature_ok: bool
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid


def _utc_iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_voucher_id() -> str:
    """A fresh high-entropy bearer secret (43-char base64url, 32 bytes)."""
    return secrets.token_urlsafe(32)


def build_voucher(
    *,
    denomination: str,
    unit: str,
    issuer_pubkey: str,
    issued_at: datetime,
    expires_at: datetime,
    voucher_id: str | None = None,
) -> dict[str, Any]:
    """Build an unsigned voucher dict ready for :func:`sign_voucher`."""
    return {
        "voucher_version": VOUCHER_VERSION,
        "voucher_id": voucher_id or new_voucher_id(),
        "denomination": denomination,
        "unit": unit,
        "issuer_pubkey": issuer_pubkey,
        "issued_at": _utc_iso(issued_at),
        "expires_at": _utc_iso(expires_at),
    }


def sign_voucher(voucher: dict[str, Any], keypair: KeyPair) -> dict[str, Any]:
    """Sign a voucher with the issuer's key pair."""
    return sign_document(voucher, keypair)


def verify_voucher(voucher: dict[str, Any]) -> VoucherVerification:
    """Validate a voucher against the schema and verify the issuer signature."""
    errors = iter_errors("voucher", voucher)
    schema_ok = not errors
    signature_ok = verify_document(voucher, pubkey_field="issuer_pubkey")
    if not signature_ok:
        errors = [*errors, "signature: invalid or missing issuer signature"]
    return VoucherVerification(
        valid=schema_ok and signature_ok,
        schema_ok=schema_ok,
        signature_ok=signature_ok,
        errors=errors,
    )


def voucher_is_expired(voucher: dict[str, Any], now: datetime) -> bool:
    """True if ``now`` is at or past the voucher's ``expires_at`` (or it's malformed)."""
    raw = voucher.get("expires_at")
    if not isinstance(raw, str):
        return True
    try:
        expires = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return True
    return now.astimezone(UTC) >= expires.astimezone(UTC)
