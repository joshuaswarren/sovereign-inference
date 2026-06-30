# SPDX-License-Identifier: Apache-2.0
"""Signed inference receipts.

A receipt is an *accountability artifact*, not a cryptographic proof that a
specific model produced a specific answer. It binds together: who served the
request (provider public key), what was claimed (model manifest hash, runtime),
what it cost, and a hash of the response — all under a provider signature.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .documents import sign_document, signing_bytes, verify_document
from .schemas import iter_errors
from .signing import KeyPair

RECEIPT_VERSION = "sip-ai.receipt.v1"


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of verifying a receipt: schema validity AND signature validity."""

    valid: bool
    schema_ok: bool
    signature_ok: bool
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid


def _utc_iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_receipt(
    *,
    request_id: str,
    provider_pubkey: str,
    model_manifest_hash: str,
    model_alias: str,
    runtime: str,
    input_tokens: int,
    output_tokens: int,
    price_units: str,
    price_amount: str,
    privacy_mode: str,
    started_at: datetime,
    completed_at: datetime,
    response_hash: str,
    runtime_version: str | None = None,
    request_hash: str | None = None,
) -> dict[str, Any]:
    """Build an unsigned receipt dict ready to pass to :func:`sign_receipt`."""
    receipt: dict[str, Any] = {
        "receipt_version": RECEIPT_VERSION,
        "request_id": request_id,
        "provider_pubkey": provider_pubkey,
        "model_manifest_hash": model_manifest_hash,
        "model_alias": model_alias,
        "runtime": runtime,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "price_units": price_units,
        "price_amount": price_amount,
        "privacy_mode": privacy_mode,
        "started_at": _utc_iso(started_at),
        "completed_at": _utc_iso(completed_at),
        "response_hash": response_hash,
    }
    if runtime_version is not None:
        receipt["runtime_version"] = runtime_version
    if request_hash is not None:
        receipt["request_hash"] = request_hash
    return receipt


def sign_receipt(receipt: dict[str, Any], keypair: KeyPair) -> dict[str, Any]:
    """Return a signed copy of ``receipt`` (signature over canonical fields)."""
    return sign_document(receipt, keypair)


def receipt_signing_bytes(receipt: dict[str, Any]) -> bytes:
    """Expose the exact bytes a receipt signature covers (for debugging/tools)."""
    return signing_bytes(receipt)


def verify_receipt(receipt: dict[str, Any]) -> VerificationResult:
    """Validate a receipt against the schema and verify its provider signature."""
    errors = iter_errors("receipt", receipt)
    schema_ok = not errors
    signature_ok = verify_document(receipt, pubkey_field="provider_pubkey")
    if not signature_ok:
        errors = [*errors, "signature: invalid or missing provider signature"]
    return VerificationResult(
        valid=schema_ok and signature_ok,
        schema_ok=schema_ok,
        signature_ok=signature_ok,
        errors=errors,
    )
