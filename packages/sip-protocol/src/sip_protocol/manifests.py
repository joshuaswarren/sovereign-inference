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

_DEFAULT_PRIVACY_MODES = ["direct"]


def build_provider_manifest(
    *,
    provider_pubkey: str,
    models: list[str],
    runtime_adapters: list[str],
    pricing_unit: str,
    published_at: str,
    input_per_1m: float = 0.0,
    output_per_1m: float = 0.0,
    node_type: str = "sovereign-node",
    max_context: int = 4096,
    max_concurrency: int | None = None,
    logging_policy: str = "no_prompt_logging",
    retention_policy: str | None = None,
    privacy_modes: list[str] | None = None,
    benchmark: dict[str, Any] | None = None,
    manifest_uri: str | None = None,
) -> dict[str, Any]:
    """Assemble an unsigned ``sip-ai.provider_manifest.v1`` dict.

    A reusable builder for any provider — a local Sovereign Inference Node
    (``sovereign-node``), an external-compute adapter, a relay. Optional fields
    are omitted entirely when not given so the manifest stays minimal. Pass the
    result to :func:`sign_provider_manifest` to sign it.
    """
    manifest: dict[str, Any] = {
        "schema": PROVIDER_MANIFEST_SCHEMA,
        "provider_pubkey": provider_pubkey,
        "node_type": node_type,
        "models": list(models),
        "runtime_adapters": list(runtime_adapters),
        "pricing": {
            "unit": pricing_unit,
            "input_per_1m": input_per_1m,
            "output_per_1m": output_per_1m,
        },
        "max_context": max_context,
        "logging_policy": logging_policy,
        "privacy_modes": list(privacy_modes) if privacy_modes is not None else list(_DEFAULT_PRIVACY_MODES),
        "published_at": published_at,
    }
    if max_concurrency is not None:
        manifest["max_concurrency"] = max_concurrency
    if retention_policy is not None:
        manifest["retention_policy"] = retention_policy
    if benchmark is not None:
        manifest["benchmark"] = dict(benchmark)
    if manifest_uri is not None:
        manifest["manifest_uri"] = manifest_uri
    return manifest


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
