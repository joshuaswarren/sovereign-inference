# SPDX-License-Identifier: Apache-2.0
"""sip_protocol — shared Sovereign Inference Protocol (SIP-AI) primitives.

Public API:
    Canonicalization & hashing: canonical_json, sha256_prefixed, hash_response_body
    Keys & signatures:          KeyPair, verify, encode_public_key, decode_public_key
    Documents:                  sign_document, verify_document, signing_bytes
    Receipts:                   build_receipt, sign_receipt, verify_receipt, VerificationResult
    Manifests:                  model_manifest_hash, sign_provider_manifest, verify_provider_manifest
    Schemas:                    validate, iter_errors, load_schema
"""

from __future__ import annotations

from .canonical import canonical_json
from .documents import sign_document, signing_bytes, verify_document
from .errors import (
    KeyEncodingError,
    SchemaValidationError,
    SignatureError,
    SIPProtocolError,
)
from .hashing import hash_response_body, sha256_prefixed
from .manifests import (
    model_manifest_hash,
    sign_provider_manifest,
    validate_model_manifest,
    verify_provider_manifest,
)
from .quotes import (
    QUOTE_VERSION,
    QuoteVerification,
    build_quote,
    quote_is_expired,
    sign_quote,
    verify_quote,
)
from .receipts import (
    RECEIPT_VERSION,
    VerificationResult,
    build_receipt,
    receipt_signing_bytes,
    sign_receipt,
    verify_receipt,
)
from .schemas import iter_errors, load_schema, validate
from .signing import (
    KeyPair,
    decode_public_key,
    encode_public_key,
    verify,
)

__version__ = "0.1.2"

__all__ = [
    "QUOTE_VERSION",
    "RECEIPT_VERSION",
    "KeyEncodingError",
    "KeyPair",
    "QuoteVerification",
    "SIPProtocolError",
    "SchemaValidationError",
    "SignatureError",
    "VerificationResult",
    "__version__",
    "build_quote",
    "build_receipt",
    "canonical_json",
    "decode_public_key",
    "encode_public_key",
    "hash_response_body",
    "iter_errors",
    "load_schema",
    "model_manifest_hash",
    "quote_is_expired",
    "receipt_signing_bytes",
    "sha256_prefixed",
    "sign_document",
    "sign_provider_manifest",
    "sign_quote",
    "sign_receipt",
    "signing_bytes",
    "validate",
    "validate_model_manifest",
    "verify",
    "verify_document",
    "verify_provider_manifest",
    "verify_quote",
    "verify_receipt",
]
