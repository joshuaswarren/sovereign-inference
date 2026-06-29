# SPDX-License-Identifier: Apache-2.0
"""Tests for anchoring SIP-AI provenance to durable storage."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from sip_arweave import (
    AnchorError,
    ArweaveAnchor,
    LocalAnchor,
    anchor_json,
    anchor_manifest,
    anchor_receipt,
    resolve_json,
)
from sip_protocol.hashing import hash_response_body
from sip_protocol.manifests import sign_provider_manifest
from sip_protocol.receipts import build_receipt, sign_receipt
from sip_protocol.signing import KeyPair


def _signed_provider_manifest(keypair: KeyPair) -> dict[str, object]:
    manifest = {
        "schema": "sip-ai.provider_manifest.v1",
        "provider_pubkey": keypair.public_key_str,
        "node_type": "external-adapter",
        "models": ["qwen-coder-7b"],
        "runtime_adapters": ["nosana"],
        "pricing": {"unit": "usdc"},
        "max_context": 4096,
        "logging_policy": "no_prompt_logging",
        "privacy_modes": ["direct"],
        "published_at": "2026-06-29T00:00:00Z",
    }
    return sign_provider_manifest(manifest, keypair)


def _signed_receipt(keypair: KeyPair) -> dict[str, object]:
    moment = datetime(2026, 6, 29, tzinfo=UTC)
    return sign_receipt(
        build_receipt(
            request_id="req-1",
            provider_pubkey=keypair.public_key_str,
            model_manifest_hash="sha256:" + "0" * 64,
            model_alias="qwen-coder-7b",
            runtime="vllm",
            input_tokens=1,
            output_tokens=1,
            price_units="usdc",
            price_amount="0.000003",
            privacy_mode="direct",
            started_at=moment,
            completed_at=moment,
            response_hash=hash_response_body(b"hi"),
        ),
        keypair,
    )


# -- LocalAnchor ----------------------------------------------------------------


def test_local_anchor_round_trips_bytes(tmp_path: object) -> None:
    anchor = LocalAnchor(tmp_path)  # type: ignore[arg-type]
    uri = anchor.put(b"hello world", content_type="text/plain")
    assert uri.startswith("local://")
    assert anchor.get(uri) == b"hello world"


def test_local_anchor_is_content_addressed() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        anchor = LocalAnchor(d)
        uri_a = anchor.put(b"same")
        uri_b = anchor.put(b"same")
        assert uri_a == uri_b  # identical content -> identical URI


def test_local_anchor_rejects_foreign_scheme() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        anchor = LocalAnchor(d)
        with pytest.raises(AnchorError):
            anchor.get("ar://deadbeef")


def test_local_anchor_missing_object_raises() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        anchor = LocalAnchor(d)
        with pytest.raises(AnchorError):
            anchor.get("local://0000000000000000000000000000000000000000000000000000000000000000")


# -- JSON helpers ---------------------------------------------------------------


def test_anchor_json_and_resolve_round_trip() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        anchor = LocalAnchor(d)
        obj = {"b": 2, "a": 1, "nested": {"y": True, "x": None}}
        uri = anchor_json(anchor, obj)
        assert resolve_json(anchor, uri) == obj


def test_anchor_receipt_verifies_before_anchoring() -> None:
    import tempfile

    keypair = KeyPair.generate()
    receipt = _signed_receipt(keypair)
    with tempfile.TemporaryDirectory() as d:
        anchor = LocalAnchor(d)
        uri = anchor_receipt(anchor, receipt)
        assert resolve_json(anchor, uri) == receipt


def test_anchor_receipt_rejects_tampered_receipt() -> None:
    import tempfile

    keypair = KeyPair.generate()
    receipt = _signed_receipt(keypair)
    receipt["model_alias"] = "tampered"
    with tempfile.TemporaryDirectory() as d:
        anchor = LocalAnchor(d)
        with pytest.raises(AnchorError):
            anchor_receipt(anchor, receipt)


def test_anchor_receipt_tags_with_receipt_version_not_a_hardcoded_default() -> None:
    # The provenance tag must track the receipt's real version field
    # (receipt_version), not a missing 'schema' key that always falls back.
    keypair = KeyPair.generate()
    receipt = _signed_receipt(keypair)
    captured: dict[str, object] = {}

    def submitter(data: bytes, content_type: str, tags: dict[str, str]) -> str:
        captured["tags"] = tags
        return "TXR"

    anchor = ArweaveAnchor(submitter=submitter)
    anchor_receipt(anchor, receipt)
    tags = captured["tags"]
    assert isinstance(tags, dict)
    assert tags["SIP-AI"] == receipt["receipt_version"]


def test_anchor_manifest_round_trips_signed_provider_manifest() -> None:
    import tempfile

    keypair = KeyPair.generate()
    manifest = _signed_provider_manifest(keypair)
    with tempfile.TemporaryDirectory() as d:
        anchor = LocalAnchor(d)
        uri = anchor_manifest(anchor, manifest)
        assert resolve_json(anchor, uri) == manifest


def test_anchor_manifest_rejects_tampered_provider_manifest() -> None:
    import tempfile

    keypair = KeyPair.generate()
    manifest = _signed_provider_manifest(keypair)
    manifest["models"] = ["evil-model"]  # invalidates the signature
    with tempfile.TemporaryDirectory() as d:
        anchor = LocalAnchor(d)
        with pytest.raises(AnchorError):
            anchor_manifest(anchor, manifest)


# -- ArweaveAnchor --------------------------------------------------------------


def test_arweave_anchor_get_resolves_via_gateway() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/abc123"
        return httpx.Response(200, content=b'{"ok": true}')

    client = httpx.Client(transport=httpx.MockTransport(handler))
    anchor = ArweaveAnchor(gateway="https://arweave.net", client=client)
    assert anchor.get("ar://abc123") == b'{"ok": true}'


def test_arweave_anchor_put_uses_injected_submitter() -> None:
    captured: dict[str, object] = {}

    def submitter(data: bytes, content_type: str, tags: dict[str, str]) -> str:
        captured["data"] = data
        captured["content_type"] = content_type
        captured["tags"] = tags
        return "TX_ID_42"

    anchor = ArweaveAnchor(submitter=submitter)
    uri = anchor.put(b"payload", content_type="application/json", tags={"App-Name": "SIP-AI"})
    assert uri == "ar://TX_ID_42"
    assert captured["data"] == b"payload"
    assert captured["content_type"] == "application/json"
    assert captured["tags"] == {"App-Name": "SIP-AI"}


def test_arweave_anchor_put_without_submitter_raises() -> None:
    anchor = ArweaveAnchor()
    with pytest.raises(AnchorError):
        anchor.put(b"payload")


def test_arweave_anchor_get_http_error_raises_anchor_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    anchor = ArweaveAnchor(client=client)
    with pytest.raises(AnchorError):
        anchor.get("ar://missing")


def test_arweave_anchor_rejects_foreign_scheme() -> None:
    anchor = ArweaveAnchor()
    with pytest.raises(AnchorError):
        anchor.get("local://abc")


def test_arweave_json_round_trip_through_mock_network() -> None:
    store: dict[str, bytes] = {}

    def submitter(data: bytes, content_type: str, tags: dict[str, str]) -> str:
        tx = f"tx{len(store)}"
        store[tx] = data
        return tx

    def handler(request: httpx.Request) -> httpx.Response:
        tx = request.url.path.lstrip("/")
        if tx in store:
            return httpx.Response(200, content=store[tx])
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    anchor = ArweaveAnchor(client=client, submitter=submitter)
    obj = {"hello": "world", "n": 7}
    uri = anchor_json(anchor, obj)
    assert resolve_json(anchor, uri) == obj
