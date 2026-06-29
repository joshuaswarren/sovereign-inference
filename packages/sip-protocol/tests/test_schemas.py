# SPDX-License-Identifier: Apache-2.0
import pytest

from sip_protocol import iter_errors, load_schema, validate
from sip_protocol.errors import SchemaValidationError


def test_load_known_schemas() -> None:
    for name in ("receipt", "model_manifest", "provider_manifest"):
        schema = load_schema(name)
        assert schema["$schema"].startswith("https://json-schema.org/")


def test_unknown_schema_raises() -> None:
    with pytest.raises(SchemaValidationError):
        load_schema("nope")


def test_iter_errors_reports_bad_pubkey_pattern() -> None:
    bad = {
        "receipt_version": "sip-ai.receipt.v1",
        "request_id": "r",
        "provider_pubkey": "not-an-ed25519-key",
        "model_manifest_hash": "sha256:" + "0" * 64,
        "model_alias": "m",
        "runtime": "llama.cpp",
        "input_tokens": 1,
        "output_tokens": 1,
        "price_units": "pic",
        "price_amount": "0.1",
        "privacy_mode": "direct",
        "started_at": "2026-06-29T18:15:02Z",
        "completed_at": "2026-06-29T18:15:09Z",
        "response_hash": "sha256:" + "0" * 64,
        "signature": "ed25519:" + "A" * 86,
    }
    errors = iter_errors("receipt", bad)
    assert any("provider_pubkey" in e for e in errors)


def test_validate_raises_on_unknown_runtime() -> None:
    doc = {"runtime": "magic-runtime"}
    with pytest.raises(SchemaValidationError):
        validate("receipt", doc)
