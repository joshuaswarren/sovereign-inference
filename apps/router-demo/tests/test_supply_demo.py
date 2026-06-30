# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration test for the supply demo (hosted directory + reputation + re-announce)."""

from __future__ import annotations

from sip_router_demo.supply_demo import NODE_URL, main


def test_supply_demo_runs_the_full_supply_loop(tmp_path: object) -> None:
    result = main(
        directory_store=str(tmp_path) + "/directory.json",  # type: ignore[operator]
        reputation_store=str(tmp_path) + "/reputation.json",  # type: ignore[operator]
    )
    assert result.exit_code == 0
    assert result.discovered_count == 1
    assert result.served_by == NODE_URL
    assert result.receipt_verified
    assert result.recorded_samples == 1
    assert result.fresh_tps == 55.0  # re-announce surfaced the updated benchmark


def test_supply_demo_default_stores_are_offline() -> None:
    assert main().exit_code == 0
