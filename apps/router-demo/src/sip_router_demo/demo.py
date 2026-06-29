# SPDX-License-Identifier: AGPL-3.0-or-later
"""End-to-end Sovereign Inference routing + failover demo.

This module wires the *real* :class:`sip_router.SovereignClient` against two
*real* :func:`sip_gateway.create_app` provider gateways running in-process over
an httpx ASGI transport — no sockets, no ports, no mocked business logic. Only
the network boundary is bridged.

What it proves, end to end:

1. A chat request is resolved to ranked providers, routed to the best one, and
   answered with a provider-signed receipt that
   :func:`sip_protocol.verify_receipt` accepts.
2. When the top-ranked provider goes down, the client transparently fails over
   to the next provider and still returns a verified receipt.

Run it with ``uv run sip-router-demo`` (or ``python -m sip_router_demo.demo``).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from typing import Any

import httpx

import sip_protocol
from sip_gateway import MockAdapter, create_app
from sip_protocol import KeyPair
from sip_router import NoProviderAvailable, ProviderEntry, ProviderRegistry, SovereignClient

MODEL = "qwen-coder-7b"
TOKEN = "demo-token"  # A non-secret bearer token shared by the demo gateways.

PROVIDER_A = "http://provider-a"
PROVIDER_B = "http://provider-b"


class _SyncASGITransport(httpx.BaseTransport):
    """Bridge a synchronous ``httpx.Client`` to an async ASGI app.

    The router speaks through a synchronous :class:`httpx.Client`, but
    :class:`httpx.ASGITransport` only exposes an async request path. This shim
    drives the ASGI app on a fresh event loop per request and materializes the
    response so it satisfies the sync client's ``SyncByteStream`` contract.
    """

    def __init__(self, app: Any) -> None:
        self._async = httpx.ASGITransport(app=app)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        async def _run() -> tuple[int, list[tuple[bytes, bytes]], bytes]:
            response = await self._async.handle_async_request(request)
            body = await response.aread()
            await response.aclose()
            return response.status_code, list(response.headers.raw), body

        status, headers, body = asyncio.run(_run())
        return httpx.Response(status_code=status, headers=headers, content=body, request=request)

    def close(self) -> None:
        """No persistent resources to release (a loop is spun up per request)."""


class _DownTransport(httpx.BaseTransport):
    """A transport for a provider that is hard-down: 503 on every route."""

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "service unavailable"}, request=request)

    def close(self) -> None:
        """No resources to release."""


def build_gateway_app(keypair: KeyPair, *, token: str | None = TOKEN) -> Any:
    """Build a real provider-gateway ASGI app backed by the deterministic mock adapter."""
    return create_app(
        adapter=MockAdapter(),
        keypair=keypair,
        allowed_models=[MODEL],
        token=token,
    )


def make_provider_entry(base_url: str, keypair: KeyPair) -> ProviderEntry:
    """Register a provider by fetching its signed manifest from the running gateway."""
    app = build_gateway_app(keypair)
    client = httpx.Client(transport=_SyncASGITransport(app), base_url=base_url)
    try:
        response = client.get("/sip/v1/provider-manifest")
        manifest: dict[str, Any] = response.json()
    finally:
        client.close()
    return ProviderEntry(base_url=base_url, manifest=manifest)


def sync_client_factory(apps: dict[str, Any]) -> Callable[[str], httpx.Client]:
    """A client_factory that maps each provider base_url to its in-process ASGI app."""

    def factory(base_url: str) -> httpx.Client:
        return httpx.Client(transport=_SyncASGITransport(apps[base_url]), base_url=base_url)

    return factory


def down_client_factory(apps: dict[str, Any], *, down: Iterable[str]) -> Callable[[str], httpx.Client]:
    """Like :func:`sync_client_factory`, but ``down`` base_urls answer 503 everywhere."""
    down_set = set(down)

    def factory(base_url: str) -> httpx.Client:
        if base_url in down_set:
            return httpx.Client(transport=_DownTransport(), base_url=base_url)
        return httpx.Client(transport=_SyncASGITransport(apps[base_url]), base_url=base_url)

    return factory


def build_client(registry: ProviderRegistry, client_factory: Callable[[str], httpx.Client]) -> SovereignClient:
    """Build the routing client wired to ``client_factory`` and the demo token."""
    return SovereignClient(registry, token=TOKEN, client_factory=client_factory)


def main() -> int:
    """Run the routing + failover demo, printing each proof step. Returns 0 on success."""
    print("=== Sovereign Inference: routing + failover demo ===")
    print(f"model: {MODEL}")

    kp_a = KeyPair.generate()
    kp_b = KeyPair.generate()
    apps: dict[str, Any] = {PROVIDER_A: build_gateway_app(kp_a), PROVIDER_B: build_gateway_app(kp_b)}

    registry = ProviderRegistry()
    registry.add(make_provider_entry(PROVIDER_A, kp_a))
    registry.add(make_provider_entry(PROVIDER_B, kp_b))
    print(f"registered providers: {PROVIDER_A} ({_short(kp_a)}), {PROVIDER_B} ({_short(kp_b)})")

    messages = [{"role": "user", "content": "In one sentence, what is sovereign inference?"}]

    # 1) Happy path: route to the best available provider.
    print("\n--- routing request (both providers healthy) ---")
    client = build_client(registry, sync_client_factory(apps))
    result = client.chat(MODEL, messages)
    served_by = "provider-a" if result.base_url == PROVIDER_A else "provider-b"
    print(f"served by: {result.base_url} ({served_by})")
    print(f"provider pubkey: {result.provider_pubkey}")
    print(f"response: {result.content!r}")
    if not sip_protocol.verify_receipt(result.receipt).valid:
        print("ERROR: receipt failed verification")
        return 1
    print("receipt verified: OK (signature + schema valid)")

    # 2) Failover: provider A goes hard-down (503 everywhere).
    print(f"\n--- {PROVIDER_A} goes DOWN; routing again ---")
    failover_client = build_client(registry, down_client_factory(apps, down={PROVIDER_A}))
    try:
        failover = failover_client.chat(MODEL, messages)
    except NoProviderAvailable as exc:  # pragma: no cover — defensive; B is healthy here.
        print(f"ERROR: no provider available: {exc}")
        return 1

    if failover.base_url != PROVIDER_B:
        print(f"ERROR: expected failover to {PROVIDER_B}, got {failover.base_url}")
        return 1
    print(f"attempts: {[(a['base_url'], a['outcome']) for a in failover.attempts]}")
    print(f"FAILED OVER to: {failover.base_url} (provider-b)")
    print(f"provider pubkey: {failover.provider_pubkey}")
    print(f"response: {failover.content!r}")
    if not sip_protocol.verify_receipt(failover.receipt).valid:
        print("ERROR: failover receipt failed verification")
        return 1
    print("receipt verified: OK (signature + schema valid)")

    print("\n=== demo complete: routed, verified, and failed over successfully ===")
    return 0


def _short(keypair: KeyPair) -> str:
    """A short, human-readable prefix of a provider pubkey for log lines."""
    return keypair.public_key_str[:18] + "..."


if __name__ == "__main__":
    raise SystemExit(main())
