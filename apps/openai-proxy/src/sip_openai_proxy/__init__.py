# SPDX-License-Identifier: AGPL-3.0-or-later
"""sip-openai-proxy — a local OpenAI-compatible endpoint over the SIP-AI network.

``build_backend`` wires a policy-filtered routing client; ``create_proxy_app``
exposes the OpenAI surface (``/v1/models``, ``/v1/chat/completions``). Point any
OpenAI client at it and requests route across SIP-AI providers with verified receipts.
"""

from __future__ import annotations

from .app import ProxyBackend, build_backend, create_proxy_app, run

__version__ = "0.1.2"

__all__ = ["ProxyBackend", "build_backend", "create_proxy_app", "run"]
