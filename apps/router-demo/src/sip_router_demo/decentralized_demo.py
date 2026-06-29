# SPDX-License-Identifier: AGPL-3.0-or-later
"""End-to-end Sovereign Inference DECENTRALIZED (Phase 4) demo.

This wires the *real* external-compute adapter
(:class:`sip_provider_nosana.NosanaProvider`), the *real*
:func:`sip_compute.provider_manifest_for` signing helper, the *real*
:class:`sip_router.SovereignClient`, and the *real* :mod:`sip_arweave` anchoring
layer. Only two boundaries are bridged in-process so the demo is deterministic
and offline:

* the Nosana **CLI** is faked (``fake_nosana_cli``) so ``deploy``/``await_ready``
  resolve to a node URL without a wallet or the GPU network, and
* that node URL is served by a **real** :func:`sip_gateway.create_app` gateway
  over an httpx ASGI transport (no sockets) — i.e. exactly the SIP gateway image
  a Nosana/Akash container would run.

What it proves, end to end:

1. **Provisioning.** The Nosana adapter posts a job and polls it to ``RUNNING``,
   yielding a reachable endpoint.
2. **Signed advertisement.** ``provider_manifest_for`` turns that endpoint into a
   signed ``external-adapter`` provider manifest.
3. **Durable provenance.** The manifest is anchored to storage (``local://`` here,
   ``ar://`` in production) and resolved back, verified.
4. **Routing.** The router routes a real chat request to the provisioned node and
   gets a provider-signed receipt that :func:`sip_protocol.verify_receipt` accepts.
5. **Receipt anchoring.** The signed receipt is anchored too, so anyone can audit
   the inference after the node is long gone.

Run it with ``uv run sip-decentralized-demo``.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx

import sip_protocol
from sip_arweave import Anchor, LocalAnchor, anchor_manifest, anchor_receipt
from sip_compute import Deployment, InferenceSpec, provider_manifest_for
from sip_gateway import MockAdapter, create_app
from sip_protocol import KeyPair
from sip_provider_nosana import NosanaProvider
from sip_router import ProviderEntry, ProviderRegistry

from .demo import (
    MODEL,
    TOKEN,
    _SyncASGITransport,
    build_client,
    sync_client_factory,
)

# The URL the "provisioned" Nosana node serves its SIP gateway at. In production
# this is whatever the Nosana job exposes; here it maps to an in-process app.
NODE_URL = "http://sin-node-nosana"
MARKET = "nvidia-3090"
GATEWAY_IMAGE = "ghcr.io/sovereign-inference/sip-gateway:latest"
DEMO_PROMPT = "In one sentence, what is sovereign inference?"

# Realistic advertised pricing for a decentralized GPU node (USDC per 1M tokens).
INPUT_PER_1M = 0.20
OUTPUT_PER_1M = 0.60
PRICING_UNIT = "usdc"


def build_node_gateway(provider_kp: KeyPair) -> Any:
    """Build the SIP gateway the provisioned node runs, priced in USDC to match
    what the external-adapter manifest advertises."""
    return create_app(
        adapter=MockAdapter(),
        keypair=provider_kp,
        allowed_models=[MODEL],
        token=TOKEN,
        price_units=PRICING_UNIT,
        input_per_1m=str(INPUT_PER_1M),
        output_per_1m=str(OUTPUT_PER_1M),
    )


def fake_nosana_cli(node_url: str) -> Any:
    """A Nosana CLI stand-in: posts a job, then reports it RUNNING at ``node_url``.

    This replaces the ``nosana`` binary + wallet so the demo runs offline. The
    adapter's real logic (job-definition build, state mapping, endpoint
    extraction, polling) all runs unchanged against this canned output.
    """
    job_id = "JOB_DEMO_1"

    def run(argv: Sequence[str]) -> str:
        joined = " ".join(argv)
        if "job post" in joined:
            return json.dumps({"job": job_id, "state": "QUEUED"})
        if "job get" in joined:
            return json.dumps({"job": job_id, "state": "RUNNING", "serviceUrl": node_url})
        if "job stop" in joined:
            return "stopped"
        return "{}"

    return run


def provision_node(node_url: str = NODE_URL) -> Deployment:
    """Provision a Nosana inference node and block until it is ready."""
    provider = NosanaProvider(market=MARKET, run=fake_nosana_cli(node_url), sleep=lambda _s: None)
    spec = InferenceSpec(
        model=MODEL,
        image=GATEWAY_IMAGE,
        port=8080,
        input_per_1m=INPUT_PER_1M,
        output_per_1m=OUTPUT_PER_1M,
        pricing_unit="usdc",
    )
    deployment = provider.deploy(spec)
    return provider.await_ready(deployment)


@dataclass(frozen=True, slots=True)
class DemoResult:
    """The artifacts a decentralized-demo run produces (for tests and callers)."""

    exit_code: int
    manifest_uri: str
    receipt_uri: str
    input_tokens: int
    output_tokens: int
    endpoint: str


def _served_manifest(app: Any, base_url: str) -> dict[str, Any]:
    """Fetch a gateway's served provider manifest over the in-process transport."""
    client = httpx.Client(transport=_SyncASGITransport(app), base_url=base_url)
    try:
        manifest: dict[str, Any] = client.get("/sip/v1/provider-manifest").json()
    finally:
        client.close()
    return manifest


def main(*, anchor: Anchor | None = None) -> DemoResult:
    """Run the decentralized demo, printing each proof step.

    ``anchor`` defaults to a throwaway :class:`~sip_arweave.LocalAnchor`; pass an
    :class:`~sip_arweave.ArweaveAnchor` (with a submitter) to anchor for real.
    """
    if anchor is None:
        anchor = LocalAnchor(tempfile.mkdtemp(prefix="sip-anchor-"))

    print("=== Sovereign Inference: DECENTRALIZED routing + anchoring demo ===")
    print(f"model: {MODEL}")
    print(f"market: {MARKET}  image: {GATEWAY_IMAGE}")

    # --- (1) provision an external GPU node via the Nosana adapter -------------
    print("\n--- provisioning a node on Nosana (job post -> poll -> RUNNING) ---")
    deployment = provision_node()
    if not deployment.is_ready:
        print("ERROR: node did not reach a ready state")
        return DemoResult(1, "", "", 0, 0, "")
    print(f"job id:   {deployment.id}")
    print(f"endpoint: {deployment.endpoint}  (status={deployment.status})")

    # The node runs a real SIP gateway; its signing key is the provider identity.
    provider_kp = KeyPair.generate()
    node_app = build_node_gateway(provider_kp)

    # --- (2) build & anchor the signed external-adapter provider manifest ------
    print("\n--- advertising the node as a signed SIP provider ---")
    manifest = provider_manifest_for(
        deployment,
        keypair=provider_kp,
        models=[MODEL],
        input_per_1m=INPUT_PER_1M,
        output_per_1m=OUTPUT_PER_1M,
        pricing_unit=PRICING_UNIT,
        max_context=8192,
    )
    if not sip_protocol.verify_provider_manifest(manifest):
        print("ERROR: provider manifest failed verification")
        return DemoResult(1, "", "", 0, 0, deployment.endpoint or "")
    manifest_uri = anchor_manifest(anchor, manifest)
    print(f"provider: {provider_kp.public_key_str[:18]}...  (node_type=external-adapter)")
    print(f"manifest anchored at: {manifest_uri}")

    # --- (3) route a real request to the provisioned node ---------------------
    print("\n--- routing a request to the decentralized node ---")
    registry = ProviderRegistry()
    registry.add(ProviderEntry(base_url=NODE_URL, manifest=manifest))
    client = build_client(registry, sync_client_factory({NODE_URL: node_app}))
    result = client.chat(MODEL, [{"role": "user", "content": DEMO_PROMPT}])
    print(f"served by: {result.base_url}")
    print(f"response:  {result.content!r}")

    receipt = result.receipt
    if not sip_protocol.verify_receipt(receipt).valid:
        print("ERROR: receipt failed verification")
        return DemoResult(1, manifest_uri, "", 0, 0, deployment.endpoint or "")
    print("receipt verified: OK (signature + schema valid)")

    # --- (4) anchor the signed receipt for permanent auditability -------------
    receipt_uri = anchor_receipt(anchor, receipt)
    print(f"receipt anchored at: {receipt_uri}")

    input_tokens = int(receipt["input_tokens"])
    output_tokens = int(receipt["output_tokens"])
    print("\n--- reproducible metrics ---")
    print(f"  provider_pubkey : {receipt['provider_pubkey']}")
    print(f"  endpoint        : {deployment.endpoint}")
    print(f"  input_tokens    : {input_tokens}")
    print(f"  output_tokens   : {output_tokens}")
    print(f"  price           : {receipt['price_amount']} {receipt['price_units']}")
    print(f"  manifest_uri    : {manifest_uri}")
    print(f"  receipt_uri     : {receipt_uri}")

    print("\n=== demo complete: provisioned, advertised, anchored, routed, verified ===")
    return DemoResult(
        exit_code=0,
        manifest_uri=manifest_uri,
        receipt_uri=receipt_uri,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        endpoint=deployment.endpoint or "",
    )


def run() -> int:
    """Console-script entry point: run the demo and return its exit code."""
    return main().exit_code


if __name__ == "__main__":
    raise SystemExit(run())
