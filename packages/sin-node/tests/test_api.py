# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the local status API (FastAPI).

The API is dependency-injected: ``create_app`` accepts ``scan``, ``recommend``,
and ``catalog`` callables so tests pass deterministic fakes and never touch the
real machine, network, or bundled catalog. We assert each endpoint's status code
and JSON shape against the frozen ``sin_node.models`` contracts.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from sin_node import __version__
from sin_node.adapter import available_adapter_names
from sin_node.models import (
    Accelerator,
    CatalogModel,
    CPUInfo,
    GPUInfo,
    GpuVendor,
    HardwareProfile,
    MemoryEstimate,
    QuantOption,
    Recommendation,
)


def _fake_profile() -> HardwareProfile:
    return HardwareProfile(
        os="Darwin",
        os_version="15.0",
        arch="arm64",
        cpu=CPUInfo(arch="arm64", model="Apple M3", physical_cores=8, logical_cores=8),
        ram_total_gb=16.0,
        ram_available_gb=10.0,
        disk_free_gb=200.0,
        gpus=[GPUInfo(vendor=GpuVendor.apple, name="Apple M3 GPU")],
        accelerator=Accelerator.metal,
        unified_memory=True,
    )


def _fake_catalog_model() -> CatalogModel:
    return CatalogModel(
        model_id="qwen2.5-0.5b-instruct",
        display_name="Qwen2.5 0.5B Instruct",
        params_b=0.5,
        quants=[QuantOption(name="Q4_K_M", bits=4.5)],
        tasks=["general-chat", "coding"],
        license="Apache-2.0",
        recommended_runtimes=["llama.cpp"],
        context_options=[4096],
        default_context=4096,
    )


def _fake_recommendation() -> Recommendation:
    return Recommendation(
        model_id="qwen2.5-0.5b-instruct",
        display_name="Qwen2.5 0.5B Instruct",
        runtime="llama.cpp",
        quant="Q4_K_M",
        context=4096,
        estimate=MemoryEstimate(weights_gb=0.3, kv_cache_gb=0.1, overhead_gb=0.7, total_gb=1.1),
        fits=True,
        headroom_ratio=10.18,
        predicted_tps=180.0,
        quality_score=0.6,
        score=1.5,
        why="fits comfortably",
        tradeoffs=["aggressively quantized"],
    )


def _client(**overrides: object) -> TestClient:
    """Build a TestClient over an app wired with deterministic fakes.

    Records calls so tests can assert the recommend endpoint forwards its query
    params (task/commercial/top) into the injected ``recommend`` callable.
    """
    from sin_node.api import create_app

    calls: dict[str, object] = {}

    def fake_scan() -> HardwareProfile:
        calls["scan"] = True
        return _fake_profile()

    def fake_recommend(
        profile: HardwareProfile,
        task: str,
        *,
        commercial_required: bool = False,
        top_k: int = 3,
        **_: object,
    ) -> list[Recommendation]:
        calls["recommend"] = {
            "task": task,
            "commercial_required": commercial_required,
            "top_k": top_k,
            "profile_arch": profile.arch,
        }
        return [_fake_recommendation()]

    def fake_catalog() -> list[CatalogModel]:
        calls["catalog"] = True
        return [_fake_catalog_model()]

    kwargs: dict[str, object] = {
        "scan": fake_scan,
        "recommend": fake_recommend,
        "catalog": fake_catalog,
    }
    kwargs.update(overrides)
    app = create_app(**kwargs)  # type: ignore[arg-type]
    client = TestClient(app)
    client.calls = calls  # type: ignore[attr-defined]
    return client


def test_health_returns_ok_and_version() -> None:
    resp = _client().get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_status_returns_version_and_adapter_names() -> None:
    resp = _client().get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == __version__
    assert body["adapters"] == available_adapter_names()
    assert isinstance(body["adapters"], list)


def test_scan_returns_hardware_profile_json() -> None:
    client = _client()
    resp = client.get("/api/scan")
    assert resp.status_code == 200
    body = resp.json()
    # Matches the injected fake profile and the HardwareProfile contract.
    assert body == _fake_profile().model_dump(mode="json")
    assert body["accelerator"] == "metal"
    assert body["unified_memory"] is True
    assert client.calls["scan"] is True  # type: ignore[attr-defined]


def test_catalog_returns_list_of_catalog_models() -> None:
    resp = _client().get("/api/catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body == [_fake_catalog_model().model_dump(mode="json")]
    assert body[0]["model_id"] == "qwen2.5-0.5b-instruct"


def test_recommend_returns_list_of_recommendations() -> None:
    resp = _client().get("/api/recommend?task=coding")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body
    first = body[0]
    assert first["model_id"] == "qwen2.5-0.5b-instruct"
    # Nested MemoryEstimate is serialized too.
    assert first["estimate"]["total_gb"] == 1.1


def test_recommend_forwards_query_params_to_recommend_callable() -> None:
    client = _client()
    resp = client.get("/api/recommend?task=coding&commercial=true&top=5")
    assert resp.status_code == 200
    recorded = client.calls["recommend"]  # type: ignore[attr-defined]
    assert recorded == {
        "task": "coding",
        "commercial_required": True,
        "top_k": 5,
        "profile_arch": "arm64",
    }


def test_recommend_defaults_when_only_task_given() -> None:
    client = _client()
    client.get("/api/recommend?task=general-chat")
    recorded = client.calls["recommend"]  # type: ignore[attr-defined]
    assert recorded == {
        "task": "general-chat",
        "commercial_required": False,
        "top_k": 3,
        "profile_arch": "arm64",
    }


def test_recommend_requires_task_param() -> None:
    # task is a required query param; omitting it is a 422 validation error.
    resp = _client().get("/api/recommend")
    assert resp.status_code == 422


def test_cors_headers_present_for_localhost_origin() -> None:
    resp = _client().get(
        "/api/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] in {"http://localhost:5173", "*"}


def test_create_app_uses_real_defaults_when_no_fakes_passed() -> None:
    # Smoke test the real wiring: with no injected callables, /api/health and
    # /api/status must still work (they do not touch hardware).
    from sin_node.api import create_app

    client = TestClient(create_app())
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/status").status_code == 200
