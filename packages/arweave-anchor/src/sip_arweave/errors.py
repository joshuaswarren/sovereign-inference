# SPDX-License-Identifier: Apache-2.0
"""Error type for anchoring operations."""

from __future__ import annotations


class AnchorError(RuntimeError):
    """Raised when anchoring or resolving durable provenance fails."""
