# SPDX-License-Identifier: AGPL-3.0-or-later
"""A hosted SIP-AI provider directory: announce over HTTP, discover over HTTP.

The service is a thin FastAPI over any :class:`sip_discovery.Directory` store, so
it inherits the store's guarantees: **announce verifies the manifest signature**
(forged manifests are rejected with 400) and **discover returns only signed,
freshest-per-provider manifests**. Clients use ``sip_discovery.HttpDirectory``,
which re-verifies every manifest and routes only to the signed ``manifest_uri`` —
the relay is never trusted to redirect traffic.
"""

from __future__ import annotations

import argparse
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from sip_discovery import Directory, DiscoveryError, FileDirectory


def create_directory_app(store: Directory) -> FastAPI:
    """Build the directory-service FastAPI app backed by ``store``."""
    app = FastAPI(title="SIP-AI Directory Service")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/directory/announce")
    async def announce(request: Request) -> JSONResponse:
        try:
            manifest = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({"error": "body must be a JSON provider manifest"}, status_code=400)
        if not isinstance(manifest, dict):
            return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
        try:
            ref = store.announce(manifest)
        except DiscoveryError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse({"ref": ref})

    @app.get("/directory/providers")
    def providers(model: str | None = None) -> JSONResponse:
        found = store.discover(model=model)
        return JSONResponse({"providers": [p.manifest for p in found]})

    return app


def run() -> int:  # pragma: no cover - serves until interrupted
    """Console-script entry point: run the directory service with uvicorn."""
    import uvicorn

    parser = argparse.ArgumentParser(prog="sip-directory-service", description="Hosted SIP-AI provider directory.")
    parser.add_argument("--store", default="directory.json", help="path to the FileDirectory store JSON")
    parser.add_argument("--host", default="127.0.0.1", help="bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8088, help="bind port (default 8088)")
    args = parser.parse_args()
    app: Any = create_directory_app(FileDirectory(args.store))
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
