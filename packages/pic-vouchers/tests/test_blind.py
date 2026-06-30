# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for issuer-unlinkable blind-signature credits (Chaumian-style)."""

from __future__ import annotations

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
    blinded, r = blind(token, key)
    blinded_sig = issuer.sign_blinded(blinded)
    sig = unblind(blinded_sig, r, key)
    assert verify_blind_token(token, sig, key) is True


def test_blinding_is_unlinkable_same_token_differs() -> None:
    # The issuer only ever sees the blinded value; blinding the same token twice
    # yields different blinded messages, so the issuer cannot recognize a token.
    key = _issuer().public
    token = b"same-token"
    b1, _ = blind(token, key)
    b2, _ = blind(token, key)
    assert b1 != b2
    assert b1 != int.from_bytes(token, "big")


def test_forged_signature_is_rejected() -> None:
    key = _issuer().public
    assert verify_blind_token(b"token", 12345, key) is False


def test_signature_from_other_issuer_is_rejected() -> None:
    issuer_a, issuer_b = _issuer(), _issuer()
    token = b"token"
    blinded, r = blind(token, issuer_a.public)
    sig = unblind(issuer_a.sign_blinded(blinded), r, issuer_a.public)
    assert verify_blind_token(token, sig, issuer_a.public) is True
    assert verify_blind_token(token, sig, issuer_b.public) is False


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
