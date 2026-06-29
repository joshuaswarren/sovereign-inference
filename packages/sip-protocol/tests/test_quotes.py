# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest

from sip_protocol import KeyPair
from sip_protocol.quotes import (
    QUOTE_VERSION,
    build_quote,
    quote_is_expired,
    sign_quote,
    verify_quote,
)


@pytest.fixture
def signed_quote() -> dict:
    kp = KeyPair.generate()
    quote = build_quote(
        request_id="req-1",
        provider_pubkey=kp.public_key_str,
        model_alias="qwen2.5-coder-7b-instruct",
        price_units="pic",
        input_per_1m="0.20",
        output_per_1m="0.80",
        max_output_tokens=256,
        max_price="0.01",
        issued_at=datetime(2026, 6, 29, 18, 0, 0, tzinfo=UTC),
        expires_at=datetime(2026, 6, 29, 18, 0, 30, tzinfo=UTC),
        privacy_mode="direct",
    )
    return sign_quote(quote, kp)


def test_valid_quote_verifies(signed_quote: dict) -> None:
    result = verify_quote(signed_quote)
    assert result.valid
    assert result.schema_ok
    assert result.signature_ok
    assert bool(result) is True
    assert signed_quote["quote_version"] == QUOTE_VERSION


def test_tampered_price_breaks_signature(signed_quote: dict) -> None:
    signed_quote["max_price"] = "9.99"
    result = verify_quote(signed_quote)
    assert not result.valid
    assert result.schema_ok
    assert not result.signature_ok


def test_missing_required_field_fails_schema(signed_quote: dict) -> None:
    del signed_quote["model_alias"]
    assert not verify_quote(signed_quote).schema_ok


def test_non_decimal_price_fails_schema(signed_quote: dict) -> None:
    signed_quote["output_per_1m"] = "free"
    assert not verify_quote(signed_quote).schema_ok


def test_quote_expiry() -> None:
    issued = datetime(2026, 6, 29, 18, 0, 0, tzinfo=UTC)
    expires = issued + timedelta(seconds=30)
    quote = {"expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ")}
    assert quote_is_expired(quote, issued + timedelta(seconds=10)) is False
    assert quote_is_expired(quote, issued + timedelta(seconds=31)) is True


def test_malformed_expiry_is_treated_as_expired() -> None:
    assert quote_is_expired({"expires_at": "not-a-date"}, datetime.now(UTC)) is True
    assert quote_is_expired({}, datetime.now(UTC)) is True
