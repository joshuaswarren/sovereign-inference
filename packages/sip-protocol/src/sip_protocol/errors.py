# SPDX-License-Identifier: Apache-2.0
"""Exception types for the SIP-AI protocol primitives."""

from __future__ import annotations


class SIPProtocolError(Exception):
    """Base class for all SIP-AI protocol errors."""


class KeyEncodingError(SIPProtocolError):
    """Raised when an Ed25519 key or signature string is malformed."""


class SchemaValidationError(SIPProtocolError):
    """Raised when a document fails JSON Schema validation."""


class SignatureError(SIPProtocolError):
    """Raised when a document signature is missing or invalid."""
