# SPDX-License-Identifier: Apache-2.0
"""sip-policy — declarative provider-selection policy for SIP-AI.

A :class:`Policy` governs which providers a router or the OpenAI proxy may use
(required attestation, price caps, privacy modes, allow/deny, minimum reputation);
``permits`` yields a :class:`PolicyDecision` and ``filter_entries`` keeps the
allowed providers.
"""

from __future__ import annotations

from .policy import Policy, PolicyDecision

__version__ = "0.1.2"

__all__ = ["Policy", "PolicyDecision"]
