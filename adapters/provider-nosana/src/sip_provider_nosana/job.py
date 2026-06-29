# SPDX-License-Identifier: Apache-2.0
"""Translate a provider-agnostic :class:`InferenceSpec` into a Nosana job.

Nosana runs containerized GPU jobs described by a small JSON document: a list of
``ops``, each a ``container/run`` carrying the image, command, GPU flag, an
exposed port, and environment. We emit exactly one op that serves the SIP
gateway image for the requested model.

Reference: Nosana job definition (``version``/``type``/``ops[]`` with
``args.image``/``cmd``/``gpu``/``expose``/``env``).
"""

from __future__ import annotations

from typing import Any

from sip_compute import InferenceSpec

JOB_VERSION = "0.1"
OP_ID = "sip-inference"


def build_job_definition(spec: InferenceSpec) -> dict[str, Any]:
    """Build the Nosana JSON job definition that serves ``spec``."""
    args: dict[str, Any] = {
        "image": spec.image,
        "gpu": spec.gpu,
        "expose": spec.port,
    }
    if spec.command:
        args["cmd"] = list(spec.command)
    if spec.env:
        args["env"] = dict(spec.env)
    return {
        "version": JOB_VERSION,
        "type": "container",
        "meta": {"trigger": "cli"},
        "ops": [
            {
                "type": "container/run",
                "id": OP_ID,
                "args": args,
            }
        ],
    }
