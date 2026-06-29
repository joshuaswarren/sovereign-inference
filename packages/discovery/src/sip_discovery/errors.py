# SPDX-License-Identifier: Apache-2.0
"""Error type for discovery operations."""

from __future__ import annotations


class DiscoveryError(RuntimeError):
    """Raised when announcing or discovering a provider fails."""
