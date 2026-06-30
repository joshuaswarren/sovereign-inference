# SPDX-License-Identifier: Apache-2.0
"""sip-discovery — announce and discover SIP-AI providers.

A node announces its signed provider manifest to a :class:`Directory`; a router
discovers verified providers from it. :class:`FileDirectory` is an offline,
shared-JSON directory; :class:`ArweaveDirectory` publishes to and queries Arweave.
Discovery verifies every manifest signature and keeps the freshest entry per
provider key.
"""

from __future__ import annotations

from .directory import (
    ArweaveDirectory,
    Directory,
    DiscoveredProvider,
    DiscoveryQuery,
    FileDirectory,
    HttpDirectory,
    arweave_discovery_query,
)
from .errors import DiscoveryError

__version__ = "0.1.2"

__all__ = [
    "ArweaveDirectory",
    "Directory",
    "DiscoveredProvider",
    "DiscoveryError",
    "DiscoveryQuery",
    "FileDirectory",
    "HttpDirectory",
    "arweave_discovery_query",
]
