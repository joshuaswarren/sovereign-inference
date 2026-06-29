# SPDX-License-Identifier: AGPL-3.0-or-later
"""End-to-end Sovereign Inference DISCOVERY demo (announce → discover → route).

This proves the supply side joins the network *without manual registry editing*:
a node publishes its signed provider manifest to a :class:`~sip_discovery.Directory`,
and a router **discovers** it from that directory, builds its registry, and routes
a real request to the discovered endpoint — getting back a verified receipt.

Only the network boundary is bridged (the node's gateway runs in-process over an
httpx ASGI transport); the directory, the signed manifest, the verification, and
the routing are all the real thing. The directory here is a :class:`FileDirectory`
(``local://`` of discovery); in production this is an :class:`ArweaveDirectory`.

Run it with ``uv run sip-discovery-demo``.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sip_protocol
from sip_discovery import FileDirectory
from sip_gateway import MockAdapter, create_app
from sip_protocol import KeyPair, build_provider_manifest, sign_provider_manifest
from sip_router import ProviderEntry, ProviderRegistry

from .demo import MODEL, TOKEN, build_client, sync_client_factory

# The public URL the node advertises in its manifest (== the directory base_url).
NODE_URL = "http://discovered-node"
INPUT_PER_1M = 0.20
OUTPUT_PER_1M = 0.60
PRICING_UNIT = "usdc"
DEMO_PROMPT = "In one sentence, what is sovereign inference?"


@dataclass(frozen=True, slots=True)
class DiscoveryDemoResult:
    """What a discovery-demo run produced (for tests and callers)."""

    exit_code: int
    discovered_count: int
    served_by: str
    receipt_verified: bool


def build_shared_node() -> tuple[KeyPair, dict[str, Any], Any]:
    """Build a node identity, its signed provider manifest, and its gateway app.

    The manifest carries ``manifest_uri = NODE_URL`` so discovery knows where to
    route; the gateway is configured with the same manifest and price.
    """
    keypair = KeyPair.generate()
    manifest = sign_provider_manifest(
        build_provider_manifest(
            provider_pubkey=keypair.public_key_str,
            models=[MODEL],
            runtime_adapters=["llama.cpp"],
            pricing_unit=PRICING_UNIT,
            input_per_1m=INPUT_PER_1M,
            output_per_1m=OUTPUT_PER_1M,
            node_type="sovereign-node",
            max_context=8192,
            manifest_uri=NODE_URL,
            published_at=datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
        keypair,
    )
    app = create_app(
        adapter=MockAdapter(),
        keypair=keypair,
        allowed_models=[MODEL],
        token=TOKEN,
        price_units=PRICING_UNIT,
        input_per_1m=str(INPUT_PER_1M),
        output_per_1m=str(OUTPUT_PER_1M),
        provider_manifest=manifest,
    )
    return keypair, manifest, app


def main(*, directory_path: str | None = None) -> DiscoveryDemoResult:
    """Run the discovery demo, printing each proof step."""
    if directory_path is None:
        directory_path = str(Path(tempfile.mkdtemp(prefix="sip-directory-")) / "providers.json")
    directory = FileDirectory(directory_path)

    print("=== Sovereign Inference: DISCOVERY demo (announce → discover → route) ===")
    print(f"model: {MODEL}  directory: {directory_path}")

    # --- (1) a node announces its signed manifest to the directory ------------
    _keypair, manifest, node_app = build_shared_node()
    ref = directory.announce(manifest)
    print("\n--- node announces itself ---")
    print(f"provider: {manifest['provider_pubkey'][:18]}...  (node_type=sovereign-node)")
    print(f"announced to directory as: {ref}")

    # --- (2) a router discovers providers for the model -----------------------
    print("\n--- router discovers providers ---")
    discovered = directory.discover(model=MODEL)
    print(f"discovered {len(discovered)} verified provider(s) serving {MODEL!r}")
    if not discovered:
        print("ERROR: no providers discovered")
        return DiscoveryDemoResult(1, 0, "", False)
    for provider in discovered:
        print(f"  - {provider.base_url}  ({provider.provider_pubkey[:18]}...)")

    # --- (3) build a registry from discovery and route a real request ---------
    registry = ProviderRegistry()
    for provider in discovered:
        registry.add(ProviderEntry(base_url=provider.base_url, manifest=provider.manifest))

    print("\n--- routing a request to a discovered node ---")
    client = build_client(registry, sync_client_factory({NODE_URL: node_app}))
    result = client.chat(MODEL, [{"role": "user", "content": DEMO_PROMPT}])
    print(f"served by: {result.base_url}")
    print(f"response:  {result.content!r}")

    verified = sip_protocol.verify_receipt(result.receipt).valid
    if not verified:
        print("ERROR: receipt failed verification")
        return DiscoveryDemoResult(1, len(discovered), result.base_url, False)
    print("receipt verified: OK (signature + schema valid)")

    print("\n=== demo complete: announced, discovered, routed, verified ===")
    return DiscoveryDemoResult(
        exit_code=0,
        discovered_count=len(discovered),
        served_by=result.base_url,
        receipt_verified=verified,
    )


def run() -> int:
    """Console-script entry point: run the demo and return its exit code."""
    return main().exit_code


if __name__ == "__main__":
    raise SystemExit(run())
