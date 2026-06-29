# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for `sin share`: build a shareable provider + announce it."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import sip_pic
import sip_protocol
from sin_cli.cli import main
from sin_cli.share import ShareConfig, announce_to_directory, build_share
from sip_discovery import FileDirectory
from sip_gateway import MockAdapter
from sip_protocol import KeyPair

MODEL = "qwen-coder-7b"


def _config(**overrides: object) -> ShareConfig:
    base: dict[str, object] = {"model": MODEL, "advertised_url": "http://my-node:8090"}
    base.update(overrides)
    return ShareConfig(**base)  # type: ignore[arg-type]


# -- build_share ----------------------------------------------------------------


def test_build_share_produces_a_signed_sovereign_manifest() -> None:
    kp = KeyPair.generate()
    result = build_share(
        _config(input_per_1m=0.2, output_per_1m=0.6, pricing_unit="usdc"), keypair=kp, adapter=MockAdapter()
    )
    m = result.manifest
    assert m["node_type"] == "sovereign-node"
    assert m["models"] == [MODEL]
    assert m["provider_pubkey"] == kp.public_key_str
    assert m["manifest_uri"] == "http://my-node:8090"
    assert m["runtime_adapters"] == ["llama.cpp"]
    assert m["pricing"] == {"unit": "usdc", "input_per_1m": 0.2, "output_per_1m": 0.6}
    assert sip_protocol.verify_provider_manifest(m) is True
    assert result.base_url == "http://my-node:8090"


def test_build_share_app_serves_the_signed_manifest() -> None:
    kp = KeyPair.generate()
    result = build_share(_config(), keypair=kp, adapter=MockAdapter())
    client = TestClient(result.app)
    served = client.get("/sip/v1/provider-manifest").json()
    assert served == result.manifest


def test_build_share_defaults_base_url_to_host_port() -> None:
    kp = KeyPair.generate()
    result = build_share(ShareConfig(model=MODEL, host="0.0.0.0", port=9000), keypair=kp, adapter=MockAdapter())
    assert result.base_url == "http://0.0.0.0:9000"
    assert result.manifest["manifest_uri"] == "http://0.0.0.0:9000"


def test_build_share_enforces_model_allowlist() -> None:
    kp = KeyPair.generate()
    result = build_share(_config(), keypair=kp, adapter=MockAdapter())
    client = TestClient(result.app)
    resp = client.post(
        "/v1/chat/completions", json={"model": "not-shared", "messages": [{"role": "user", "content": "hi"}]}
    )
    assert resp.status_code == 404  # only the shared model is allowed


def test_build_share_requires_payment_when_configured() -> None:
    kp = KeyPair.generate()
    issuer = sip_pic.Issuer(KeyPair.generate(), unit="usdc")
    result = build_share(
        _config(require_payment=True, pic_issuers=(issuer.pubkey,), input_per_1m=10000.0),
        keypair=kp,
        adapter=MockAdapter(),
    )
    client = TestClient(result.app)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": MODEL, "messages": [{"role": "user", "content": "hello there"}]},
    )
    assert resp.status_code == 402  # payment required (the safety/payment envelope is wired)


def test_build_share_applies_input_size_cap() -> None:
    kp = KeyPair.generate()
    result = build_share(_config(max_input_chars=16), keypair=kp, adapter=MockAdapter())
    client = TestClient(result.app)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": MODEL, "messages": [{"role": "user", "content": "x" * 5000}]},
    )
    assert resp.status_code == 413  # the opt-in input-size cap is enforced


def test_build_share_applies_rate_limit_cap() -> None:
    kp = KeyPair.generate()
    result = build_share(_config(rate_limit_per_minute=1), keypair=kp, adapter=MockAdapter())
    client = TestClient(result.app)
    body = {"model": MODEL, "messages": [{"role": "user", "content": "hi"}]}
    first = client.post("/v1/chat/completions", json=body)
    second = client.post("/v1/chat/completions", json=body)
    assert first.status_code == 200
    assert second.status_code == 429  # the opt-in rate cap is enforced


# -- announce_to_directory ------------------------------------------------------


def test_announce_to_directory_makes_provider_discoverable() -> None:
    kp = KeyPair.generate()
    result = build_share(_config(), keypair=kp, adapter=MockAdapter())
    with tempfile.TemporaryDirectory() as d:
        directory = FileDirectory(Path(d) / "providers.json")
        announce_to_directory(directory, result)
        found = directory.discover(model=MODEL)
        assert len(found) == 1
        assert found[0].base_url == "http://my-node:8090"
        assert found[0].provider_pubkey == kp.public_key_str


# -- `sin share --no-serve` CLI -------------------------------------------------


def test_cli_share_no_serve_publishes_and_announces() -> None:
    with tempfile.TemporaryDirectory() as d:
        manifest_path = Path(d) / "manifest.json"
        directory_path = Path(d) / "providers.json"
        code = main(
            [
                "share",
                "--runtime",
                "ollama",
                "--model",
                MODEL,
                "--advertised-url",
                "http://shared-node:8090",
                "--unit",
                "usdc",
                "--input-per-1m",
                "0.2",
                "--manifest-out",
                str(manifest_path),
                "--directory",
                str(directory_path),
                "--no-serve",
            ]
        )
        assert code == 0
        manifest = json.loads(manifest_path.read_text())
        assert manifest["node_type"] == "sovereign-node"
        assert manifest["runtime_adapters"] == ["ollama"]
        assert sip_protocol.verify_provider_manifest(manifest)
        found = FileDirectory(directory_path).discover(model=MODEL)
        assert len(found) == 1
        assert found[0].base_url == "http://shared-node:8090"
