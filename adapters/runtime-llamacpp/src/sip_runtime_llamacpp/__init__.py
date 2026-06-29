# SPDX-License-Identifier: Apache-2.0
"""sip-runtime-llamacpp — llama.cpp runtime adapter for SIP-AI providers.

Importing this package registers the ``llama.cpp`` adapter so it can be wired
by name via :func:`sin_node.adapter.get_adapter`.
"""

from __future__ import annotations

from sin_node.adapter import register_adapter

from .adapter import RUNTIME_NAME, LlamaCppAdapter

__version__ = "0.1.2"

register_adapter(RUNTIME_NAME, LlamaCppAdapter)

__all__ = ["RUNTIME_NAME", "LlamaCppAdapter", "__version__"]
