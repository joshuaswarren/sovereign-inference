# SPDX-License-Identifier: AGPL-3.0-or-later
"""sip-provider-gateway — Hardened provider gateway: auth, quotas, policy, payment validation, and receipt generation in front of a model runtime.

Public API:
    create_app  — build the configured FastAPI gateway app.
    serve       — run the app with uvicorn.
    Adapter     — the minimal runtime-adapter Protocol the gateway needs.
    MockAdapter — a deterministic, network-free adapter for tests and demos.
"""

from __future__ import annotations

from .app import Adapter, create_app, serve
from .mock import MockAdapter

__version__ = "0.1.2"

__all__ = [
    "Adapter",
    "MockAdapter",
    "__version__",
    "create_app",
    "serve",
]
