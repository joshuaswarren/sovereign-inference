# SPDX-License-Identifier: Apache-2.0
"""Deterministic canonical JSON serialization for signing.

The signed payload for a receipt or manifest must be byte-stable across
languages and machines. We use a JSON Canonicalization Scheme (RFC 8785)
compatible subset: object keys are sorted lexicographically, separators are
compact, and the output is UTF-8. We forbid NaN/Infinity, and the protocol
keeps non-deterministic numeric fields (e.g. prices) encoded as strings so the
canonical form is fully reproducible.
"""

from __future__ import annotations

import json
from typing import Any


def canonical_json(obj: Any) -> bytes:
    """Return the canonical UTF-8 byte encoding of ``obj``.

    Keys are sorted, whitespace is removed, and non-finite floats raise.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
