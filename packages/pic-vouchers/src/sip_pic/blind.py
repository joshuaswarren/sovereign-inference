# SPDX-License-Identifier: AGPL-3.0-or-later
"""Issuer-unlinkable blind-signature credits (Chaumian-ecash style).

Private Inference Credits (PIC) are bearer credits: a provider can't see who the
buyer is. But the *issuer* can still link issuance to redemption, because it sees
the same voucher in both. This module closes that gap with **RSA blind
signatures**: the client blinds a random serial, the issuer signs the blinded
value (learning nothing about the serial), and the client unblinds into a bearer
credit. At redemption the issuer sees a serial it never saw at issuance, so it
cannot link the two — full payer↔issuer unlinkability.

Protocol (textbook RSA blind signatures with an MGF1 full-domain hash):

    m = FDH(token)                      # hash the serial into Z_n
    blinded = m * r^e        (mod n)    # client blinds with random r
    s_blinded = blinded^d    (mod n)    # issuer blind-signs (never sees token)
    s = s_blinded * r^-1     (mod n)    # client unblinds  ->  s = m^d
    verify: s^e == m         (mod n)

**Security status (honest):** the blinding/unlinkability and the issue/redeem
protocol are real and tested. The FDH here is MGF1-over-SHA-256, which is a
reasonable full-domain hash but this scheme has **not had formal review**; treat
it as a v0 of the unlinkable-credit path, not yet a drop-in for the audited PIC
voucher flow. Denomination (``amount``/``unit``) is bound **into the signed
message** — folded into the FDH preimage alongside the serial — so the issuer's
signature covers the value, and any post-issuance mutation of the denomination
invalidates the signature. Using one issuer key per denomination is an optional
additional hardening, not required for value integrity.
"""

from __future__ import annotations

import base64
import hashlib
import math
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.asymmetric import rsa

from .payment import RedeemResult
from .spentset import SpentSet

ISSUER_PREFIX = "rsa-blind:"
_SERIAL_BYTES = 32
RngBytes = Callable[[int], bytes]


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _int_to_b64u(value: int) -> str:
    length = max(1, (value.bit_length() + 7) // 8)
    return _b64u_encode(value.to_bytes(length, "big"))


def _b64u_to_int(text: str) -> int:
    return int.from_bytes(_b64u_decode(text), "big")


@dataclass(frozen=True, slots=True)
class BlindIssuerKey:
    """The public RSA parameters used to blind, verify, and identify an issuer."""

    n: int
    e: int

    def key_bytes(self) -> int:
        """The largest byte length strictly below ``n`` (the FDH output size)."""
        return (self.n.bit_length() - 1) // 8

    def pubkey_str(self) -> str:
        return f"{ISSUER_PREFIX}{_int_to_b64u(self.n)}.{self.e}"

    @classmethod
    def from_str(cls, text: str) -> BlindIssuerKey:
        if not text.startswith(ISSUER_PREFIX):
            raise ValueError(f"not a blind-issuer key: {text[:24]!r}")
        n_b64, _, e_str = text[len(ISSUER_PREFIX) :].partition(".")
        n, e = _b64u_to_int(n_b64), int(e_str)
        # Reject degenerate moduli: n < 3 would crash modular ops (n == 0) or make
        # verification trivially accept anything (n == 1); e must be a real exponent.
        if n < 3 or e < 2:
            raise ValueError(f"degenerate issuer key (n={n}, e={e})")
        return cls(n=n, e=e)


class BlindIssuer:
    """An RSA blind-signature issuer; holds the private exponent ``d``."""

    def __init__(self, *, n: int, e: int, d: int) -> None:
        self._n = n
        self._e = e
        self._d = d

    @classmethod
    def generate(cls, *, key_size: int = 2048) -> BlindIssuer:
        private = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
        numbers = private.private_numbers()
        public = numbers.public_numbers
        return cls(n=public.n, e=public.e, d=numbers.d)

    @property
    def public(self) -> BlindIssuerKey:
        return BlindIssuerKey(n=self._n, e=self._e)

    def sign_blinded(self, blinded: int) -> int:
        """Raw-RSA blind-sign a blinded message (the issuer never sees the token)."""
        if not 0 < blinded < self._n:
            raise ValueError("blinded message out of range")
        return pow(blinded, self._d, self._n)


def _mgf1(seed: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        counter += 1
    return bytes(out[:length])


def _denomination_bytes(amount: str, unit: str) -> bytes:
    """Unambiguous, length-prefixed encoding of a credit's denomination.

    Length-prefixing prevents field-confusion (e.g. amount="1"+unit="0PIC"
    hashing the same as amount="10"+unit="PIC") and keeps distinct values
    distinct. Encoded exactly as the strings that live on the credit, so the
    issuer signs, and the redeemer checks, byte-for-byte the same value.
    """
    a = amount.encode("utf-8")
    u = unit.encode("utf-8")
    return len(a).to_bytes(4, "big") + a + len(u).to_bytes(4, "big") + u


def _fdh(token: bytes, amount: str, unit: str, key: BlindIssuerKey) -> int:
    """Full-domain hash of ``(serial, amount, unit)`` into Z_n via MGF1-over-SHA-256.

    Binding amount||unit into the preimage means the issuer's signature covers
    the denomination: mutating amount or unit after issuance changes m, so
    verification fails. The domain tag is bumped to sip-blind-fdh-v2 so a v1
    (value-unbound) signature can never satisfy a v2 verification and vice versa.
    """
    preimage = b"sip-blind-fdh-v2:" + token + _denomination_bytes(amount, unit)
    digest = _mgf1(preimage, key.key_bytes())
    return int.from_bytes(digest, "big") % key.n


def _random_unit(n: int, rng: RngBytes) -> int:
    nbytes = (n.bit_length() + 7) // 8
    while True:
        r = int.from_bytes(rng(nbytes), "big") % n
        if r > 1 and math.gcd(r, n) == 1:
            return r


def blind(
    token: bytes,
    amount: str,
    unit: str,
    key: BlindIssuerKey,
    *,
    rng: RngBytes = secrets.token_bytes,
) -> tuple[int, int]:
    """Blind ``token`` for ``key``; return ``(blinded_message, blinding_factor)``.

    The denomination (``amount``, ``unit``) is folded into the FDH preimage so
    the issuer's blind signature covers the value, not just the serial.
    """
    m = _fdh(token, amount, unit, key)
    r = _random_unit(key.n, rng)
    blinded = (m * pow(r, key.e, key.n)) % key.n
    return blinded, r


def unblind(blinded_sig: int, r: int, key: BlindIssuerKey) -> int:
    """Remove the blinding factor from a blind signature, yielding ``m^d``."""
    r_inv = pow(r, -1, key.n)
    return (blinded_sig * r_inv) % key.n


def verify_blind_token(token: bytes, amount: str, unit: str, sig: int, key: BlindIssuerKey) -> bool:
    """True if ``sig`` is a valid issuer signature over ``(token, amount, unit)``."""
    return pow(sig, key.e, key.n) == _fdh(token, amount, unit, key)


# -- the unlinkable credit flow -------------------------------------------------


@dataclass(frozen=True, slots=True)
class BlindCreditRequest:
    """What the client sends the issuer: only the blinded message + metadata."""

    blinded: int
    unit: str
    amount: str
    issuer: str


@dataclass(frozen=True, slots=True)
class BlindingSecret:
    """The client's private state needed to unblind (never sent to the issuer)."""

    token: bytes
    r: int
    unit: str
    amount: str
    key: BlindIssuerKey


@dataclass(frozen=True, slots=True)
class BlindCredit:
    """An issuer-unlinkable bearer credit, ready to redeem."""

    unit: str
    amount: str
    issuer: str
    token: str
    signature: str


def blind_credit_request(
    key: BlindIssuerKey,
    *,
    unit: str,
    amount: str,
    rng: RngBytes = secrets.token_bytes,
) -> tuple[BlindCreditRequest, BlindingSecret]:
    """Client side: pick a random serial and blind it for ``key``."""
    token = rng(_SERIAL_BYTES)
    blinded, r = blind(token, amount, unit, key, rng=rng)
    request = BlindCreditRequest(blinded=blinded, unit=unit, amount=amount, issuer=key.pubkey_str())
    secret = BlindingSecret(token=token, r=r, unit=unit, amount=amount, key=key)
    return request, secret


def finalize_blind_credit(blinded_sig: int, secret: BlindingSecret) -> BlindCredit:
    """Client side: unblind the issuer's signature into a bearer credit."""
    sig = unblind(blinded_sig, secret.r, secret.key)
    return BlindCredit(
        unit=secret.unit,
        amount=secret.amount,
        issuer=secret.key.pubkey_str(),
        token=_b64u_encode(secret.token),
        signature=_int_to_b64u(sig),
    )


def verify_blind_credit(credit: BlindCredit) -> bool:
    """True if the credit carries a valid issuer signature over its serial AND denomination (amount/unit)."""
    try:
        key = BlindIssuerKey.from_str(credit.issuer)
        token = _b64u_decode(credit.token)
        sig = _b64u_to_int(credit.signature)
    except (ValueError, TypeError):
        return False
    return verify_blind_token(token, credit.amount, credit.unit, sig, key)


def redeem_blind_credit(
    credit: BlindCredit,
    *,
    price: str,
    unit: str,
    issuer_keys: list[str],
    spent_set: SpentSet,
    now: Any = None,
) -> RedeemResult:
    """Redeem an unlinkable credit: check issuer, signature, amount, double-spend.

    The serial is only revealed here (never at issuance), so the issuer cannot
    link this redemption to who it was issued to.
    """
    if credit.issuer not in set(issuer_keys):
        return RedeemResult(ok=False, scheme="blind", total="0", reason="unknown_issuer")
    if not verify_blind_credit(credit):
        return RedeemResult(ok=False, scheme="blind", total="0", reason="bad_signature")
    if credit.unit != unit or credit.amount != price:
        return RedeemResult(ok=False, scheme="blind", total="0", reason="amount_mismatch")
    spend_key = f"blind:{credit.issuer}:{credit.token}"
    if spent_set.is_spent(spend_key):
        return RedeemResult(ok=False, scheme="blind", total="0", reason="double_spend")
    spent_set.spend(spend_key)
    return RedeemResult(ok=True, scheme="blind", total=credit.amount, reason="")
