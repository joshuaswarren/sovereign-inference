# SPDX-License-Identifier: Apache-2.0
"""TEE attestation statements and the attested-provider selection policy.

A ``sip-ai.attestation.v1`` statement binds a TEE type and a code/enclave
``measurement`` to a provider's public key, signed by that provider key. The
optional ``quote_ref`` points to a raw hardware attestation quote (e.g. an Intel
DCAP quote); verifying that quote against a hardware root of trust is a separate,
pluggable step injected as ``verifier`` — so this module is fully testable
offline, and operators plug in real DCAP/SEV verification in production.

The statement is also embedded into the provider manifest (``attestation`` field)
so it travels with discovery and is covered by the manifest signature.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .documents import sign_document, verify_document
from .schemas import iter_errors
from .signing import KeyPair

ATTESTATION_SCHEMA = "sip-ai.attestation.v1"
TEE_TYPES = ("intel-tdx", "amd-sev-snp", "nvidia-cc", "aws-nitro", "none")

# A hardware-quote verifier: given an attestation statement, confirm its raw
# quote against a hardware root of trust (DCAP, SEV-SNP, ...). Injected.
QuoteVerifier = Callable[[dict[str, Any]], bool]


def build_attestation(
    *,
    provider_pubkey: str,
    tee_type: str,
    measurement: str,
    issued_at: str,
    quote_ref: str | None = None,
) -> dict[str, Any]:
    """Assemble an unsigned ``sip-ai.attestation.v1`` statement."""
    statement: dict[str, Any] = {
        "schema": ATTESTATION_SCHEMA,
        "provider_pubkey": provider_pubkey,
        "tee_type": tee_type,
        "measurement": measurement,
        "issued_at": issued_at,
    }
    if quote_ref is not None:
        statement["quote_ref"] = quote_ref
    return statement


def sign_attestation(statement: dict[str, Any], keypair: KeyPair) -> dict[str, Any]:
    """Sign an attestation statement with the provider's key pair."""
    return sign_document(statement, keypair)


def verify_attestation(statement: dict[str, Any]) -> bool:
    """Validate the schema and verify the statement's provider signature."""
    if iter_errors("attestation", statement):
        return False
    return verify_document(statement, pubkey_field="provider_pubkey")


def attach_attestation(manifest: dict[str, Any], attestation: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``manifest`` with ``attestation`` embedded (sign after)."""
    return {**manifest, "attestation": attestation}


def is_attested(
    manifest: dict[str, Any],
    *,
    accepted_tee_types: list[str],
    verifier: QuoteVerifier | None = None,
) -> bool:
    """True if the manifest carries a valid attestation the policy accepts.

    Requires: a schema-valid, signature-verified attestation whose
    ``provider_pubkey`` matches the manifest's (no impersonation), whose
    ``tee_type`` is accepted, and — if a ``verifier`` is supplied — whose
    hardware quote passes that verifier.
    """
    attestation = manifest.get("attestation")
    if not isinstance(attestation, dict):
        return False
    if not verify_attestation(attestation):
        return False
    if attestation.get("provider_pubkey") != manifest.get("provider_pubkey"):
        return False
    if attestation.get("tee_type") not in set(accepted_tee_types):
        return False
    return verifier is None or verifier(attestation)
