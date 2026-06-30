# SPDX-License-Identifier: AGPL-3.0-or-later
"""End-to-end Sovereign Inference PRIVACY demo (Phase 5).

Demonstrates the three privacy modes together, in-process and deterministic:

1. **TEE attestation** — the provider advertises a signed attestation binding an
   ``intel-tdx`` measurement to its key; a privacy-conscious client requires it
   (``is_attested``) and rejects a manifest whose attestation is for another key.
2. **Issuer-unlinkable credits** — a blind-signature credit is minted so the
   issuer signs a blinded serial it never sees in the clear, then redeemed once
   (double-spend blocked) — payer↔issuer unlinkability.
3. **Privacy relay** — the request is routed through a relay, so the provider
   sees the relay, not the client; the client still verifies the provider's
   signed receipt, and a tampering relay is detected.

Run it with ``uv run sip-privacy-demo``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

import sip_protocol
from sip_gateway import MockAdapter, create_app
from sip_pic import (
    BlindIssuer,
    SpentSet,
    blind_credit_request,
    finalize_blind_credit,
    redeem_blind_credit,
    verify_blind_credit,
)
from sip_protocol import (
    KeyPair,
    build_attestation,
    build_provider_manifest,
    is_attested,
    sign_attestation,
)
from sip_relay import create_relay_app, relay_chat
from sip_router import in_process_client as _client

from .demo import MODEL

NODE_URL = "http://attested-node"
RELAY_URL = "http://relay"
TEE_TYPE = "intel-tdx"
CREDIT = "0.03"


@dataclass(frozen=True, slots=True)
class PrivacyDemoResult:
    exit_code: int
    provider_attested: bool
    credit_unlinkable: bool
    double_spend_blocked: bool
    relayed_receipt_verified: bool
    tamper_detected: bool


def _attested_provider() -> tuple[KeyPair, dict[str, Any], Any]:
    keypair = KeyPair.generate()
    attestation = sign_attestation(
        build_attestation(
            provider_pubkey=keypair.public_key_str,
            tee_type=TEE_TYPE,
            measurement="sha256:" + "ab" * 32,
            issued_at="2026-06-30T00:00:00Z",
            quote_ref="ar://dcap-quote",
        ),
        keypair,
    )
    manifest = build_provider_manifest(
        provider_pubkey=keypair.public_key_str,
        models=[MODEL],
        runtime_adapters=["llama.cpp"],
        pricing_unit="test",
        published_at="2026-06-30T00:00:00Z",
        manifest_uri=NODE_URL,
    )
    manifest = sip_protocol.sign_provider_manifest({**manifest, "attestation": attestation}, keypair)
    app = create_app(
        adapter=MockAdapter(), keypair=keypair, allowed_models=[MODEL], token=None, provider_manifest=manifest
    )
    return keypair, manifest, app


def main() -> PrivacyDemoResult:
    """Run the privacy demo, printing each proof step."""
    print("=== Sovereign Inference: PRIVACY demo (attestation + blind credit + relay) ===")
    print(f"model: {MODEL}")

    # --- (1) require a TEE-attested provider ----------------------------------
    print("\n--- requiring a TEE-attested provider ---")
    _kp, manifest, node_app = _attested_provider()
    attested = is_attested(manifest, accepted_tee_types=[TEE_TYPE, "amd-sev-snp"])
    print(f"provider attestation ({TEE_TYPE}): {'ACCEPTED' if attested else 'REJECTED'}")
    if not attested:
        return PrivacyDemoResult(1, False, False, False, False, False)

    # --- (2) mint and spend an issuer-unlinkable credit -----------------------
    print("\n--- minting an issuer-unlinkable blind credit ---")
    issuer = BlindIssuer.generate(key_size=1024)
    request, secret = blind_credit_request(issuer.public, unit="pic", amount=CREDIT)
    blinded_sig = issuer.sign_blinded(request.blinded)  # issuer never sees the serial
    credit = finalize_blind_credit(blinded_sig, secret)
    credit_unlinkable = verify_blind_credit(credit) and request.blinded != int.from_bytes(secret.token, "big")
    print(f"issuer signed only the blinded serial; credit valid: {verify_blind_credit(credit)}")

    spent = SpentSet()
    first = redeem_blind_credit(
        credit, price=CREDIT, unit="pic", issuer_keys=[issuer.public.pubkey_str()], spent_set=spent
    )
    replay = redeem_blind_credit(
        credit, price=CREDIT, unit="pic", issuer_keys=[issuer.public.pubkey_str()], spent_set=spent
    )
    double_spend_blocked = first.ok and not replay.ok and replay.reason == "double_spend"
    print(f"redeemed: {first.ok}; replay rejected: {not replay.ok} ({replay.reason})")

    # --- (3) route through a privacy relay ------------------------------------
    print("\n--- routing through a privacy relay (provider never sees the client) ---")
    relay_app = create_relay_app(client_factory=lambda base_url: _client(node_app, base_url))
    relay_client = _client(relay_app, RELAY_URL)
    target = {"base_url": NODE_URL, "manifest": manifest}
    completion = {"model": MODEL, "messages": [{"role": "user", "content": "what is sovereign inference?"}]}
    result = relay_chat(relay_client, target=target, completion=completion)
    print(f"relayed; receipt verified: {'OK' if result.verified else 'FAILED'}")

    # a relay that tampers with the answer is caught by the signed receipt
    def tamper(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "TAMPERED"}}],
                "sip_receipt": result.receipt,
            },
        )

    tampering_client = httpx.Client(transport=httpx.MockTransport(tamper), base_url=RELAY_URL)
    tampered = relay_chat(tampering_client, target=target, completion=completion)
    tamper_detected = not tampered.verified
    print(f"tampering relay detected: {tamper_detected}")

    ok = attested and credit_unlinkable and double_spend_blocked and result.verified and tamper_detected
    print(
        "\n=== demo complete: attested, unlinkably paid, relayed, integrity-checked ==="
        if ok
        else "\n=== demo FAILED ==="
    )
    return PrivacyDemoResult(
        exit_code=0 if ok else 1,
        provider_attested=attested,
        credit_unlinkable=credit_unlinkable,
        double_spend_blocked=double_spend_blocked,
        relayed_receipt_verified=result.verified,
        tamper_detected=tamper_detected,
    )


def run() -> int:
    """Console-script entry point: run the demo and return its exit code."""
    return main().exit_code


if __name__ == "__main__":
    raise SystemExit(run())
