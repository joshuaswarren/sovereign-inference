# SPDX-License-Identifier: AGPL-3.0-or-later
"""The unified desktop app server: one origin, three surfaces.

A single FastAPI app the desktop window talks to:

* **OpenAI surface** (``/v1/*``, ``/healthz``) — the local LLM endpoint.
* **Node status** (``/api/status``, ``/api/scan``, ``/api/recommend``) — what the
  Phase-1 dashboard panels read.
* **Onboarding admin** (``/api/config``, ``/api/providers``, ``/api/directory``,
  ``/api/runtimes``, ``/api/local-use``, ``/api/onboarding/complete``) — the
  first-run flow: choose a local runtime and/or connect to network providers.

The routing backend is held mutably and **rebuilt live** on every config change,
so adding a provider or starting a local model takes effect with no restart. All
config is persisted (atomically) to the OS app-data dir and restored on boot —
including re-fronting the chosen local model. Mutating ``/api`` routes require a
per-install admin token (injected by the desktop shell); the trust boundary in
:mod:`sip_openai_proxy.sources` ensures only validly-signed providers bound to
their signed ``manifest_uri`` are ever routed to.
"""

from __future__ import annotations

import hmac
import os
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from sin_node import __version__ as node_version
from sin_node import hardware
from sin_node import recommend as recommend_module
from sin_node.adapter import available_adapter_names
from sin_node.catalog import load_catalog
from sip_discovery import Directory
from sip_router import ProviderRegistry, in_process_client

from .app import ProxyBackend, build_backend, mount_proxy_routes
from .config import AppConfig, LocalUse, load_config, save_config
from .local_use import LocalProvider, RuntimeStatus, default_adapters, detect_runtimes, front_local_model
from .sources import UntrustedProvider, build_registry, is_safe_remote_url, merge_provider, trusted_provider_entry

# Injectable node services (defaults touch the real machine; tests pass fakes).
ScanFn = Callable[[], Any]
RecommendFn = Callable[..., Any]
CatalogFn = Callable[[], Any]
DetectFn = Callable[[], list[RuntimeStatus]]
StartLocalFn = Callable[[str, str], LocalProvider]

# Only the app's own origins may call the API. Ports are bounded to 1-65535 so the
# pattern can't admit a malformed/over-range origin.
_PORT = r"(6553[0-5]|655[0-2]\d|65[0-4]\d{2}|6[0-4]\d{3}|[1-5]\d{4}|[1-9]\d{0,3})"
_ALLOW_ORIGIN_REGEX = (
    r"^(tauri://localhost|https://tauri\.localhost|https?://(localhost|127\.0\.0\.1)(:" + _PORT + r")?)$"
)
_REMOTE_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


class LocalUseError(RuntimeError):
    """Raised when a local runtime cannot be fronted (missing/down/no model)."""


def _default_start_local(runtime: str, model: str) -> LocalProvider:
    for adapter in default_adapters():
        if adapter.name == runtime:
            if not adapter.is_available():
                raise LocalUseError(f"runtime {runtime!r} is not available — is its server running?")
            return front_local_model(model, adapter=adapter)
    raise LocalUseError(f"no installed runtime named {runtime!r}")


class _AddProvider(BaseModel):
    model_config = ConfigDict(extra="ignore")
    manifest: dict[str, Any]
    base_url: str | None = None


class _AddDirectory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    spec: str


class _StartLocal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    runtime: str
    model: str


class _ServerState:
    """Holds the live config, the in-process local provider, and the routing backend."""

    def __init__(
        self,
        config_dir: Path,
        start_local: StartLocalFn,
        directory_for: Callable[[str], Directory] | None = None,
    ) -> None:
        self._dir = config_dir
        self._start_local = start_local
        self._directory_for = directory_for
        self.config: AppConfig = load_config(config_dir)
        self.local: LocalProvider | None = None
        # Two warning sources, tracked separately: a boot-time local-restore failure
        # (sticky until the local model changes), and per-rebuild source warnings
        # (always recomputed from the *current* config). snapshot() unions them.
        self._restore_warning: str | None = None
        self._build_warnings: list[str] = []
        self.backend: ProxyBackend = build_backend(ProviderRegistry())
        self._restore_local()
        self.rebuild()

    def _client_factory(self, base_url: str) -> httpx.Client:
        if self.local is not None and base_url == self.local.entry.base_url:
            return in_process_client(self.local.app, base_url)
        return httpx.Client(base_url=base_url, timeout=_REMOTE_TIMEOUT)

    def _restore_local(self) -> None:
        self._restore_warning = None
        if self.config.local_use is None:
            self.local = None
            return
        try:
            self.local = self._start_local(self.config.local_use.runtime, self.config.local_use.model)
        except Exception as exc:  # a model that won't start on boot is a warning, not a crash
            self.local = None
            self._restore_warning = f"local model {self.config.local_use.model!r} could not be restored: {exc}"

    def rebuild(self) -> None:
        registry, warnings = build_registry(self.config, directory_for=self._directory_for)
        if self.local is not None:
            registry.add(self.local.entry)
        self.backend = build_backend(registry, token=self.config.token, client_factory=self._client_factory)
        self._build_warnings = warnings

    @property
    def warnings(self) -> list[str]:
        """All current warnings: the sticky local-restore warning plus build ones."""
        return ([self._restore_warning] if self._restore_warning else []) + self._build_warnings

    def persist(self) -> None:
        save_config(self._dir, self.config)

    def snapshot(self) -> dict[str, Any]:
        providers = [
            {
                "provider_pubkey": e.manifest["provider_pubkey"],
                "base_url": e.base_url,
                "models": e.manifest.get("models", []),
            }
            for e in self.config.providers
        ]
        local = (
            {"runtime": self.config.local_use.runtime, "model": self.config.local_use.model}
            if self.config.local_use
            else None
        )
        return {
            "onboarding_complete": self.config.onboarding_complete,
            "providers": providers,
            "directories": list(self.config.directories),
            "models": self.backend.models,
            "local_use": local,
            "warnings": self.warnings,
        }


def create_app_server(
    config_dir: str | Path,
    *,
    admin_token: str | None = None,
    proxy_api_key: str | None = None,
    scan: ScanFn = hardware.scan,
    recommend: RecommendFn = recommend_module.recommend,
    catalog: CatalogFn = load_catalog,
    detect: DetectFn = detect_runtimes,
    start_local: StartLocalFn = _default_start_local,
    directory_for: Callable[[str], Directory] | None = None,
    dashboard_dir: str | Path | None = None,
) -> FastAPI:
    """Build the unified desktop app server rooted at ``config_dir``."""
    state = _ServerState(Path(config_dir), start_local, directory_for)
    app = FastAPI(title="Sovereign Inference — desktop app server")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=_ALLOW_ORIGIN_REGEX,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # OpenAI surface (/healthz, /v1/*) over the live backend.
    mount_proxy_routes(app, lambda: state.backend, api_key=proxy_api_key)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": node_version}

    def _require_token(x_sovereign_token: Annotated[str | None, Header()] = None) -> None:
        if admin_token is None:
            return
        presented = (x_sovereign_token or "").encode("utf-8")
        if not hmac.compare_digest(presented, admin_token.encode("utf-8")):
            raise HTTPException(status_code=401, detail="missing or invalid admin token")

    api = APIRouter(prefix="/api", dependencies=[Depends(_require_token)])

    # -- node status (read-only) ------------------------------------------------

    @api.get("/status")
    def status() -> dict[str, Any]:
        return {"version": node_version, "adapters": available_adapter_names()}

    @api.get("/scan")
    def scan_endpoint() -> dict[str, Any]:
        profile: dict[str, Any] = scan().model_dump(mode="json")
        return profile

    @api.get("/catalog")
    def catalog_endpoint() -> list[dict[str, Any]]:
        return [m.model_dump(mode="json") for m in catalog()]

    @api.get("/recommend")
    def recommend_endpoint(
        task: str = Query(..., description="Target task, e.g. coding or general-chat."),
        commercial: bool = Query(False),
        top: int = Query(3, ge=1, le=50),
    ) -> list[dict[str, Any]]:
        recs = recommend(scan(), task, commercial_required=commercial, top_k=top)
        return [r.model_dump(mode="json") for r in recs]

    @api.get("/runtimes")
    def runtimes() -> list[dict[str, Any]]:
        return [{"name": s.name, "available": s.available, "models": list(s.models)} for s in detect()]

    # -- onboarding state + mutations -------------------------------------------

    @api.get("/config")
    def get_config() -> dict[str, Any]:
        return state.snapshot()

    @api.post("/onboarding/complete")
    def complete_onboarding() -> dict[str, Any]:
        state.config = replace(state.config, onboarding_complete=True)
        state.persist()
        state.rebuild()  # refresh warnings/backend against the final config
        return state.snapshot()

    @api.post("/providers")
    def add_provider(body: _AddProvider) -> dict[str, Any]:
        try:
            entry = trusted_provider_entry(body.manifest, base_url=body.base_url)
            merged = merge_provider(state.config.providers, entry)
        except UntrustedProvider as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state.config = replace(state.config, providers=merged)
        state.persist()
        state.rebuild()
        return state.snapshot()

    @api.delete("/providers/{pubkey}")
    def remove_provider(pubkey: str) -> dict[str, Any]:
        remaining = tuple(e for e in state.config.providers if e.manifest.get("provider_pubkey") != pubkey)
        state.config = replace(state.config, providers=remaining)
        state.persist()
        state.rebuild()
        return state.snapshot()

    @api.post("/directory")
    def add_directory(body: _AddDirectory) -> dict[str, Any]:
        spec = body.spec
        if spec.startswith(("http://", "https://")) and not is_safe_remote_url(spec):
            raise HTTPException(status_code=400, detail=f"directory URL {spec!r} is not a safe public endpoint")
        if spec not in state.config.directories:  # adding a known spec is a no-op (no re-fetch)
            state.config = replace(state.config, directories=(*state.config.directories, spec))
            state.persist()
            state.rebuild()
        return state.snapshot()

    @api.delete("/directory")
    def remove_directory(spec: str = Query(...)) -> dict[str, Any]:
        if spec in state.config.directories:  # removing an unknown spec is a no-op
            state.config = replace(state.config, directories=tuple(d for d in state.config.directories if d != spec))
            state.persist()
            state.rebuild()
        return state.snapshot()

    @api.post("/local-use")
    def start_local_use(body: _StartLocal) -> dict[str, Any]:
        try:
            local = start_local(body.runtime, body.model)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"could not start local model: {exc}") from exc
        state.local = local
        state.config = replace(state.config, local_use=LocalUse(runtime=body.runtime, model=body.model))
        state.persist()
        state.rebuild()
        return state.snapshot()

    @api.delete("/local-use")
    def stop_local_use() -> dict[str, Any]:
        state.local = None
        state.config = replace(state.config, local_use=None)
        state.persist()
        state.rebuild()
        return state.snapshot()

    app.include_router(api)
    _mount_dashboard(app, dashboard_dir)
    return app


def _resolve_dashboard_dir(explicit: str | Path | None) -> Path:
    """Locate the built dashboard, working both from source and a frozen bundle."""
    if explicit is not None:
        return Path(explicit)
    env = os.environ.get("SIP_DASHBOARD_DIR")
    if env:
        return Path(env)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / "dashboard"
        if bundled.is_dir():
            return bundled
    # source-tree fallback: apps/dashboard/dist
    return Path(__file__).resolve().parents[3] / "dashboard" / "dist"


def _mount_dashboard(app: FastAPI, dashboard_dir: str | Path | None) -> None:
    """Mount the built SPA at ``/`` if present (so a browser can use the app too)."""
    directory = _resolve_dashboard_dir(dashboard_dir)
    if directory.is_dir() and (directory / "index.html").is_file():
        app.mount("/", StaticFiles(directory=str(directory), html=True), name="dashboard")


def _generate_token() -> str:
    import secrets

    return secrets.token_urlsafe(24)


def _pid_alive(pid: int) -> bool:
    """True if process ``pid`` exists (signal 0 probes without delivering)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists but not ours to signal
    return True


def watch_parent_once(
    parent_pid: int,
    *,
    is_alive: Callable[[int], bool] = _pid_alive,
    on_dead: Callable[[], None],
) -> bool:
    """Check the parent once; fire ``on_dead`` and return False if it is gone.

    The desktop shell can die by a signal or crash without Tauri's graceful-exit
    hook running, which would orphan this sidecar. Watching the parent PID makes
    the sidecar exit no matter *how* the app went away.
    """
    if is_alive(parent_pid):
        return True
    on_dead()
    return False


def _watch_parent_forever(parent_pid: int, *, interval: float = 2.0) -> None:  # pragma: no cover - real loop
    import threading
    import time

    def _loop() -> None:
        while watch_parent_once(parent_pid, on_dead=lambda: os._exit(0)):
            time.sleep(interval)

    thread = threading.Thread(target=_loop, name="parent-watch", daemon=True)
    thread.start()


def run() -> int:  # pragma: no cover - serves until interrupted
    """Console entry point: serve the unified app server from CLI flags."""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(prog="sip-app-server", description="Sovereign Inference desktop app server.")
    parser.add_argument("--config-dir", required=True, help="OS app-data dir for persisted config")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11435)
    parser.add_argument("--admin-token", help="token required on mutating /api routes (default: generated)")
    parser.add_argument("--proxy-api-key", help="optional bearer key required from OpenAI clients on /v1")
    parser.add_argument("--parent-pid", type=int, help="exit when this process (the desktop shell) is gone")
    args = parser.parse_args()

    if args.parent_pid:
        _watch_parent_forever(args.parent_pid)

    token = args.admin_token or _generate_token()
    app = create_app_server(args.config_dir, admin_token=token, proxy_api_key=args.proxy_api_key)
    # Emit the token on stdout so the desktop shell can inject it into the webview.
    print(f"SOVEREIGN_ADMIN_TOKEN={token}", flush=True)
    print(f"Sovereign Inference app server on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
