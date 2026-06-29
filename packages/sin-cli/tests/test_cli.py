# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the ``sin`` command-line interface.

Every test injects fakes (monkeypatched module-level callables) so no subprocess
is spawned, no server is started, and the network is never touched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sin_cli import cli
from sin_node.models import (
    Accelerator,
    BenchmarkResult,
    CPUInfo,
    HardwareProfile,
    MemoryEstimate,
    Recommendation,
)


def _fake_profile() -> HardwareProfile:
    return HardwareProfile(
        os="Darwin",
        os_version="15.0",
        arch="arm64",
        cpu=CPUInfo(arch="arm64", model="Apple M3", physical_cores=8, logical_cores=8, features=["neon"]),
        ram_total_gb=24.0,
        ram_available_gb=18.0,
        disk_free_gb=200.0,
        gpus=[],
        accelerator=Accelerator.metal,
        unified_memory=True,
        runtimes=[],
        on_battery=False,
    )


def _fake_recommendation() -> Recommendation:
    return Recommendation(
        model_id="qwen-coder-7b",
        display_name="Qwen Coder 7B",
        runtime="llama.cpp",
        quant="q4_k_m",
        context=4096,
        estimate=MemoryEstimate(weights_gb=4.0, kv_cache_gb=0.5, overhead_gb=0.7, total_gb=5.2),
        fits=True,
        headroom_ratio=3.4,
        predicted_tps=42.0,
        quality_score=0.8,
        score=1.5,
        why="fits nicely",
        tradeoffs=["aggressively quantized"],
    )


# ---------------------------------------------------------------- scan


def test_scan_json_emits_profile(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli.hardware, "scan", lambda **_: _fake_profile())

    code = cli.main(["scan", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["accelerator"] == "metal"
    assert payload["os"] == "Darwin"


def test_scan_human_renders_summary(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli.hardware, "scan", lambda **_: _fake_profile())

    code = cli.main(["scan"])

    assert code == 0
    out = capsys.readouterr().out
    assert "Darwin" in out
    assert "metal" in out


# ---------------------------------------------------------------- recommend


def test_recommend_json_emits_list(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli.hardware, "scan", lambda **_: _fake_profile())
    monkeypatch.setattr(cli.recommend, "recommend", lambda *a, **k: [_fake_recommendation()])

    code = cli.main(["recommend", "--task", "coding", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert payload[0]["model_id"] == "qwen-coder-7b"


def test_recommend_passes_task_and_flags(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    captured: dict[str, Any] = {}

    monkeypatch.setattr(cli.hardware, "scan", lambda **_: _fake_profile())

    def _fake_recommend(profile: HardwareProfile, task: str, **kwargs: Any) -> list[Recommendation]:
        captured["task"] = task
        captured["commercial_required"] = kwargs.get("commercial_required")
        captured["top_k"] = kwargs.get("top_k")
        return [_fake_recommendation()]

    monkeypatch.setattr(cli.recommend, "recommend", _fake_recommend)

    code = cli.main(["recommend", "--task", "coding", "--commercial", "--top", "5"])

    assert code == 0
    assert captured["task"] == "coding"
    assert captured["commercial_required"] is True
    assert captured["top_k"] == 5


def test_recommend_human_renders_table(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli.hardware, "scan", lambda **_: _fake_profile())
    monkeypatch.setattr(cli.recommend, "recommend", lambda *a, **k: [_fake_recommendation()])

    code = cli.main(["recommend", "--task", "coding"])

    assert code == 0
    assert "Qwen Coder 7B" in capsys.readouterr().out


def test_recommend_rejects_nonpositive_top() -> None:
    # argparse rejects --top 0/-1 cleanly (exit code 2) before recommend() runs.
    for bad in ("0", "-1"):
        with pytest.raises(SystemExit) as exc:
            cli.main(["recommend", "--task", "coding", "--top", bad])
        assert exc.value.code == 2


# ---------------------------------------------------------------- catalog


def test_catalog_json_emits_models(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["catalog", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert all("model_id" in entry for entry in payload)


def test_catalog_human(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["catalog"])

    assert code == 0
    assert capsys.readouterr().out.strip() != ""


# ---------------------------------------------------------------- serve


def test_serve_prints_base_url(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class _FakeHandle:
        base_url = "http://localhost:8080"

    class _FakeAdapter:
        def serve(self, model: str, **kwargs: Any) -> _FakeHandle:
            return _FakeHandle()

    monkeypatch.setattr(cli, "get_adapter", lambda name, *a, **k: _FakeAdapter())

    code = cli.main(["serve", "--runtime", "llama.cpp", "--model", "/tmp/model.gguf", "--port", "8080"])

    assert code == 0
    assert "http://localhost:8080" in capsys.readouterr().out


def test_serve_unknown_runtime_returns_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _boom(name: str, *a: Any, **k: Any) -> Any:
        raise KeyError(name)

    monkeypatch.setattr(cli, "get_adapter", _boom)

    code = cli.main(["serve", "--runtime", "ollama", "--model", "qwen"])

    assert code == 1


# ---------------------------------------------------------------- install


def test_install_calls_pull(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    pulled: dict[str, str] = {}

    class _FakeAdapter:
        def pull(self, model: str) -> None:
            pulled["model"] = model

    monkeypatch.setattr(cli, "get_adapter", lambda name, *a, **k: _FakeAdapter())

    code = cli.main(["install", "--runtime", "ollama", "--model", "qwen3:8b"])

    assert code == 0
    assert pulled["model"] == "qwen3:8b"


def test_install_pull_failure_returns_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class _FakeAdapter:
        def pull(self, model: str) -> None:
            raise RuntimeError("registry unreachable")

    monkeypatch.setattr(cli, "get_adapter", lambda name, *a, **k: _FakeAdapter())

    code = cli.main(["install", "--runtime", "ollama", "--model", "qwen3:8b"])

    assert code == 1


# ---------------------------------------------------------------- benchmark


def test_benchmark_prints_result_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    result = BenchmarkResult(
        model_alias="qwen",
        runtime="ollama",
        ttft_ms=120.0,
        tokens_per_second=55.5,
        output_tokens=128,
        input_tokens=12,
        measured_at="2026-06-29T00:00:00Z",
    )
    monkeypatch.setattr(cli, "benchmark_endpoint", lambda *a, **k: result)

    code = cli.main(["benchmark", "--base-url", "http://localhost:11434", "--model", "qwen"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["model_alias"] == "qwen"
    assert payload["tokens_per_second"] == 55.5


def test_benchmark_publish_emits_signed_manifest(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from sip_protocol import KeyPair, verify_provider_manifest

    keypair = KeyPair.generate()
    key_file = tmp_path / "key.json"
    key_file.write_text(
        json.dumps({"public_key": keypair.public_key_str, "private_key": keypair.private_key_str}),
        encoding="utf-8",
    )

    result = BenchmarkResult(
        model_alias="qwen",
        runtime="ollama",
        ttft_ms=120.0,
        tokens_per_second=55.5,
        output_tokens=128,
        measured_at="2026-06-29T00:00:00Z",
    )
    monkeypatch.setattr(cli, "benchmark_endpoint", lambda *a, **k: result)
    monkeypatch.setattr(cli.hardware, "scan", lambda **_: _fake_profile())

    code = cli.main(
        [
            "benchmark",
            "--base-url",
            "http://localhost:11434",
            "--model",
            "qwen",
            "--runtime",
            "ollama",
            "--publish",
            str(key_file),
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "sip-ai.provider_manifest.v1"
    assert payload["provider_pubkey"] == keypair.public_key_str
    assert verify_provider_manifest(payload) is True


# ---------------------------------------------------------------- status / version


def test_status_lists_adapters(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["status"])

    assert code == 0
    out = capsys.readouterr().out
    assert "ollama" in out
    assert "llama.cpp" in out


def test_version_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["version"])

    assert code == 0
    assert cli.__version__ in capsys.readouterr().out


def test_no_command_prints_help_and_returns_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main([])

    assert code != 0
