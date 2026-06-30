# SPDX-License-Identifier: Apache-2.0
"""Liveness probing for a discovered provider.

A :class:`HealthProbe` hits a provider's ``/sip/v1/health`` endpoint and checks
that it is reachable, that the public key it reports matches the *signed* manifest
(so a hijacked endpoint can't impersonate a provider), and that it still serves a
model the manifest advertises. The HTTP client and the clock are injected, so the
probe is fully unit-testable offline.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from sip_discovery import DiscoveredProvider

_HEALTH_PATH = "/sip/v1/health"
_TIMEOUT_S = 5.0


@dataclass(frozen=True, slots=True)
class HealthStatus:
    """The outcome of probing one provider's health endpoint."""

    reachable: bool
    pubkey_match: bool
    model_match: bool
    latency_ms: float | None = None

    @property
    def ok(self) -> bool:
        """True only if the node is live, the right identity, and serving a model."""
        return self.reachable and self.pubkey_match and self.model_match


class HealthProbe:
    """Probe a provider's ``/sip/v1/health`` for liveness and identity."""

    def __init__(self, *, client: httpx.Client | None = None, clock: Callable[[], float] = time.perf_counter) -> None:
        self._client = client
        self._clock = clock

    def check(self, provider: DiscoveredProvider) -> HealthStatus:
        owns = self._client is None
        client = self._client or httpx.Client(timeout=_TIMEOUT_S)
        start = self._clock()
        try:
            response = client.get(f"{provider.base_url}{_HEALTH_PATH}")
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError):
            return HealthStatus(reachable=False, pubkey_match=False, model_match=False, latency_ms=None)
        finally:
            if owns:
                client.close()
        latency_ms = (self._clock() - start) * 1000.0

        if not isinstance(body, dict):
            return HealthStatus(reachable=True, pubkey_match=False, model_match=False, latency_ms=latency_ms)
        pubkey_match = body.get("provider_pubkey") == provider.provider_pubkey
        live_models = body.get("models") or []
        model_match = bool(set(provider.models) & set(live_models)) if isinstance(live_models, list) else False
        return HealthStatus(
            reachable=True,
            pubkey_match=pubkey_match,
            model_match=model_match,
            latency_ms=latency_ms,
        )
