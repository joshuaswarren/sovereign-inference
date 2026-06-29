# SPDX-License-Identifier: Apache-2.0
"""Generic detached-signature handling for SIP-AI documents.

Receipts and provider/model manifests share one signing rule: the signature
covers the canonical JSON of the document with the signature field removed.
This module implements that rule once so every document type is consistent.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .canonical import canonical_json
from .signing import KeyPair, verify

Document = Mapping[str, Any]


def signing_bytes(document: Document, *, signature_field: str = "signature") -> bytes:
    """Return the canonical bytes that a document's signature must cover."""
    unsigned = {k: v for k, v in document.items() if k != signature_field}
    return canonical_json(unsigned)


def sign_document(
    document: Document,
    keypair: KeyPair,
    *,
    signature_field: str = "signature",
) -> dict[str, Any]:
    """Return a copy of ``document`` with a detached signature attached."""
    signed = {k: v for k, v in document.items() if k != signature_field}
    signature = keypair.sign(signing_bytes(signed, signature_field=signature_field))
    signed[signature_field] = signature
    return signed


def verify_document(
    document: Document,
    *,
    pubkey_field: str,
    signature_field: str = "signature",
) -> bool:
    """Verify a document's detached signature against its embedded public key."""
    public_key = document.get(pubkey_field)
    signature = document.get(signature_field)
    if not isinstance(public_key, str) or not isinstance(signature, str):
        return False
    return verify(public_key, signing_bytes(document, signature_field=signature_field), signature)
