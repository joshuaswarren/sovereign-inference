# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration test for the discovery demo (announce → discover → route)."""

from __future__ import annotations

from sip_router_demo.discovery_demo import NODE_URL, main


def test_discovery_demo_announces_discovers_and_routes(tmp_path: object) -> None:
    result = main(directory_path=str(tmp_path) + "/providers.json")  # type: ignore[operator]
    assert result.exit_code == 0
    assert result.discovered_count == 1
    assert result.served_by == NODE_URL
    assert result.receipt_verified


def test_discovery_demo_default_directory_is_offline() -> None:
    assert main().exit_code == 0
