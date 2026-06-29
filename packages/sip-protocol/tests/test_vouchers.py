# SPDX-License-Identifier: Apache-2.0
import re
from datetime import UTC, datetime, timedelta

import pytest

from sip_protocol import KeyPair
from sip_protocol.vouchers import (
    VOUCHER_VERSION,
    build_voucher,
    new_voucher_id,
    sign_voucher,
    verify_voucher,
    voucher_is_expired,
)


@pytest.fixture
def signed_voucher() -> dict:
    kp = KeyPair.generate()
    voucher = build_voucher(
        denomination="0.10",
        unit="pic",
        issuer_pubkey=kp.public_key_str,
        issued_at=datetime(2026, 6, 29, 18, 0, 0, tzinfo=UTC),
        expires_at=datetime(2026, 6, 29, 19, 0, 0, tzinfo=UTC),
    )
    return sign_voucher(voucher, kp)


def test_valid_voucher_verifies(signed_voucher: dict) -> None:
    result = verify_voucher(signed_voucher)
    assert result.valid
    assert result.schema_ok
    assert result.signature_ok
    assert signed_voucher["voucher_version"] == VOUCHER_VERSION


def test_voucher_id_is_high_entropy_and_unique() -> None:
    ids = {new_voucher_id() for _ in range(100)}
    assert len(ids) == 100  # no collisions
    for vid in ids:
        assert re.fullmatch(r"[A-Za-z0-9_-]{43,86}", vid)


def test_tampered_denomination_breaks_signature(signed_voucher: dict) -> None:
    signed_voucher["denomination"] = "9999.0"
    result = verify_voucher(signed_voucher)
    assert not result.valid
    assert result.schema_ok
    assert not result.signature_ok


def test_non_decimal_denomination_fails_schema(signed_voucher: dict) -> None:
    signed_voucher["denomination"] = "free"
    assert not verify_voucher(signed_voucher).schema_ok


def test_missing_field_fails_schema(signed_voucher: dict) -> None:
    del signed_voucher["unit"]
    assert not verify_voucher(signed_voucher).schema_ok


def test_voucher_expiry() -> None:
    issued = datetime(2026, 6, 29, 18, 0, 0, tzinfo=UTC)
    voucher = {"expires_at": (issued + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    assert voucher_is_expired(voucher, issued) is False
    assert voucher_is_expired(voucher, issued + timedelta(hours=2)) is True
    assert voucher_is_expired({"expires_at": "garbage"}, issued) is True
    assert voucher_is_expired({}, issued) is True
