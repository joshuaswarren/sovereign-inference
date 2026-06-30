# SPDX-License-Identifier: Apache-2.0
"""A declarative provider-selection policy.

A :class:`Policy` is the one place an operator expresses *which* providers a
router or the OpenAI proxy may use: require TEE attestation, cap the price, demand
a privacy mode, allow/deny specific keys, and require a minimum reputation.
``permits`` returns a :class:`PolicyDecision` (with a machine-readable reason on
rejection); ``filter_entries`` keeps only the providers the policy allows.

Reputation is supplied by the caller (``reputation_score`` / ``get_score``) so the
policy has no dependency on the reputation store.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sip_protocol.attestation import TEE_TYPES, is_attested


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Whether a provider is permitted, and (if not) why."""

    ok: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class Policy:
    """Operator-defined constraints on which providers may serve a request."""

    require_attestation: bool = False
    accepted_tee_types: tuple[str, ...] = field(default_factory=tuple)
    accepted_units: tuple[str, ...] = field(default_factory=tuple)
    max_input_per_1m: float | None = None
    max_output_per_1m: float | None = None
    required_privacy_modes: tuple[str, ...] = field(default_factory=tuple)
    allow_providers: tuple[str, ...] = field(default_factory=tuple)
    deny_providers: tuple[str, ...] = field(default_factory=tuple)
    min_reputation: float | None = None

    def permits(self, manifest: dict[str, Any], *, reputation_score: float | None = None) -> PolicyDecision:
        """Decide whether ``manifest``'s provider satisfies this policy."""
        pubkey = manifest.get("provider_pubkey")

        if self.deny_providers and pubkey in set(self.deny_providers):
            return PolicyDecision(False, "provider_denylisted")
        if self.allow_providers and pubkey not in set(self.allow_providers):
            return PolicyDecision(False, "not_allowlisted")

        if self.require_attestation:
            # With no explicit list, accept any *real* TEE — never "none", which a
            # provider can self-assert and would defeat the attestation requirement.
            accepted = list(self.accepted_tee_types) or [t for t in TEE_TYPES if t != "none"]
            if not is_attested(manifest, accepted_tee_types=accepted):
                return PolicyDecision(False, "attestation_required")

        raw_pricing = manifest.get("pricing")
        pricing: dict[str, Any] = raw_pricing if isinstance(raw_pricing, dict) else {}
        if self.accepted_units and pricing.get("unit") not in set(self.accepted_units):
            return PolicyDecision(False, "unit_not_accepted")
        if self.max_input_per_1m is not None and _price(pricing, "input_per_1m") > self.max_input_per_1m:
            return PolicyDecision(False, "input_price_too_high")
        if self.max_output_per_1m is not None and _price(pricing, "output_per_1m") > self.max_output_per_1m:
            return PolicyDecision(False, "output_price_too_high")

        if self.required_privacy_modes:
            advertised = set(manifest.get("privacy_modes") or [])
            if not set(self.required_privacy_modes).issubset(advertised):
                return PolicyDecision(False, "privacy_mode_unmet")

        if self.min_reputation is not None and (reputation_score is None or reputation_score < self.min_reputation):
            return PolicyDecision(False, "reputation_too_low")

        return PolicyDecision(True, "")

    def filter_entries(
        self,
        entries: list[Any],
        *,
        manifest_of: Callable[[Any], dict[str, Any]] = lambda entry: entry.manifest,
        get_score: Callable[[str], float | None] | None = None,
    ) -> list[Any]:
        """Return the subset of ``entries`` this policy permits.

        ``manifest_of`` extracts a manifest from each entry (defaults to
        ``entry.manifest``, matching ``ProviderEntry``/``DiscoveredProvider``);
        ``get_score`` optionally maps a provider pubkey to a reputation score.
        """
        permitted: list[Any] = []
        for entry in entries:
            manifest = manifest_of(entry)
            score = get_score(str(manifest.get("provider_pubkey"))) if get_score is not None else None
            if self.permits(manifest, reputation_score=score).ok:
                permitted.append(entry)
        return permitted


def _price(pricing: dict[str, Any], key: str) -> float:
    try:
        return float(pricing.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0
