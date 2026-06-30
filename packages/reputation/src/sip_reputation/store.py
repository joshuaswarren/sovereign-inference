# SPDX-License-Identifier: Apache-2.0
"""Persisted provider reputation: record routing outcomes, compute a score.

A :class:`ReputationStore` aggregates per-provider outcomes (success/failure,
latency, whether the returned receipt verified) and computes a bounded ``score``
in ``[0, 1]``. An unseen provider scores a neutral ``0.5`` so newcomers are not
starved by the cold-start problem. Persistence is atomic (tempfile + replace).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Composite weights: a returned-and-correct answer matters most, an honest
# (verifiable) receipt next. Latency is a tie-breaker in ranking, not the score.
_SUCCESS_WEIGHT = 0.7
_RECEIPT_WEIGHT = 0.3
NEUTRAL_SCORE = 0.5


@dataclass(frozen=True, slots=True)
class ReputationScore:
    """A provider's aggregate reputation."""

    provider_pubkey: str
    samples: int
    success_rate: float
    receipt_valid_rate: float
    avg_latency_ms: float | None
    score: float


class ReputationStore:
    """File-backed per-provider outcome counters."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def record(
        self,
        provider_pubkey: str,
        *,
        success: bool,
        latency_ms: float | None = None,
        receipt_valid: bool = True,
    ) -> None:
        """Record one routing outcome for ``provider_pubkey``."""
        data = self._load()
        entry = data.setdefault(
            provider_pubkey,
            {"total": 0, "success": 0, "receipt_valid": 0, "latency_sum": 0.0, "latency_n": 0},
        )
        entry["total"] += 1
        if success:
            entry["success"] += 1
        if receipt_valid:
            entry["receipt_valid"] += 1
        if latency_ms is not None:
            entry["latency_sum"] += float(latency_ms)
            entry["latency_n"] += 1
        self._write(data)

    def score(self, provider_pubkey: str) -> ReputationScore:
        """Return the aggregate :class:`ReputationScore` for ``provider_pubkey``."""
        entry = self._load().get(provider_pubkey)
        if not entry or int(entry.get("total", 0)) == 0:
            return ReputationScore(provider_pubkey, 0, 0.0, 0.0, None, NEUTRAL_SCORE)
        total = int(entry["total"])
        success_rate = int(entry.get("success", 0)) / total
        receipt_valid_rate = int(entry.get("receipt_valid", 0)) / total
        latency_n = int(entry.get("latency_n", 0))
        avg_latency = float(entry["latency_sum"]) / latency_n if latency_n else None
        score = _SUCCESS_WEIGHT * success_rate + _RECEIPT_WEIGHT * receipt_valid_rate
        return ReputationScore(provider_pubkey, total, success_rate, receipt_valid_rate, avg_latency, score)

    # -- storage --------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, sort_keys=True)
            Path(tmp).replace(self._path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
