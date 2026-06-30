# SPDX-License-Identifier: Apache-2.0
"""sip-reputation — provider health + reputation signals for selection.

Probe a discovered provider's liveness and identity (:class:`HealthProbe`), track
routing outcomes and a bounded reputation score (:class:`ReputationStore`), and
rank discovered providers best-first (:func:`rank_providers`).
"""

from __future__ import annotations

from .health import HealthProbe, HealthStatus
from .rank import RankedProvider, rank_providers
from .store import NEUTRAL_SCORE, ReputationScore, ReputationStore

__version__ = "0.1.2"

__all__ = [
    "NEUTRAL_SCORE",
    "HealthProbe",
    "HealthStatus",
    "RankedProvider",
    "ReputationScore",
    "ReputationStore",
    "rank_providers",
]
