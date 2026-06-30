# SPDX-License-Identifier: Apache-2.0
"""Tests for TEE attestation statements and the attested-provider policy."""

from __future__ import annotations

from sip_protocol import (
    KeyPair,
    build_provider_manifest,
    sign_provider_manifest,
    verify_provider_manifest,
)
from sip_protocol.attestation import (
    attach_attestation,
    build_attestation,
    is_attested,
    sign_attestation,
    verify_attestation,
)


def _attestation(keypair: KeyPair, *, tee_type: str = "intel-tdx") -> dict:
    return sign_attestation(
        build_attestation(
            provider_pubkey=keypair.public_key_str,
            tee_type=tee_type,
            measurement="sha256:" + "ab" * 32,
            issued_at="2026-06-30T00:00:00Z",
            quote_ref="ar://quote-tx",
        ),
        keypair,
    )


def _manifest_with_attestation(keypair: KeyPair, attestation: dict) -> dict:
    manifest = build_provider_manifest(
        provider_pubkey=keypair.public_key_str,
        models=["qwen-coder-7b"],
        runtime_adapters=["vllm"],
        pricing_unit="usdc",
        published_at="2026-06-30T00:00:00Z",
        manifest_uri="https://node.example/sip",
    )
    return sign_provider_manifest(attach_attestation(manifest, attestation), keypair)


# -- attestation artifact -------------------------------------------------------


def test_attestation_sign_and_verify() -> None:
    kp = KeyPair.generate()
    assert verify_attestation(_attestation(kp)) is True


def test_attestation_tamper_detected() -> None:
    kp = KeyPair.generate()
    statement = _attestation(kp)
    statement["measurement"] = "sha256:" + "00" * 32
    assert verify_attestation(statement) is False


def test_attestation_schema_rejects_unknown_tee_type() -> None:
    kp = KeyPair.generate()
    statement = sign_attestation(
        {
            "schema": "sip-ai.attestation.v1",
            "provider_pubkey": kp.public_key_str,
            "tee_type": "magic-box",  # not in the enum
            "measurement": "sha256:" + "ab" * 32,
            "issued_at": "2026-06-30T00:00:00Z",
        },
        kp,
    )
    assert verify_attestation(statement) is False


# -- manifest binding -----------------------------------------------------------


def test_attached_attestation_keeps_manifest_signature_valid() -> None:
    kp = KeyPair.generate()
    manifest = _manifest_with_attestation(kp, _attestation(kp))
    assert verify_provider_manifest(manifest) is True
    assert "attestation" in manifest


# -- is_attested policy ---------------------------------------------------------


def test_is_attested_true_for_valid_matching_attestation() -> None:
    kp = KeyPair.generate()
    manifest = _manifest_with_attestation(kp, _attestation(kp, tee_type="intel-tdx"))
    assert is_attested(manifest, accepted_tee_types=["intel-tdx", "amd-sev-snp"]) is True


def test_is_attested_false_when_no_attestation() -> None:
    kp = KeyPair.generate()
    manifest = sign_provider_manifest(
        build_provider_manifest(
            provider_pubkey=kp.public_key_str,
            models=["m"],
            runtime_adapters=["vllm"],
            pricing_unit="usdc",
            published_at="2026-06-30T00:00:00Z",
            manifest_uri="https://x",
        ),
        kp,
    )
    assert is_attested(manifest, accepted_tee_types=["intel-tdx"]) is False


def test_is_attested_false_when_tee_type_not_accepted() -> None:
    kp = KeyPair.generate()
    manifest = _manifest_with_attestation(kp, _attestation(kp, tee_type="aws-nitro"))
    assert is_attested(manifest, accepted_tee_types=["intel-tdx"]) is False


def test_is_attested_false_when_attestation_pubkey_mismatches_manifest() -> None:
    # An attestation signed by a different key (impersonation) must not pass.
    kp, other = KeyPair.generate(), KeyPair.generate()
    manifest = build_provider_manifest(
        provider_pubkey=kp.public_key_str,
        models=["m"],
        runtime_adapters=["vllm"],
        pricing_unit="usdc",
        published_at="2026-06-30T00:00:00Z",
        manifest_uri="https://x",
    )
    foreign_attestation = _attestation(other)  # valid, but for `other`, not `kp`
    signed = sign_provider_manifest(attach_attestation(manifest, foreign_attestation), kp)
    assert is_attested(signed, accepted_tee_types=["intel-tdx"]) is False


def test_is_attested_honours_hardware_verifier() -> None:
    kp = KeyPair.generate()
    manifest = _manifest_with_attestation(kp, _attestation(kp))
    assert is_attested(manifest, accepted_tee_types=["intel-tdx"], verifier=lambda _a: False) is False
    assert is_attested(manifest, accepted_tee_types=["intel-tdx"], verifier=lambda _a: True) is True
