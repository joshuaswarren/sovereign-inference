# SPDX-License-Identifier: Apache-2.0
"""Load and validate documents against the bundled JSON Schemas.

The authoritative schemas live in ``docs/spec/schemas/`` and an identical copy
is bundled inside this package (``sip_protocol/schemas/``) so validation works
once installed. ``packages/sip-protocol/tests/test_schema_sync.py`` guards
against the two copies drifting apart.
"""

from __future__ import annotations

import json
from functools import cache
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator

from .errors import SchemaValidationError

SCHEMA_FILES: dict[str, str] = {
    "receipt": "inference_receipt.schema.json",
    "quote": "inference_quote.schema.json",
    "model_manifest": "model_manifest.schema.json",
    "provider_manifest": "provider_manifest.schema.json",
}


@cache
def load_schema(name: str) -> dict[str, Any]:
    """Load a bundled schema by short name ('receipt', 'model_manifest', ...)."""
    try:
        filename = SCHEMA_FILES[name]
    except KeyError:
        raise SchemaValidationError(f"unknown schema {name!r}") from None
    text = files("sip_protocol").joinpath("schemas", filename).read_text("utf-8")
    schema: dict[str, Any] = json.loads(text)
    return schema


@cache
def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(name))


def iter_errors(name: str, document: Any) -> list[str]:
    """Return a sorted list of human-readable validation error messages."""
    validator = _validator(name)
    messages = []
    for error in validator.iter_errors(document):
        location = "/".join(str(p) for p in error.absolute_path) or "<root>"
        messages.append(f"{location}: {error.message}")
    return sorted(messages)


def validate(name: str, document: Any) -> None:
    """Validate ``document``; raise SchemaValidationError on the first failure."""
    errors = iter_errors(name, document)
    if errors:
        raise SchemaValidationError(f"{name} failed validation: " + "; ".join(errors))
