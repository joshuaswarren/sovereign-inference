# SPDX-License-Identifier: AGPL-3.0-or-later
"""Router error types."""

from __future__ import annotations

from typing import Any


class SovereignRouterError(Exception):
    """Base class for all sip_router errors."""


class NoProviderAvailable(SovereignRouterError):
    """Raised when every candidate provider failed to serve a request.

    Carries the per-candidate ``attempts`` so callers can inspect *why* routing
    failed (each attempt is ``{"base_url": str, "outcome": str}``).
    """

    def __init__(self, model: str, attempts: list[dict[str, Any]]) -> None:
        self.model = model
        self.attempts = attempts
        if attempts:
            detail = ", ".join(f"{a['base_url']} ({a['outcome']})" for a in attempts)
            message = f"no provider could serve model {model!r}; tried: {detail}"
        else:
            message = f"no provider in the registry serves model {model!r}"
        super().__init__(message)
