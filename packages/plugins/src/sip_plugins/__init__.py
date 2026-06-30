# SPDX-License-Identifier: Apache-2.0
"""sip-plugins — discover and register Sovereign Inference extensions.

Third-party packages declare entry points in the SIP-AI groups; :func:`discover`
loads them and the ``load_*`` helpers register them. See the package README.
"""

from __future__ import annotations

from .loader import (
    COMPUTE_GROUP,
    DIRECTORY_GROUP,
    RUNTIME_GROUP,
    Plugin,
    discover,
    load_all,
    load_compute_providers,
    load_runtime_adapters,
)

__version__ = "0.1.2"

__all__ = [
    "COMPUTE_GROUP",
    "DIRECTORY_GROUP",
    "RUNTIME_GROUP",
    "Plugin",
    "discover",
    "load_all",
    "load_compute_providers",
    "load_runtime_adapters",
]
