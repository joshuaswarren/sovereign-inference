# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deterministic provider scoring (spec 6.8 weighted blend) and ranking.

The score is a weighted sum of normalized sub-scores in ``[0, 1]``:

    provider_score =
        0.25 * model_fit
      + 0.20 * expected_latency
      + 0.15 * price
      + 0.15 * receipt_trust
      + 0.10 * uptime
      + 0.10 * privacy_mode_match

``geographic_or_jurisdiction_preference`` (0.05 in the spec) is opt-in and not
applied by default, so the active weights sum to 0.95. Reputation inputs
(receipt_trust, uptime) default to a neutral mid-value until a router has
observed history. All sub-scores are pure functions of the manifest plus the
optional measured-latency override, so scoring is deterministic.
"""

from __future__ import annotations

from typing import Any

from .models import ProviderEntry

DEFAULT_WEIGHTS: dict[str, float] = {
    "model_fit": 0.25,
    "expected_latency": 0.20,
    "price": 0.15,
    "receipt_trust": 0.15,
    "uptime": 0.10,
    "privacy_mode_match": 0.10,
}

# Neutral priors for reputation inputs a fresh router has not yet observed.
_DEFAULT_TRUST = 0.5
_DEFAULT_UPTIME = 0.5

# Latency normalization anchor: ~2s of effective latency maps to a low score.
_LATENCY_ANCHOR_MS = 2000.0
# Price normalization anchor: a blended per-1M rate at/above this maps near zero.
_PRICE_ANCHOR = 100.0


def _model_fit_score(entry: ProviderEntry, model_id: str | None) -> float:
    """1.0 when the provider serves the requested model (or any, if unspecified)."""
    models = entry.manifest.get("models") or []
    if model_id is None:
        return 1.0 if models else 0.0
    return 1.0 if model_id in models else 0.0


def _latency_score(entry: ProviderEntry, measured_latency_ms: float | None) -> float:
    """Higher is better. Lower effective latency -> score closer to 1.0."""
    if measured_latency_ms is not None:
        effective_ms = max(measured_latency_ms, 0.0)
    else:
        benchmark = entry.manifest.get("benchmark") or {}
        ttft = float(benchmark.get("ttft_ms", _LATENCY_ANCHOR_MS))
        tps = float(benchmark.get("tokens_per_second", 0.0))
        # Approximate latency as time-to-first-token plus per-token cost.
        per_token_ms = (1000.0 / tps) if tps > 0 else _LATENCY_ANCHOR_MS
        effective_ms = ttft + per_token_ms
    return _LATENCY_ANCHOR_MS / (_LATENCY_ANCHOR_MS + max(effective_ms, 0.0))


def _price_score(entry: ProviderEntry) -> float:
    """Higher is better. Cheaper blended per-1M price -> score closer to 1.0."""
    pricing = entry.manifest.get("pricing") or {}
    input_rate = float(pricing.get("input_per_1m", 0.0))
    output_rate = float(pricing.get("output_per_1m", 0.0))
    blended = (input_rate + output_rate) / 2.0
    return _PRICE_ANCHOR / (_PRICE_ANCHOR + max(blended, 0.0))


def _privacy_score(entry: ProviderEntry, privacy_mode: str | None) -> float:
    if privacy_mode is None:
        return 1.0
    modes = entry.manifest.get("privacy_modes") or []
    return 1.0 if privacy_mode in modes else 0.0


def score_provider(
    entry: ProviderEntry,
    *,
    measured_latency_ms: float | None = None,
    privacy_mode: str | None = None,
    model_id: str | None = None,
    weights: dict[str, float] | None = None,
) -> float:
    """Score ``entry`` in ``[0, 1]`` using the spec 6.8 weighted blend.

    ``model_id`` lets callers require an exact model match for ``model_fit``;
    when omitted, any provider that advertises at least one model is treated as a
    full fit (resolvers normally pre-filter by model anyway).
    """
    active = weights if weights is not None else DEFAULT_WEIGHTS

    sub_scores: dict[str, float] = {
        "model_fit": _model_fit_score(entry, model_id),
        "expected_latency": _latency_score(entry, measured_latency_ms),
        "price": _price_score(entry),
        "receipt_trust": _DEFAULT_TRUST,
        "uptime": _DEFAULT_UPTIME,
        "privacy_mode_match": _privacy_score(entry, privacy_mode),
    }

    total_weight = sum(active.values())
    if total_weight <= 0:
        return 0.0
    weighted = sum(active.get(key, 0.0) * value for key, value in sub_scores.items())
    return weighted / total_weight


def rank_candidates(entries: list[ProviderEntry], **kwargs: Any) -> list[ProviderEntry]:
    """Return ``entries`` sorted by score descending (stable for ties)."""
    return sorted(entries, key=lambda entry: score_provider(entry, **kwargs), reverse=True)
