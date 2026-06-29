# SPDX-License-Identifier: Apache-2.0
"""sip-provider-nosana — serve a SIP inference endpoint on the Nosana GPU network.

Importing this package registers the ``nosana`` compute provider with
:mod:`sip_compute`. :func:`build_job_definition` is exposed for inspection and
testing of the generated Nosana job document.
"""

from __future__ import annotations

from .job import build_job_definition
from .provider import CliRunner, NosanaProvider

__version__ = "0.1.2"

__all__ = [
    "CliRunner",
    "NosanaProvider",
    "build_job_definition",
]
