# SPDX-License-Identifier: Apache-2.0
"""Anchor SIP-AI artifacts (receipts, manifests, arbitrary JSON) and resolve them.

Documents are stored in their canonical JSON form so the anchored bytes match
the bytes that were signed. Receipts and provider manifests are *verified before
they are anchored* — durable provenance must not enshrine an invalid artifact.
"""

from __future__ import annotations

import json
from typing import Any

from sip_protocol.canonical import canonical_json
from sip_protocol.manifests import PROVIDER_MANIFEST_SCHEMA, verify_provider_manifest
from sip_protocol.receipts import verify_receipt

from .anchor import Anchor
from .errors import AnchorError

_JSON = "application/json"


def anchor_json(anchor: Anchor, obj: dict[str, Any], *, tags: dict[str, str] | None = None) -> str:
    """Canonicalize ``obj`` and store it; return its anchor URI."""
    return anchor.put(canonical_json(obj), content_type=_JSON, tags=tags)


def resolve_json(anchor: Anchor, uri: str) -> dict[str, Any]:
    """Resolve ``uri`` and parse the stored bytes as a JSON object."""
    raw = anchor.get(uri)
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise AnchorError(f"anchored object at {uri!r} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise AnchorError(f"anchored object at {uri!r} is not a JSON object")
    return value


def anchor_receipt(anchor: Anchor, receipt: dict[str, Any], *, tags: dict[str, str] | None = None) -> str:
    """Verify a signed receipt, then anchor it. Raises if verification fails."""
    if not verify_receipt(receipt):
        raise AnchorError("refusing to anchor an invalid receipt")
    # Receipts carry their version under ``receipt_version`` (not ``schema``); use
    # it so the provenance tag tracks the real receipt version.
    merged = {"SIP-AI": receipt.get("receipt_version", "sip-ai.receipt.v1"), **(tags or {})}
    return anchor_json(anchor, receipt, tags=merged)


def anchor_manifest(anchor: Anchor, manifest: dict[str, Any], *, tags: dict[str, str] | None = None) -> str:
    """Anchor a SIP-AI manifest.

    Provider manifests are signed and verified before anchoring; model manifests
    (which are content-addressed rather than signed) are anchored as-is.
    """
    if manifest.get("schema") == PROVIDER_MANIFEST_SCHEMA and not verify_provider_manifest(manifest):
        raise AnchorError("refusing to anchor an invalid provider manifest")
    merged = {"SIP-AI": str(manifest.get("schema", "sip-ai.manifest")), **(tags or {})}
    return anchor_json(anchor, manifest, tags=merged)
