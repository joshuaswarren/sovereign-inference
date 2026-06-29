# SPDX-License-Identifier: AGPL-3.0-or-later
"""sip-router — SIP-AI client SDK and provider router.

Resolve a model id to ranked providers, optionally fetch signed quotes, route
an OpenAI-compatible chat completion to the best available provider, fail over
on failure, and verify the returned signed receipt.

Public API:
    Models:    ProviderEntry, RouteResult
    Registry:  ProviderRegistry
    Scoring:   score_provider, rank_candidates, DEFAULT_WEIGHTS
    Resolver:  resolve
    Client:    SovereignClient
    Errors:    SovereignRouterError, NoProviderAvailable
"""

from __future__ import annotations

from .client import SovereignClient
from .errors import NoProviderAvailable, SovereignRouterError
from .models import ProviderEntry, RouteResult
from .registry import ProviderRegistry
from .resolver import resolve
from .scoring import DEFAULT_WEIGHTS, rank_candidates, score_provider

__version__ = "0.1.2"

__all__ = [
    "DEFAULT_WEIGHTS",
    "NoProviderAvailable",
    "ProviderEntry",
    "ProviderRegistry",
    "RouteResult",
    "SovereignClient",
    "SovereignRouterError",
    "__version__",
    "rank_candidates",
    "resolve",
    "score_provider",
]
