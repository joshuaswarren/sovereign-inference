# SPDX-License-Identifier: Apache-2.0
"""Error types for the external-compute contract."""

from __future__ import annotations


class ComputeError(RuntimeError):
    """Raised when a compute spec is invalid or a provider operation fails."""
