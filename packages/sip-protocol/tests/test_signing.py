# SPDX-License-Identifier: Apache-2.0
import pytest

from sip_protocol import KeyPair, decode_public_key, encode_public_key, verify
from sip_protocol.errors import KeyEncodingError
from sip_protocol.signing import ED25519_PREFIX


def test_generated_public_key_has_expected_shape() -> None:
    kp = KeyPair.generate()
    assert kp.public_key_str.startswith(ED25519_PREFIX)
    # 32 raw bytes -> 43 base64url chars (no padding)
    assert len(kp.public_key_str[len(ED25519_PREFIX) :]) == 43


def test_sign_then_verify_roundtrip() -> None:
    kp = KeyPair.generate()
    msg = b"sovereign inference"
    sig = kp.sign(msg)
    assert verify(kp.public_key_str, msg, sig) is True


def test_verify_fails_on_tampered_message() -> None:
    kp = KeyPair.generate()
    sig = kp.sign(b"original")
    assert verify(kp.public_key_str, b"tampered", sig) is False


def test_verify_fails_with_wrong_key() -> None:
    signer = KeyPair.generate()
    other = KeyPair.generate()
    sig = signer.sign(b"hello")
    assert verify(other.public_key_str, b"hello", sig) is False


def test_private_key_roundtrip() -> None:
    kp = KeyPair.generate()
    restored = KeyPair.from_private_str(kp.private_key_str)
    assert restored.public_key_str == kp.public_key_str


def test_public_key_encode_decode_roundtrip() -> None:
    kp = KeyPair.generate()
    decoded = decode_public_key(kp.public_key_str)
    assert encode_public_key(decoded) == kp.public_key_str


def test_malformed_key_raises() -> None:
    with pytest.raises(KeyEncodingError):
        decode_public_key("notakey")


def test_verify_returns_false_on_malformed_inputs() -> None:
    assert verify("notakey", b"x", "alsonotasig") is False
