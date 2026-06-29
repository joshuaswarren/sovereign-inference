# SPDX-License-Identifier: Apache-2.0
"""Translate a provider-agnostic :class:`InferenceSpec` into an Akash SDL.

Akash deployments are described by a Stack Definition Language (SDL v2.0)
manifest: a ``services`` block (image, exposed ports, env), a ``profiles``
block (compute resources incl. GPU, and placement pricing), and a
``deployment`` block binding each service to a placement/profile. We emit a
single service that serves the SIP gateway image for the requested model.
"""

from __future__ import annotations

from typing import Any

from sip_compute import InferenceSpec

SDL_VERSION = "2.0"
SERVICE_NAME = "sip-gateway"
PLACEMENT_NAME = "sovereign"
DEFAULT_DENOM = "uakt"
DEFAULT_PRICE = 10_000  # uakt/block bid ceiling
DEFAULT_STORAGE = "16Gi"


def build_sdl(spec: InferenceSpec, *, price: int = DEFAULT_PRICE, denom: str = DEFAULT_DENOM) -> dict[str, Any]:
    """Build the SDL v2.0 manifest that serves ``spec`` on Akash."""
    service: dict[str, Any] = {
        "image": spec.image,
        "expose": [
            {
                "port": spec.port,
                "as": 80,
                "to": [{"global": True}],
            }
        ],
    }
    if spec.env:
        service["env"] = [f"{key}={value}" for key, value in spec.env.items()]
    if spec.command:
        service["command"] = list(spec.command)

    resources: dict[str, Any] = {
        "cpu": {"units": spec.cpu},
        "memory": {"size": spec.memory},
        "storage": {"size": DEFAULT_STORAGE},
    }
    if spec.gpu:
        gpu: dict[str, Any] = {"units": 1}
        if spec.gpu_model:
            gpu["attributes"] = {"vendor": {"nvidia": [{"model": spec.gpu_model}]}}
        resources["gpu"] = gpu

    return {
        "version": SDL_VERSION,
        "services": {SERVICE_NAME: service},
        "profiles": {
            "compute": {SERVICE_NAME: {"resources": resources}},
            "placement": {
                PLACEMENT_NAME: {
                    "pricing": {SERVICE_NAME: {"denom": denom, "amount": price}},
                }
            },
        },
        "deployment": {
            SERVICE_NAME: {
                PLACEMENT_NAME: {"profile": SERVICE_NAME, "count": 1},
            }
        },
    }
