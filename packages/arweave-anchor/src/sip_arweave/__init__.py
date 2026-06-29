# SPDX-License-Identifier: Apache-2.0
"""sip-arweave — anchor SIP-AI provenance to durable storage and resolve it back.

Exposes the :class:`Anchor` protocol with two implementations — :class:`LocalAnchor`
(offline, content-addressed) and :class:`ArweaveAnchor` (permanent, ``ar://``) —
plus helpers to anchor and resolve canonical JSON, signed receipts, and manifests.
"""

from __future__ import annotations

from .anchor import (
    Anchor,
    ArweaveAnchor,
    LocalAnchor,
    TxSubmitter,
    arweave_submitter,
)
from .errors import AnchorError
from .helpers import (
    anchor_json,
    anchor_manifest,
    anchor_receipt,
    resolve_json,
)

__version__ = "0.1.2"

__all__ = [
    "Anchor",
    "AnchorError",
    "ArweaveAnchor",
    "LocalAnchor",
    "TxSubmitter",
    "anchor_json",
    "anchor_manifest",
    "anchor_receipt",
    "arweave_submitter",
    "resolve_json",
]
