# SPDX-License-Identifier: AGPL-3.0-or-later
"""Data models for the router: provider entries and route results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict


class ProviderEntry(BaseModel):
    """A known provider: where to reach it and its signed provider manifest.

    ``manifest`` is a ``sip-ai.provider_manifest.v1`` dict (as produced by
    :func:`sip_protocol.sign_provider_manifest`).
    """

    model_config = ConfigDict(frozen=True)

    base_url: str
    manifest: dict[str, Any]


@dataclass(frozen=True)
class RouteResult:
    """The outcome of a successful :meth:`SovereignClient.chat` call.

    ``attempts`` records every provider tried in order, each as
    ``{"base_url": str, "outcome": str}`` — the final entry is the one that
    served the response (``outcome == "ok"``).
    """

    content: str
    receipt: dict[str, Any]
    provider_pubkey: str
    base_url: str
    quote: dict[str, Any] | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)
