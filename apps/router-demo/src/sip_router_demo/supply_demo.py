# SPDX-License-Identifier: AGPL-3.0-or-later
"""End-to-end Sovereign Inference SUPPLY demo — the full provider lifecycle.

Ties together the three supply-onboarding follow-ons:

1. **Hosted directory** — a node announces its signed manifest to a relay
   (``sip_directory_service.create_directory_app``) over HTTP, and a router
   discovers it with ``sip_discovery.HttpDirectory``.
2. **Health + reputation** — the router probes each provider's liveness and ranks
   by reputation (``sip_reputation``), routing only to the best *live* node.
3. **Auto re-announce** — after the node re-benchmarks, it re-announces a fresh
   manifest and the directory surfaces the updated metrics.

Everything runs in-process over httpx ASGI transports (no sockets); only the
network boundary is bridged. Run it with ``uv run sip-supply-demo``.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

import sip_protocol
from sip_directory_service import create_directory_app
from sip_discovery import FileDirectory, HttpDirectory
from sip_gateway import MockAdapter, create_app
from sip_protocol import KeyPair, build_provider_manifest, sign_provider_manifest
from sip_reputation import HealthProbe, ReputationStore, rank_providers
from sip_router import ProviderEntry, ProviderRegistry

from .demo import MODEL, TOKEN, _SyncASGITransport, build_client, sync_client_factory

NODE_URL = "http://supply-node"
DIRECTORY_URL = "http://directory"
INPUT_PER_1M = 0.20
OUTPUT_PER_1M = 0.60
PRICING_UNIT = "usdc"
INITIAL_TPS = 30.0
REBENCH_TPS = 55.0


def _node_manifest(keypair: KeyPair, *, tps: float, published_at: str) -> dict[str, Any]:
    return sign_provider_manifest(
        build_provider_manifest(
            provider_pubkey=keypair.public_key_str,
            models=[MODEL],
            runtime_adapters=["llama.cpp"],
            pricing_unit=PRICING_UNIT,
            input_per_1m=INPUT_PER_1M,
            output_per_1m=OUTPUT_PER_1M,
            node_type="sovereign-node",
            max_context=8192,
            benchmark={"tokens_per_second": tps, "ttft_ms": 500},
            manifest_uri=NODE_URL,
            published_at=published_at,
        ),
        keypair,
    )


def _asgi_client(app: Any, base_url: str) -> httpx.Client:
    return httpx.Client(transport=_SyncASGITransport(app), base_url=base_url)


@dataclass(frozen=True, slots=True)
class SupplyDemoResult:
    exit_code: int
    discovered_count: int
    served_by: str
    receipt_verified: bool
    recorded_samples: int
    fresh_tps: float


def main(*, directory_store: str | None = None, reputation_store: str | None = None) -> SupplyDemoResult:
    """Run the full supply loop, printing each proof step."""
    if directory_store is None:
        directory_store = str(Path(tempfile.mkdtemp(prefix="sip-dir-")) / "directory.json")
    if reputation_store is None:
        reputation_store = str(Path(tempfile.mkdtemp(prefix="sip-rep-")) / "reputation.json")

    print("=== Sovereign Inference: SUPPLY demo (hosted directory + reputation + re-announce) ===")
    print(f"model: {MODEL}")

    # The node: identity, initial manifest, and a real gateway serving it.
    provider_kp = KeyPair.generate()
    manifest = _node_manifest(provider_kp, tps=INITIAL_TPS, published_at="2026-06-30T00:00:00Z")
    node_app = create_app(
        adapter=MockAdapter(),
        keypair=provider_kp,
        allowed_models=[MODEL],
        token=TOKEN,
        price_units=PRICING_UNIT,
        input_per_1m=str(INPUT_PER_1M),
        output_per_1m=str(OUTPUT_PER_1M),
        provider_manifest=manifest,
    )

    # The hosted directory (relay) and a client that speaks to it.
    directory_app = create_directory_app(FileDirectory(directory_store))
    directory = HttpDirectory(DIRECTORY_URL, client=_asgi_client(directory_app, DIRECTORY_URL))

    # --- (1) node announces to the hosted directory ---------------------------
    print("\n--- node announces to the hosted directory ---")
    directory.announce(manifest)
    print(f"announced {provider_kp.public_key_str[:18]}... to {DIRECTORY_URL}")

    # --- (2) router discovers, then health + reputation rank ------------------
    print("\n--- router discovers + ranks by health and reputation ---")
    discovered = directory.discover(model=MODEL)
    if not discovered:
        print("ERROR: nothing discovered")
        return SupplyDemoResult(1, 0, "", False, 0, 0.0)
    probe = HealthProbe(client=_asgi_client(node_app, NODE_URL))
    store = ReputationStore(reputation_store)
    ranked = rank_providers(discovered, store=store, probe=probe)
    if not ranked:
        print("ERROR: all discovered providers failed health checks")
        return SupplyDemoResult(1, len(discovered), "", False, 0, 0.0)
    best = ranked[0]
    print(f"discovered {len(discovered)}, top live provider {best.provider.base_url} (score {best.score:.2f})")

    # --- (3) route to the best provider, verify the receipt -------------------
    print("\n--- routing to the top-ranked provider ---")
    registry = ProviderRegistry()
    registry.add(ProviderEntry(base_url=best.provider.base_url, manifest=best.provider.manifest))
    client = build_client(registry, sync_client_factory({NODE_URL: node_app}))
    chat = client.chat(MODEL, [{"role": "user", "content": "what is sovereign inference?"}])
    verified = sip_protocol.verify_receipt(chat.receipt).valid
    print(f"served by: {chat.base_url}  receipt verified: {'OK' if verified else 'FAILED'}")
    if not verified:
        return SupplyDemoResult(1, len(discovered), chat.base_url, False, 0, 0.0)

    # --- (4) record the outcome in the reputation store -----------------------
    latency = best.health.latency_ms if best.health else None
    store.record(best.provider.provider_pubkey, success=True, latency_ms=latency, receipt_valid=verified)
    samples = store.score(best.provider.provider_pubkey).samples
    print(f"recorded outcome — provider now has {samples} reputation sample(s)")

    # --- (5) the node re-benchmarks and re-announces --------------------------
    print("\n--- node re-benchmarks and re-announces ---")
    refreshed = _node_manifest(provider_kp, tps=REBENCH_TPS, published_at="2026-06-30T01:00:00Z")
    directory.announce(refreshed)
    rediscovered = directory.discover(model=MODEL)
    fresh_tps = float(rediscovered[0].manifest["benchmark"]["tokens_per_second"])
    print(f"directory now advertises {fresh_tps:.0f} tok/s (was {INITIAL_TPS:.0f})")

    print("\n=== demo complete: announced, discovered, ranked, routed, recorded, re-announced ===")
    return SupplyDemoResult(
        exit_code=0,
        discovered_count=len(discovered),
        served_by=chat.base_url,
        receipt_verified=verified,
        recorded_samples=samples,
        fresh_tps=fresh_tps,
    )


def run() -> int:
    """Console-script entry point: run the demo and return its exit code."""
    return main().exit_code


if __name__ == "__main__":
    raise SystemExit(run())
