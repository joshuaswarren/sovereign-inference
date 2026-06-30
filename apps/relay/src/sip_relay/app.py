# SPDX-License-Identifier: AGPL-3.0-or-later
"""The SIP-AI privacy relay server.

``POST /sip/v1/relay`` takes ``{target: {base_url, manifest}, completion}`` and
forwards ``completion`` to the target provider's ``/v1/chat/completions``, so the
provider's gateway sees the relay's connection, not the client's. The relay only
forwards to a target whose manifest **verifies**, whose ``base_url`` equals the
signed ``manifest_uri``, and whose address is not private/loopback/link-local
(a basic SSRF guard). A self-signed manifest is not a trust anchor, so a production
relay should also gate on a trusted provider set / signed directory. The relay does
not (and need not) trust itself for integrity: the provider's signed receipt — over
both response and request — lets the client detect tampering and substitution.
"""

from __future__ import annotations

import argparse
import ipaddress
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from sip_protocol import verify_provider_manifest

ClientFactory = Callable[[str], httpx.Client]
_FORWARD_TIMEOUT_S = 60.0

# Hostnames that commonly front internal services / cloud metadata.
_BLOCKED_HOSTNAMES = {"localhost", "metadata", "metadata.google.internal"}


def _is_safe_forward_url(base_url: str) -> bool:
    """Reject obvious SSRF targets: loopback/private/link-local/metadata addresses.

    Blocks IP literals in private/loopback/link-local/reserved ranges and a few
    well-known internal hostnames. Public hostnames are allowed (a deeper guard —
    DNS resolution + rebinding protection — is future work, noted in the README).
    """
    try:
        host = urlsplit(base_url).hostname
    except ValueError:
        return False
    if not host:
        return False
    lowered = host.lower()
    if lowered in _BLOCKED_HOSTNAMES or lowered.endswith(".localhost"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True  # a non-literal hostname; allowed at this layer
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def default_client_factory(base_url: str) -> httpx.Client:
    """Production factory: an httpx client bound to the provider's base URL."""
    return httpx.Client(base_url=base_url, timeout=_FORWARD_TIMEOUT_S)


def create_relay_app(*, client_factory: ClientFactory = default_client_factory) -> FastAPI:
    """Build the relay FastAPI app. ``client_factory`` maps a base_url to a client."""
    app = FastAPI(title="SIP-AI Privacy Relay")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/sip/v1/relay")
    async def relay(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        target = body.get("target") if isinstance(body, dict) else None
        completion = body.get("completion") if isinstance(body, dict) else None
        if not isinstance(target, dict) or not isinstance(completion, dict):
            return JSONResponse({"error": "expected {target, completion}"}, status_code=400)

        manifest = target.get("manifest")
        base_url = target.get("base_url")
        if not isinstance(manifest, dict) or not isinstance(base_url, str):
            return JSONResponse({"error": "target needs base_url + manifest"}, status_code=400)
        if not verify_provider_manifest(manifest):
            return JSONResponse({"error": "target manifest does not verify"}, status_code=400)
        if base_url != manifest.get("manifest_uri"):
            return JSONResponse({"error": "base_url does not match the signed manifest_uri"}, status_code=400)
        if not _is_safe_forward_url(base_url):
            return JSONResponse({"error": "refusing to forward to a private/loopback address"}, status_code=400)

        client = client_factory(base_url)
        try:
            upstream = client.post("/v1/chat/completions", json=completion)
        except httpx.HTTPError as exc:
            return JSONResponse({"error": f"upstream provider unreachable: {exc}"}, status_code=502)
        try:
            payload: Any = upstream.json()
        except ValueError:
            payload = {"error": "provider returned non-JSON"}
        # Forward the provider's response verbatim (including a 402 challenge), so
        # the reactive payment flow works transparently through the relay.
        return JSONResponse(payload, status_code=upstream.status_code)

    return app


def run() -> int:  # pragma: no cover - serves until interrupted
    """Console-script entry point: run the relay with uvicorn."""
    import uvicorn

    parser = argparse.ArgumentParser(prog="sip-relay", description="A SIP-AI privacy relay.")
    parser.add_argument("--host", default="127.0.0.1", help="bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8099, help="bind port (default 8099)")
    args = parser.parse_args()
    uvicorn.run(create_relay_app(), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
