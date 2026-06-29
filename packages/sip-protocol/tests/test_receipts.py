# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

import pytest

from sip_protocol import (
    KeyPair,
    build_receipt,
    hash_response_body,
    sign_receipt,
    verify_receipt,
)


@pytest.fixture
def signed_receipt() -> dict:
    kp = KeyPair.generate()
    receipt = build_receipt(
        request_id="req-123",
        provider_pubkey=kp.public_key_str,
        model_manifest_hash="sha256:" + "ab" * 32,
        model_alias="qwen-coder-7b-instruct-gguf-q4_k_m",
        runtime="llama.cpp",
        runtime_version="b3000",
        input_tokens=817,
        output_tokens=242,
        price_units="pic",
        price_amount="0.0042",
        privacy_mode="private-payment-relay",
        started_at=datetime(2026, 6, 29, 18, 15, 2, tzinfo=UTC),
        completed_at=datetime(2026, 6, 29, 18, 15, 9, tzinfo=UTC),
        response_hash=hash_response_body("the answer"),
    )
    return sign_receipt(receipt, kp)


def test_valid_receipt_verifies(signed_receipt: dict) -> None:
    result = verify_receipt(signed_receipt)
    assert result.valid
    assert result.schema_ok
    assert result.signature_ok
    assert result.errors == []
    assert bool(result) is True


def test_tampered_token_count_breaks_signature(signed_receipt: dict) -> None:
    signed_receipt["output_tokens"] = 999_999
    result = verify_receipt(signed_receipt)
    assert not result.valid
    assert result.schema_ok  # still schema-valid...
    assert not result.signature_ok  # ...but signature no longer matches


def test_tampered_response_hash_breaks_signature(signed_receipt: dict) -> None:
    signed_receipt["response_hash"] = "sha256:" + "0" * 64
    assert not verify_receipt(signed_receipt).valid


def test_missing_required_field_fails_schema(signed_receipt: dict) -> None:
    del signed_receipt["model_alias"]
    result = verify_receipt(signed_receipt)
    assert not result.schema_ok
    assert not result.valid


def test_bad_timestamps_round_to_utc_z_form(signed_receipt: dict) -> None:
    assert signed_receipt["started_at"] == "2026-06-29T18:15:02Z"
    assert signed_receipt["completed_at"] == "2026-06-29T18:15:09Z"


def test_signature_uses_url_safe_encoding(signed_receipt: dict) -> None:
    assert signed_receipt["signature"].startswith("ed25519:")
