# SPDX-License-Identifier: Apache-2.0
"""Tests for the provider-selection policy."""

from __future__ import annotations

from typing import Any

from sip_policy import Policy
from sip_protocol import (
    KeyPair,
    build_attestation,
    build_provider_manifest,
    sign_attestation,
    sign_provider_manifest,
)
from sip_protocol.attestation import attach_attestation


def _manifest(
    keypair: KeyPair,
    *,
    models: list[str] | None = None,
    unit: str = "usdc",
    input_per_1m: float = 0.2,
    output_per_1m: float = 0.6,
    privacy_modes: list[str] | None = None,
    attested: bool = False,
    tee_type: str = "intel-tdx",
) -> dict[str, Any]:
    manifest = build_provider_manifest(
        provider_pubkey=keypair.public_key_str,
        models=models or ["qwen-coder-7b"],
        runtime_adapters=["vllm"],
        pricing_unit=unit,
        input_per_1m=input_per_1m,
        output_per_1m=output_per_1m,
        privacy_modes=privacy_modes or ["direct"],
        published_at="2026-06-30T00:00:00Z",
        manifest_uri="https://node.example",
    )
    if attested:
        attestation = sign_attestation(
            build_attestation(
                provider_pubkey=keypair.public_key_str,
                tee_type=tee_type,
                measurement="sha256:" + "ab" * 32,
                issued_at="2026-06-30T00:00:00Z",
            ),
            keypair,
        )
        manifest = attach_attestation(manifest, attestation)
    return sign_provider_manifest(manifest, keypair)


# -- empty policy ---------------------------------------------------------------


def test_empty_policy_permits_everything() -> None:
    kp = KeyPair.generate()
    assert Policy().permits(_manifest(kp)).ok is True


# -- attestation ----------------------------------------------------------------


def test_require_attestation_rejects_unattested() -> None:
    kp = KeyPair.generate()
    policy = Policy(require_attestation=True, accepted_tee_types=("intel-tdx",))
    assert policy.permits(_manifest(kp, attested=False)).ok is False
    decision = policy.permits(_manifest(kp, attested=True, tee_type="intel-tdx"))
    assert decision.ok is True


def test_require_attestation_rejects_wrong_tee_type() -> None:
    kp = KeyPair.generate()
    policy = Policy(require_attestation=True, accepted_tee_types=("intel-tdx",))
    assert policy.permits(_manifest(kp, attested=True, tee_type="aws-nitro")).ok is False


# -- price caps -----------------------------------------------------------------


def test_price_cap_rejects_too_expensive() -> None:
    kp = KeyPair.generate()
    policy = Policy(max_input_per_1m=0.5, max_output_per_1m=1.0)
    assert policy.permits(_manifest(kp, input_per_1m=0.2, output_per_1m=0.6)).ok is True
    assert policy.permits(_manifest(kp, input_per_1m=0.9, output_per_1m=0.6)).ok is False
    assert policy.permits(_manifest(kp, input_per_1m=0.2, output_per_1m=5.0)).ok is False


def test_accepted_units_filters_by_currency() -> None:
    kp = KeyPair.generate()
    policy = Policy(accepted_units=("usdc",))
    assert policy.permits(_manifest(kp, unit="usdc")).ok is True
    assert policy.permits(_manifest(kp, unit="pic")).ok is False


# -- privacy modes --------------------------------------------------------------


def test_required_privacy_modes_must_be_advertised() -> None:
    kp = KeyPair.generate()
    policy = Policy(required_privacy_modes=("relay",))
    assert policy.permits(_manifest(kp, privacy_modes=["direct"])).ok is False
    assert policy.permits(_manifest(kp, privacy_modes=["direct", "relay"])).ok is True


# -- allow / deny ---------------------------------------------------------------


def test_deny_list_blocks_provider() -> None:
    kp = KeyPair.generate()
    policy = Policy(deny_providers=(kp.public_key_str,))
    decision = policy.permits(_manifest(kp))
    assert decision.ok is False
    assert "deny" in decision.reason


def test_allow_list_excludes_others() -> None:
    allowed, other = KeyPair.generate(), KeyPair.generate()
    policy = Policy(allow_providers=(allowed.public_key_str,))
    assert policy.permits(_manifest(allowed)).ok is True
    assert policy.permits(_manifest(other)).ok is False


# -- reputation -----------------------------------------------------------------


def test_min_reputation_uses_injected_score() -> None:
    kp = KeyPair.generate()
    policy = Policy(min_reputation=0.7)
    assert policy.permits(_manifest(kp), reputation_score=0.9).ok is True
    assert policy.permits(_manifest(kp), reputation_score=0.5).ok is False
    assert policy.permits(_manifest(kp), reputation_score=None).ok is False  # unknown == fails the floor


# -- filter_entries -------------------------------------------------------------


def test_filter_entries_keeps_only_permitted() -> None:
    cheap, pricey = KeyPair.generate(), KeyPair.generate()

    class _Entry:
        def __init__(self, manifest: dict[str, Any]) -> None:
            self.manifest = manifest

    entries = [_Entry(_manifest(cheap, input_per_1m=0.1)), _Entry(_manifest(pricey, input_per_1m=9.0))]
    policy = Policy(max_input_per_1m=1.0)
    kept = policy.filter_entries(entries)
    assert len(kept) == 1
    assert kept[0].manifest["provider_pubkey"] == cheap.public_key_str


def test_require_attestation_default_excludes_none_tee_type() -> None:
    # require_attestation with no explicit tee types must NOT accept a self-signed
    # tee_type="none" attestation (that would defeat the requirement).
    kp = KeyPair.generate()
    policy = Policy(require_attestation=True)  # no accepted_tee_types
    assert policy.permits(_manifest(kp, attested=True, tee_type="none")).ok is False
    assert policy.permits(_manifest(kp, attested=True, tee_type="intel-tdx")).ok is True
