# SPDX-License-Identifier: AGPL-3.0-or-later
"""Local status API for the SIN dashboard (FastAPI).

A small, localhost-only HTTP surface the dashboard polls for node state:
hardware scan, model catalog, recommendations, and liveness. Everything that
touches the real machine is injected into :func:`create_app` (the hardware
``scan``, the ``recommend`` engine, and the ``catalog`` loader) so tests pass
deterministic fakes and the function stays pure and verifiable.

The serving entrypoint (:func:`serve`) wraps uvicorn and is never exercised by
tests. If a built dashboard exists at ``apps/dashboard/dist`` it is mounted at
``/`` *after* the API routes so the SPA never shadows ``/api/*``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__, hardware
from . import recommend as recommend_module
from .adapter import available_adapter_names
from .catalog import load_catalog
from .models import CatalogModel, HardwareProfile, Recommendation

# Injectable dependencies. Defaults touch the real system/catalog; tests pass fakes.
ScanFn = Callable[[], HardwareProfile]
RecommendFn = Callable[..., list[Recommendation]]
CatalogFn = Callable[[], list[CatalogModel]]

# Built dashboard location: <repo>/apps/dashboard/dist relative to this file.
# api.py -> sin_node -> src -> sin-node -> packages -> <repo>
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DASHBOARD_DIST = _REPO_ROOT / "apps" / "dashboard" / "dist"

# CORS for a localhost-bound dashboard dev server / SPA. Permissive on localhost
# only; the node never binds to a public interface without explicit opt-in.
_ALLOW_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def create_app(
    *,
    scan: ScanFn = hardware.scan,
    recommend: RecommendFn = recommend_module.recommend,
    catalog: CatalogFn = load_catalog,
) -> FastAPI:
    """Build the FastAPI app, wiring in the injected node services.

    All node-state endpoints live under ``/api``. CORS is enabled for localhost
    origins. A built dashboard, if present, is mounted last at ``/``.
    """
    app = FastAPI(title="Sovereign Inference Node", version=__version__)

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=_ALLOW_ORIGIN_REGEX,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """Liveness probe: always cheap, never touches hardware."""
        return {"status": "ok", "version": __version__}

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        """Node summary: version and the registered runtime adapter names."""
        return {"version": __version__, "adapters": available_adapter_names()}

    @app.get("/api/scan")
    def scan_endpoint() -> dict[str, Any]:
        """Run the hardware profiler and return the JSON-encoded profile."""
        return scan().model_dump(mode="json")

    @app.get("/api/catalog")
    def catalog_endpoint() -> list[dict[str, Any]]:
        """Return the curated model catalog as JSON-encoded catalog models."""
        return [model.model_dump(mode="json") for model in catalog()]

    @app.get("/api/recommend")
    def recommend_endpoint(
        task: str = Query(..., description="Target task, e.g. coding or general-chat."),
        commercial: bool = Query(False, description="Require a commercial-use license."),
        top: int = Query(3, ge=1, le=50, description="Maximum number of recommendations."),
    ) -> list[dict[str, Any]]:
        """Scan the machine, then rank recommendations for ``task``."""
        profile = scan()
        recs = recommend(profile, task, commercial_required=commercial, top_k=top)
        return [rec.model_dump(mode="json") for rec in recs]

    _mount_dashboard(app)
    return app


def _mount_dashboard(app: FastAPI) -> None:
    """Mount the built SPA at ``/`` if it exists, leaving ``/api/*`` intact.

    Mounted last so the explicit API routes are matched first; the static mount
    only catches paths the API did not claim. A missing build is a no-op.
    """
    if _DASHBOARD_DIST.is_dir() and (_DASHBOARD_DIST / "index.html").is_file():
        app.mount("/", StaticFiles(directory=str(_DASHBOARD_DIST), html=True), name="dashboard")


def serve(host: str = "127.0.0.1", port: int = 8009) -> None:  # pragma: no cover
    """Run the API with uvicorn. Localhost-bound by default; not used in tests."""
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port)
