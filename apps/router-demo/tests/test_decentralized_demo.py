# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration test for the decentralized (Phase 4) demo."""

from __future__ import annotations

import sip_protocol
from sip_arweave import LocalAnchor, resolve_json
from sip_compute import DeploymentStatus
from sip_router_demo.decentralized_demo import (
    NODE_URL,
    fake_nosana_cli,
    main,
    provision_node,
)


def test_provision_node_reaches_ready_with_endpoint() -> None:
    deployment = provision_node(NODE_URL)
    assert deployment.status == DeploymentStatus.RUNNING
    assert deployment.endpoint == NODE_URL
    assert deployment.is_ready
    assert deployment.provider == "nosana"


def test_fake_cli_drives_post_then_running() -> None:
    run = fake_nosana_cli("http://example-node")
    import json

    post = json.loads(run(["nosana", "job", "post", "--file", "x"]))
    assert post["job"]
    got = json.loads(run(["nosana", "job", "get", post["job"], "--format", "json"]))
    assert got["state"] == "RUNNING"
    assert got["serviceUrl"] == "http://example-node"


def test_main_runs_full_decentralized_loop(tmp_path: object) -> None:
    anchor = LocalAnchor(tmp_path)  # type: ignore[arg-type]
    result = main(anchor=anchor)
    assert result.exit_code == 0
    # the external-adapter manifest and the receipt were both anchored & resolvable
    manifest = resolve_json(anchor, result.manifest_uri)
    assert manifest["node_type"] == "external-adapter"
    assert manifest["manifest_uri"] == NODE_URL
    assert sip_protocol.verify_provider_manifest(manifest)
    receipt = resolve_json(anchor, result.receipt_uri)
    assert sip_protocol.verify_receipt(receipt).valid
    assert result.input_tokens > 0


def test_main_default_anchor_is_offline() -> None:
    # With no anchor injected, the demo uses a local temp anchor and still succeeds.
    assert main().exit_code == 0
