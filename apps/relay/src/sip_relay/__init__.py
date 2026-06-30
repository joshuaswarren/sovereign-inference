# SPDX-License-Identifier: AGPL-3.0-or-later
"""sip-relay — a SIP-AI privacy relay (forward to a provider, hide the client).

Exposes :func:`create_relay_app` (the relay server), ``run`` (console entry), and
the :func:`relay_chat` client helper with its :class:`RelayResult`.
"""

from __future__ import annotations

from .app import create_relay_app, default_client_factory, run
from .client import RelayResult, relay_chat

__version__ = "0.1.2"

__all__ = [
    "RelayResult",
    "create_relay_app",
    "default_client_factory",
    "relay_chat",
    "run",
]
