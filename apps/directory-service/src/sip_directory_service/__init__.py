# SPDX-License-Identifier: AGPL-3.0-or-later
"""sip-directory-service — a hosted SIP-AI provider directory (relay).

Exposes :func:`create_directory_app`, a FastAPI app over any
:class:`sip_discovery.Directory` store, and ``run`` (the console-script entry).
"""

from __future__ import annotations

from .app import create_directory_app, run

__version__ = "0.1.2"

__all__ = ["create_directory_app", "run"]
