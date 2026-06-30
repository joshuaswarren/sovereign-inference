# SPDX-License-Identifier: Apache-2.0
"""Rank discovered providers by reputation, liveness, and advertised speed.

:func:`rank_providers` blends a provider's persisted reputation with an optional
live health probe: unreachable nodes (when probed) are dropped, and the rest are
ordered by reputation score, then by latency, then by advertised throughput — so
a router can route to the best *live* provider.
"""

from __future__ import annotations

from dataclasses import dataclass

from sip_discovery import DiscoveredProvider

from .health import HealthProbe, HealthStatus
from .store import ReputationScore, ReputationStore


@dataclass(frozen=True, slots=True)
class RankedProvider:
    """A discovered provider with its reputation, health, and composite score."""

    provider: DiscoveredProvider
    reputation: ReputationScore
    score: float
    health: HealthStatus | None = None


def _advertised_tps(provider: DiscoveredProvider) -> float:
    benchmark = provider.manifest.get("benchmark")
    if isinstance(benchmark, dict):
        try:
            return float(benchmark.get("tokens_per_second", 0.0))
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _latency_for(reputation: ReputationScore, health: HealthStatus | None) -> float:
    if health is not None and health.latency_ms is not None:
        return health.latency_ms
    if reputation.avg_latency_ms is not None:
        return reputation.avg_latency_ms
    return float("inf")


def rank_providers(
    providers: list[DiscoveredProvider],
    *,
    store: ReputationStore,
    probe: HealthProbe | None = None,
) -> list[RankedProvider]:
    """Return ``providers`` ranked best-first; drop unreachable ones when probed."""
    ranked: list[RankedProvider] = []
    for provider in providers:
        reputation = store.score(provider.provider_pubkey)
        health = probe.check(provider) if probe is not None else None
        if health is not None and not health.ok:
            continue  # never route to a dead or hijacked node
        ranked.append(RankedProvider(provider=provider, reputation=reputation, score=reputation.score, health=health))

    ranked.sort(
        key=lambda r: (
            -r.score,
            _latency_for(r.reputation, r.health),
            -_advertised_tps(r.provider),
        )
    )
    return ranked
