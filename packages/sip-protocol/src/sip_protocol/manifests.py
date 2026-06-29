# SPDX-License-Identifier: Apache-2.0
"""Model and provider manifests.

Provider manifests carry an embedded ``provider_pubkey`` and a detached
``signature`` over the canonical manifest, exactly like receipts. Model
manifests are validated and content-addressed (via ``model_manifest_hash`` in
receipts); maintainer signing is left to a later spec revision.
"""

from __future__ import annotations

from typing import Any

from .canonical import canonical_json
from .documents import sign_document, verify_document
from .hashing import sha256_prefixed
from .schemas import iter_errors, validate
from .signing import KeyPair

MODEL_MANIFEST_SCHEMA = "sip-ai.model_manifest.v1"
PROVIDER_MANIFEST_SCHEMA = "sip-ai.provider_manifest.v1"


def model_manifest_hash(manifest: dict[str, Any]) -> str:
    """Content-address a model manifest as ``sha256:<hex>`` of its canonical form.

    The ``maintainer_signature`` field (if present) is excluded so the hash is
    stable whether or not the manifest has been signed.
    """
    unsigned = {k: v for k, v in manifest.items() if k != "maintainer_signature"}
    return sha256_prefixed(canonical_json(unsigned))


def validate_model_manifest(manifest: dict[str, Any]) -> None:
    validate("model_manifest", manifest)


def sign_provider_manifest(manifest: dict[str, Any], keypair: KeyPair) -> dict[str, Any]:
    """Sign a provider manifest with the provider's key pair."""
    return sign_document(manifest, keypair)


def verify_provider_manifest(manifest: dict[str, Any]) -> bool:
    """Validate schema and verify the provider manifest signature."""
    if iter_errors("provider_manifest", manifest):
        return False
    return verify_document(manifest, pubkey_field="provider_pubkey")
