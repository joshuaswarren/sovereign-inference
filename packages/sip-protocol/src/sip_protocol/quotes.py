# SPDX-License-Identifier: Apache-2.0
"""Signed inference quotes.

A quote is a provider's signed commitment to serve one request at a stated
price, valid until ``expires_at``. Like receipts, it is a detached-signature
artifact: the signature covers the canonical quote minus the ``signature`` field.
The router uses signed quotes so a provider cannot later charge more than it
committed to (the receipt's price is checked against the quote's ``max_price``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .documents import sign_document, verify_document
from .schemas import iter_errors
from .signing import KeyPair

QUOTE_VERSION = "sip-ai.quote.v1"


@dataclass(frozen=True)
class QuoteVerification:
    valid: bool
    schema_ok: bool
    signature_ok: bool
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid


def _utc_iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_quote(
    *,
    request_id: str,
    provider_pubkey: str,
    model_alias: str,
    price_units: str,
    input_per_1m: str,
    output_per_1m: str,
    max_output_tokens: int,
    max_price: str,
    issued_at: datetime,
    expires_at: datetime,
    privacy_mode: str | None = None,
) -> dict[str, Any]:
    """Build an unsigned quote dict ready for :func:`sign_quote`."""
    quote: dict[str, Any] = {
        "quote_version": QUOTE_VERSION,
        "request_id": request_id,
        "provider_pubkey": provider_pubkey,
        "model_alias": model_alias,
        "price_units": price_units,
        "input_per_1m": input_per_1m,
        "output_per_1m": output_per_1m,
        "max_output_tokens": max_output_tokens,
        "max_price": max_price,
        "issued_at": _utc_iso(issued_at),
        "expires_at": _utc_iso(expires_at),
    }
    if privacy_mode is not None:
        quote["privacy_mode"] = privacy_mode
    return quote


def sign_quote(quote: dict[str, Any], keypair: KeyPair) -> dict[str, Any]:
    """Return a signed copy of ``quote``."""
    return sign_document(quote, keypair)


def verify_quote(quote: dict[str, Any]) -> QuoteVerification:
    """Validate a quote against the schema and verify its provider signature."""
    errors = iter_errors("quote", quote)
    schema_ok = not errors
    signature_ok = verify_document(quote, pubkey_field="provider_pubkey")
    if not signature_ok:
        errors = [*errors, "signature: invalid or missing provider signature"]
    return QuoteVerification(
        valid=schema_ok and signature_ok,
        schema_ok=schema_ok,
        signature_ok=signature_ok,
        errors=errors,
    )


def quote_is_expired(quote: dict[str, Any], now: datetime) -> bool:
    """True if ``now`` is at or past the quote's ``expires_at`` (or it's malformed)."""
    raw = quote.get("expires_at")
    if not isinstance(raw, str):
        return True
    try:
        expires = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return True
    return now.astimezone(UTC) >= expires.astimezone(UTC)
