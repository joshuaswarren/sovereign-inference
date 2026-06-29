# SPDX-License-Identifier: AGPL-3.0-or-later
"""Issuer — mints fresh, issuer-signed PIC vouchers (bearer credits)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sip_protocol import KeyPair, build_voucher, sign_voucher

from ._time import NowFn, utc_now


class Issuer:
    """Signs new vouchers of a fixed ``unit`` with the issuer's key pair."""

    def __init__(self, keypair: KeyPair, *, unit: str = "pic") -> None:
        self._keypair = keypair
        self._unit = unit

    @property
    def pubkey(self) -> str:
        """The issuer's public key string (the voucher ``issuer_pubkey``)."""
        return self._keypair.public_key_str

    def issue(
        self,
        denomination: str,
        count: int = 1,
        *,
        ttl_seconds: int = 3600,
        now: NowFn = utc_now,
    ) -> list[dict[str, Any]]:
        """Return ``count`` fresh signed vouchers of ``denomination`` ``unit``.

        Each voucher gets a distinct high-entropy ``voucher_id`` and expires
        ``ttl_seconds`` after the injected ``now``.
        """
        issued_at = now()
        expires_at = issued_at + timedelta(seconds=ttl_seconds)
        vouchers: list[dict[str, Any]] = []
        for _ in range(count):
            unsigned = build_voucher(
                denomination=denomination,
                unit=self._unit,
                issuer_pubkey=self.pubkey,
                issued_at=issued_at,
                expires_at=expires_at,
            )
            vouchers.append(sign_voucher(unsigned, self._keypair))
        return vouchers
