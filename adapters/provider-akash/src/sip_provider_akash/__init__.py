# SPDX-License-Identifier: Apache-2.0
"""sip-provider-akash — serve a SIP inference endpoint on the Akash marketplace.

Importing this package registers the ``akash`` compute provider with
:mod:`sip_compute`. :func:`build_sdl` is exposed for inspection and testing of
the generated SDL v2.0 manifest.
"""

from __future__ import annotations

from .provider import AkashProvider, CliRunner
from .sdl import build_sdl

__version__ = "0.1.2"

__all__ = [
    "AkashProvider",
    "CliRunner",
    "build_sdl",
]
