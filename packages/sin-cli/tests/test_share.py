# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for `sin share`: build a shareable provider + announce it."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

import sip_pic
import sip_protocol
from sin_cli.cli import main
from sin_cli.share import ShareConfig, announce_to_directory, build_share, reannounce
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


# -- benchmark embedding + re-announce ------------------------------------------


def test_build_share_embeds_benchmark_when_configured() -> None:
    kp = KeyPair.generate()
    result = build_share(
        _config(benchmark={"tokens_per_second": 33.0, "ttft_ms": 600}), keypair=kp, adapter=MockAdapter()
    )
    assert result.manifest["benchmark"]["tokens_per_second"] == 33.0
    assert sip_protocol.verify_provider_manifest(result.manifest)


def test_reannounce_publishes_fresh_manifest_with_benchmark() -> None:
    kp = KeyPair.generate()
    config = _config(benchmark={"tokens_per_second": 42.0, "ttft_ms": 480})
    with tempfile.TemporaryDirectory() as d:
        directory = FileDirectory(Path(d) / "providers.json")
        reannounce(directory, config, keypair=kp, runtime_name="ollama")
        found = directory.discover(model=MODEL)
        assert len(found) == 1
        assert found[0].manifest["benchmark"]["tokens_per_second"] == 42.0
        assert found[0].provider_pubkey == kp.public_key_str
        assert found[0].manifest["runtime_adapters"] == ["ollama"]


def test_reannounce_supersedes_older_announcement() -> None:
    kp = KeyPair.generate()
    older = lambda: datetime(2026, 6, 29, tzinfo=UTC)  # noqa: E731
    newer = lambda: datetime(2026, 6, 30, tzinfo=UTC)  # noqa: E731
    with tempfile.TemporaryDirectory() as d:
        directory = FileDirectory(Path(d) / "providers.json")
        reannounce(
            directory,
            _config(benchmark={"tokens_per_second": 10.0, "ttft_ms": 900}),
            keypair=kp,
            runtime_name="ollama",
            now=older,
        )
        reannounce(
            directory,
            _config(benchmark={"tokens_per_second": 55.0, "ttft_ms": 300}),
            keypair=kp,
            runtime_name="ollama",
            now=newer,
        )
        found = directory.discover()
        assert len(found) == 1  # freshest-per-pubkey wins
        assert found[0].manifest["benchmark"]["tokens_per_second"] == 55.0


def test_cli_benchmark_announce_updates_directory(monkeypatch: object) -> None:
    from sin_node.models import BenchmarkResult

    fake = BenchmarkResult(model_alias=MODEL, runtime="ollama", ttft_ms=300.0, tokens_per_second=48.5)

    def fake_benchmark(base_url: str, model: str, *, runtime: str) -> BenchmarkResult:
        return fake

    import sin_cli.cli as cli

    monkeypatch.setattr(cli, "benchmark_endpoint", fake_benchmark)  # type: ignore[attr-defined]

    kp = KeyPair.generate()
    with tempfile.TemporaryDirectory() as d:
        key_path = Path(d) / "key.json"
        key_path.write_text(json.dumps({"private_key": kp.private_key_str}))
        directory_path = Path(d) / "providers.json"
        code = main(
            [
                "benchmark",
                "--base-url",
                "http://localhost:8080",
                "--model",
                MODEL,
                "--runtime",
                "ollama",
                "--publish",
                str(key_path),
                "--advertised-url",
                "http://my-node:8090",
                "--announce",
                str(directory_path),
            ]
        )
        assert code == 0
        found = FileDirectory(directory_path).discover(model=MODEL)
        assert len(found) == 1
        assert found[0].base_url == "http://my-node:8090"
        assert found[0].manifest["benchmark"]["tokens_per_second"] == 48.5


def test_cli_benchmark_announce_bad_key_returns_1(monkeypatch: object) -> None:
    from sin_node.models import BenchmarkResult

    fake = BenchmarkResult(model_alias=MODEL, runtime="ollama", ttft_ms=300.0, tokens_per_second=48.5)

    import sin_cli.cli as cli

    monkeypatch.setattr(cli, "benchmark_endpoint", lambda *_a, **_k: fake)  # type: ignore[attr-defined]

    with tempfile.TemporaryDirectory() as d:
        key_path = Path(d) / "key.json"
        key_path.write_text(json.dumps({"private_key": "ed25519:not-a-valid-key"}))  # malformed
        code = main(
            [
                "benchmark",
                "--base-url",
                "http://localhost:8080",
                "--model",
                MODEL,
                "--publish",
                str(key_path),
                "--advertised-url",
                "http://my-node:8090",
                "--announce",
                str(Path(d) / "providers.json"),
            ]
        )
        assert code == 1  # a bad key surfaces as a clean exit 1, not a traceback
