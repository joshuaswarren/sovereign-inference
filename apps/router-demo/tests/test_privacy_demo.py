# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration test for the privacy demo (attestation + blind credit + relay)."""

from __future__ import annotations

from sip_router_demo.privacy_demo import main


def test_privacy_demo_runs_all_three_privacy_modes() -> None:
    result = main()
    assert result.exit_code == 0
    assert result.provider_attested is True
    assert result.credit_unlinkable is True
    assert result.double_spend_blocked is True
    assert result.relayed_receipt_verified is True
    assert result.tamper_detected is True
