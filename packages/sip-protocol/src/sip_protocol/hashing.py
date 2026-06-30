# SPDX-License-Identifier: Apache-2.0
"""SHA-256 helpers that emit the ``sha256:<hex>`` form used across the protocol."""

from __future__ import annotations

import hashlib
from typing import Any

from .canonical import canonical_json

SHA256_PREFIX = "sha256:"


def sha256_prefixed(data: bytes) -> str:
    """Return ``sha256:<hexdigest>`` for raw bytes."""
    return SHA256_PREFIX + hashlib.sha256(data).hexdigest()


def hash_response_body(body: str | bytes) -> str:
    """Hash an inference response body for inclusion in a receipt."""
    if isinstance(body, str):
        body = body.encode("utf-8")
    return sha256_prefixed(body)


def hash_request(model: str, messages: list[dict[str, Any]]) -> str:
    """Hash the canonical request (model + messages).

    Embedded in a receipt as ``request_hash`` so a client can prove the signed
    receipt corresponds to *its* request — defeating a relay that substitutes a
    different (but genuinely signed) answer for another prompt.
    """
    return sha256_prefixed(canonical_json({"model": model, "messages": messages}))
