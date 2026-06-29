# SPDX-License-Identifier: Apache-2.0
"""sip-runtime-ollama — Ollama runtime adapter for SIP-AI providers.

Importing this package registers the ``ollama`` runtime adapter with
:mod:`sin_node.adapter` so the node can build it by name.
"""

from .adapter import DEFAULT_BASE_URL, OllamaAdapter

__version__ = "0.1.2"

__all__ = ["DEFAULT_BASE_URL", "OllamaAdapter", "__version__"]
