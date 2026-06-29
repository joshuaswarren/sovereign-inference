# SPDX-License-Identifier: AGPL-3.0-or-later
"""Resolve a model id to a ranked list of candidate providers."""

from __future__ import annotations

from sip_protocol import verify_provider_manifest

from .models import ProviderEntry
from .registry import ProviderRegistry
from .scoring import rank_candidates


def resolve(
    registry: ProviderRegistry,
    model_id: str,
    *,
    privacy_mode: str | None = None,
    weights: dict[str, float] | None = None,
    verify_manifests: bool = False,
) -> list[ProviderEntry]:
    """Return providers that serve ``model_id``, ranked best-first.

    When ``verify_manifests`` is True, entries whose provider manifest fails
    :func:`sip_protocol.verify_provider_manifest` are dropped. It defaults to
    False so freshly-signed demo manifests (and concurrently-built gateways)
    route without friction; callers that want strict trust can opt in.
    """
    candidates = registry.for_model(model_id)
    if verify_manifests:
        candidates = [e for e in candidates if verify_provider_manifest(e.manifest)]
    return rank_candidates(
        candidates,
        privacy_mode=privacy_mode,
        model_id=model_id,
        weights=weights,
    )
