# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for issuer-unlinkable blind-signature credits (Chaumian-style)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from sip_pic import SpentSet
from sip_pic.blind import (
    BlindIssuer,
    BlindIssuerKey,
    blind,
    blind_credit_request,
    finalize_blind_credit,
    redeem_blind_credit,
    unblind,
    verify_blind_credit,
    verify_blind_token,
)

# A small key keeps the test fast; production uses >= 2048.
_KEY_SIZE = 1024


def _issuer() -> BlindIssuer:
    return BlindIssuer.generate(key_size=_KEY_SIZE)


# -- raw blind-signature math ---------------------------------------------------


def test_blind_unblind_round_trip_verifies() -> None:
    issuer = _issuer()
    key = issuer.public
    token = b"a-random-serial-number"
    blinded, r = blind(token, "0.10", "pic", key)
    blinded_sig = issuer.sign_blinded(blinded)
    sig = unblind(blinded_sig, r, key)
    assert verify_blind_token(token, "0.10", "pic", sig, key) is True


def test_blinding_is_unlinkable_same_token_differs() -> None:
    # The issuer only ever sees the blinded value; blinding the same token twice
    # yields different blinded messages, so the issuer cannot recognize a token.
    key = _issuer().public
    token = b"same-token"
    b1, _ = blind(token, "0.10", "pic", key)
    b2, _ = blind(token, "0.10", "pic", key)
    assert b1 != b2
    assert b1 != int.from_bytes(token, "big")


def test_forged_signature_is_rejected() -> None:
    key = _issuer().public
    assert verify_blind_token(b"token", "0.10", "pic", 12345, key) is False


def test_signature_from_other_issuer_is_rejected() -> None:
    issuer_a, issuer_b = _issuer(), _issuer()
    token = b"token"
    blinded, r = blind(token, "0.10", "pic", issuer_a.public)
    sig = unblind(issuer_a.sign_blinded(blinded), r, issuer_a.public)
    assert verify_blind_token(token, "0.10", "pic", sig, issuer_a.public) is True
    assert verify_blind_token(token, "0.10", "pic", sig, issuer_b.public) is False


# -- issuer key serialization ---------------------------------------------------


def test_issuer_key_str_round_trips() -> None:
    key = _issuer().public
    restored = BlindIssuerKey.from_str(key.pubkey_str())
    assert restored.n == key.n
    assert restored.e == key.e


# -- the full unlinkable credit flow --------------------------------------------


def test_credit_flow_issuer_never_sees_the_token() -> None:
    issuer = _issuer()
    # client: build a request (issuer only receives `request.blinded`)
    request, secret = blind_credit_request(issuer.public, unit="pic", amount="0.10")
    assert request.blinded != int.from_bytes(secret.token, "big")
    # issuer: blind-sign without learning the token
    blinded_sig = issuer.sign_blinded(request.blinded)
    # client: unblind into a bearer credit
    credit = finalize_blind_credit(blinded_sig, secret)
    assert verify_blind_credit(credit) is True
    assert credit.unit == "pic"
    assert credit.amount == "0.10"


def test_redeem_blind_credit_then_double_spend_rejected() -> None:
    issuer = _issuer()
    request, secret = blind_credit_request(issuer.public, unit="pic", amount="0.10")
    credit = finalize_blind_credit(issuer.sign_blinded(request.blinded), secret)
    spent = SpentSet()

    first = redeem_blind_credit(
        credit, price="0.10", unit="pic", issuer_keys=[issuer.public.pubkey_str()], spent_set=spent
    )
    assert first.ok is True
    assert first.total == "0.10"

    replay = redeem_blind_credit(
        credit, price="0.10", unit="pic", issuer_keys=[issuer.public.pubkey_str()], spent_set=spent
    )
    assert replay.ok is False
    assert replay.reason == "double_spend"


def test_redeem_rejects_unknown_issuer() -> None:
    issuer, other = _issuer(), _issuer()
    request, secret = blind_credit_request(issuer.public, unit="pic", amount="0.10")
    credit = finalize_blind_credit(issuer.sign_blinded(request.blinded), secret)
    result = redeem_blind_credit(
        credit, price="0.10", unit="pic", issuer_keys=[other.public.pubkey_str()], spent_set=SpentSet()
    )
    assert result.ok is False
    assert result.reason in {"unknown_issuer", "bad_signature"}


def test_redeem_rejects_wrong_price() -> None:
    issuer = _issuer()
    request, secret = blind_credit_request(issuer.public, unit="pic", amount="0.10")
    credit = finalize_blind_credit(issuer.sign_blinded(request.blinded), secret)
    result = redeem_blind_credit(
        credit, price="0.99", unit="pic", issuer_keys=[issuer.public.pubkey_str()], spent_set=SpentSet()
    )
    assert result.ok is False


def test_redeem_rejects_forged_credit() -> None:
    issuer = _issuer()
    _request, secret = blind_credit_request(issuer.public, unit="pic", amount="0.10")
    # a credit whose signature was never produced by the issuer
    forged = finalize_blind_credit(12345, secret)
    assert verify_blind_credit(forged) is False
    result = redeem_blind_credit(
        forged, price="0.10", unit="pic", issuer_keys=[issuer.public.pubkey_str()], spent_set=SpentSet()
    )
    assert result.ok is False
    assert result.reason == "bad_signature"


# -- regression: denomination must be covered by the issuer signature (#23) ----


def test_mutating_amount_fails_verification() -> None:
    """A credit's amount is bound into the issuer signature; rewriting it must
    invalidate verification. (Regression for the denomination-forgery bug.)"""
    issuer = _issuer()
    key = issuer.public
    request, secret = blind_credit_request(key, unit="PIC", amount="1")
    credit = finalize_blind_credit(issuer.sign_blinded(request.blinded), secret)
    forged = replace(credit, amount="1000000")
    assert verify_blind_credit(forged) is False


def test_mutating_amount_fails_redemption() -> None:
    """A forged-amount credit must be rejected at redemption as bad_signature,
    not redeemed for the forged value."""
    issuer = _issuer()
    key = issuer.public
    request, secret = blind_credit_request(key, unit="PIC", amount="1")
    credit = finalize_blind_credit(issuer.sign_blinded(request.blinded), secret)
    forged = replace(credit, amount="1000000")
    result = redeem_blind_credit(
        forged,
        price="1000000",
        unit="PIC",
        issuer_keys=[key.pubkey_str()],
        spent_set=SpentSet(),
    )
    assert result.ok is False
    assert result.reason == "bad_signature"


def test_mutating_unit_fails_verification() -> None:
    """Rewriting the unit must also invalidate verification."""
    issuer = _issuer()
    key = issuer.public
    request, secret = blind_credit_request(key, unit="PIC", amount="1")
    credit = finalize_blind_credit(issuer.sign_blinded(request.blinded), secret)
    forged = replace(credit, unit="GOLD")
    assert verify_blind_credit(forged) is False


def test_unmodified_credit_still_verifies_and_redeems() -> None:
    """Happy path: a legitimately-issued credit still verifies and redeems
    (guards against over-tightening the denomination binding)."""
    issuer = _issuer()
    key = issuer.public
    request, secret = blind_credit_request(key, unit="pic", amount="0.10")
    credit = finalize_blind_credit(issuer.sign_blinded(request.blinded), secret)
    assert verify_blind_credit(credit) is True
    result = redeem_blind_credit(
        credit,
        price="0.10",
        unit="pic",
        issuer_keys=[key.pubkey_str()],
        spent_set=SpentSet(),
    )
    assert result.ok is True
    assert result.total == "0.10"


def test_amount_denomination_binding_is_field_confusion_safe() -> None:
    """Length-prefixed encoding defeats field confusion: a credit with
    amount="1", unit="0PIC" must not be confusable with amount="10", unit="PIC".
    Cross-assigning the denomination via replace must fail verification."""
    issuer = _issuer()
    key = issuer.public

    req_a, secret_a = blind_credit_request(key, unit="0PIC", amount="1")
    credit_a = finalize_blind_credit(issuer.sign_blinded(req_a.blinded), secret_a)

    req_b, secret_b = blind_credit_request(key, unit="PIC", amount="10")
    credit_b = finalize_blind_credit(issuer.sign_blinded(req_b.blinded), secret_b)

    # Each verifies on its own.
    assert verify_blind_credit(credit_a) is True
    assert verify_blind_credit(credit_b) is True

    # Cross-assign: credit_a's signature with credit_b's denomination.
    confused_ab = replace(credit_a, amount=credit_b.amount, unit=credit_b.unit)
    assert verify_blind_credit(confused_ab) is False

    # And the reverse.
    confused_ba = replace(credit_b, amount=credit_a.amount, unit=credit_a.unit)
    assert verify_blind_credit(confused_ba) is False


def test_unicode_unit_round_trips() -> None:
    """A non-ASCII unit label must round-trip through issue/verify/redeem, and
    mutating it must fail verification (UTF-8 byte-length is what is signed)."""
    issuer = _issuer()
    key = issuer.public
    request, secret = blind_credit_request(key, unit="\u03c0-credit", amount="1")
    credit = finalize_blind_credit(issuer.sign_blinded(request.blinded), secret)
    assert verify_blind_credit(credit) is True
    result = redeem_blind_credit(
        credit,
        price="1",
        unit="\u03c0-credit",
        issuer_keys=[key.pubkey_str()],
        spent_set=SpentSet(),
    )
    assert result.ok is True
    assert result.total == "1"

    forged = replace(credit, unit="\u03c0-CREDIT")
    assert verify_blind_credit(forged) is False


# -- robustness: degenerate / malformed issuer keys -----------------------------


def test_blind_issuer_key_rejects_degenerate_modulus() -> None:
    from sip_pic.blind import BlindIssuerKey

    with pytest.raises(ValueError, match="degenerate"):
        BlindIssuerKey.from_str("rsa-blind:AA.65537")  # n == 0


def test_verify_blind_credit_is_total_on_degenerate_issuer() -> None:
    from sip_pic.blind import BlindCredit, verify_blind_credit

    # n == 0 (would crash modulo/pow) and n == 1 (would trivially "verify") must
    # both yield a clean False, never a crash or a forgery acceptance.
    for bad_n in ("AA", "AQ"):  # b64u(0), b64u(1)
        credit = BlindCredit(unit="pic", amount="0.10", issuer=f"rsa-blind:{bad_n}.65537", token="eHg", signature="AQ")
        assert verify_blind_credit(credit) is False
