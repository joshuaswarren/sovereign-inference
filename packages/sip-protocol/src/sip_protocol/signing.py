# SPDX-License-Identifier: Apache-2.0
"""Ed25519 key handling, signing, and verification.

Keys and signatures are encoded as ``ed25519:<base64url>`` strings (no padding)
so they are URL-safe and unambiguous in JSON. Raw key material is 32 bytes
(public/private) and signatures are 64 bytes.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .errors import KeyEncodingError

ED25519_PREFIX = "ed25519:"


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode(text + padding)
    except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise KeyEncodingError(f"invalid base64url payload: {text!r}") from exc


def encode_public_key(public_key: Ed25519PublicKey) -> str:
    """Encode a public key as ``ed25519:<base64url>``."""
    raw = public_key.public_bytes_raw()
    return ED25519_PREFIX + _b64u_encode(raw)


def decode_public_key(encoded: str) -> Ed25519PublicKey:
    """Decode an ``ed25519:<base64url>`` public key string."""
    if not encoded.startswith(ED25519_PREFIX):
        raise KeyEncodingError(f"public key must start with {ED25519_PREFIX!r}")
    raw = _b64u_decode(encoded[len(ED25519_PREFIX) :])
    if len(raw) != 32:
        raise KeyEncodingError(f"Ed25519 public key must be 32 bytes, got {len(raw)}")
    return Ed25519PublicKey.from_public_bytes(raw)


def encode_signature(raw: bytes) -> str:
    """Encode a raw 64-byte signature as ``ed25519:<base64url>``."""
    return ED25519_PREFIX + _b64u_encode(raw)


def decode_signature(encoded: str) -> bytes:
    """Decode an ``ed25519:<base64url>`` signature string to raw bytes."""
    if not encoded.startswith(ED25519_PREFIX):
        raise KeyEncodingError(f"signature must start with {ED25519_PREFIX!r}")
    raw = _b64u_decode(encoded[len(ED25519_PREFIX) :])
    if len(raw) != 64:
        raise KeyEncodingError(f"Ed25519 signature must be 64 bytes, got {len(raw)}")
    return raw


@dataclass(frozen=True)
class KeyPair:
    """An Ed25519 key pair with convenience encode/sign helpers."""

    private_key: Ed25519PrivateKey

    @classmethod
    def generate(cls) -> KeyPair:
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_private_str(cls, encoded: str) -> KeyPair:
        if not encoded.startswith(ED25519_PREFIX):
            raise KeyEncodingError(f"private key must start with {ED25519_PREFIX!r}")
        raw = _b64u_decode(encoded[len(ED25519_PREFIX) :])
        if len(raw) != 32:
            raise KeyEncodingError(f"Ed25519 private key must be 32 bytes, got {len(raw)}")
        return cls(Ed25519PrivateKey.from_private_bytes(raw))

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self.private_key.public_key()

    @property
    def public_key_str(self) -> str:
        return encode_public_key(self.public_key)

    @property
    def private_key_str(self) -> str:
        raw = self.private_key.private_bytes_raw()
        return ED25519_PREFIX + _b64u_encode(raw)

    def sign(self, message: bytes) -> str:
        """Sign raw bytes, returning an ``ed25519:<base64url>`` signature."""
        return encode_signature(self.private_key.sign(message))


def verify(public_key: str, message: bytes, signature: str) -> bool:
    """Return True iff ``signature`` is a valid Ed25519 signature of ``message``.

    Malformed keys/signatures return False rather than raising, so callers can
    treat verification as a simple boolean predicate.
    """
    try:
        pub = decode_public_key(public_key)
        raw_sig = decode_signature(signature)
    except KeyEncodingError:
        return False
    try:
        pub.verify(raw_sig, message)
    except InvalidSignature:
        return False
    return True
