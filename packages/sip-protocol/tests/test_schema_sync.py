# SPDX-License-Identifier: Apache-2.0
"""Guard against the bundled package schemas drifting from the canonical docs.

The authoritative schemas live in ``docs/spec/schemas/``; an identical copy is
shipped inside the package so validation works once installed. If these ever
diverge, the protocol and the spec would silently disagree — so we fail loudly.
"""

import json
from pathlib import Path

import pytest

from sip_protocol.schemas import SCHEMA_FILES

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCS_SCHEMAS = _REPO_ROOT / "docs" / "spec" / "schemas"
_PKG_SCHEMAS = _REPO_ROOT / "packages" / "sip-protocol" / "src" / "sip_protocol" / "schemas"


@pytest.mark.parametrize("filename", sorted(SCHEMA_FILES.values()))
def test_bundled_schema_matches_docs(filename: str) -> None:
    docs_copy = json.loads((_DOCS_SCHEMAS / filename).read_text("utf-8"))
    pkg_copy = json.loads((_PKG_SCHEMAS / filename).read_text("utf-8"))
    assert docs_copy == pkg_copy, f"{filename} differs between docs/ and the package bundle"
