# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the model recommendation engine."""

from __future__ import annotations

import pytest

from sin_node.catalog import load_catalog
from sin_node.memory import estimate_memory
from sin_node.models import (
    Accelerator,
    CatalogModel,
    CPUInfo,
    GPUInfo,
    GpuVendor,
    HardwareProfile,
    QuantOption,
)
from sin_node.recommend import predict_tps, recommend


def _big_cuda_profile() -> HardwareProfile:
    """A workstation: 64GB RAM, NVIDIA CUDA, 24GB VRAM."""
    return HardwareProfile(
        os="Linux",
        os_version="6.8",
        arch="x86_64",
        cpu=CPUInfo(arch="x86_64", physical_cores=16, logical_cores=32),
        ram_total_gb=64.0,
        ram_available_gb=56.0,
        disk_free_gb=900.0,
        gpus=[GPUInfo(vendor=GpuVendor.nvidia, name="RTX 4090", vram_total_gb=24.0, vram_free_gb=23.0)],
        accelerator=Accelerator.cuda,
        unified_memory=False,
    )


def _tiny_cpu_profile() -> HardwareProfile:
    """A constrained laptop: 4GB RAM, CPU-only."""
    return HardwareProfile(
        os="Linux",
        os_version="6.8",
        arch="x86_64",
        cpu=CPUInfo(arch="x86_64", physical_cores=2, logical_cores=4),
        ram_total_gb=4.0,
        ram_available_gb=3.2,
        disk_free_gb=20.0,
        gpus=[],
        accelerator=Accelerator.cpu,
        unified_memory=False,
    )


def test_big_profile_returns_at_least_three_fitting_coding_recs() -> None:
    recs = recommend(_big_cuda_profile(), task="coding")
    assert len(recs) >= 3
    # ranked by score descending
    scores = [r.score for r in recs]
    assert scores == sorted(scores, reverse=True)
    # on a 24GB GPU, the top coding rec must actually fit
    assert recs[0].fits is True


def test_every_recommendation_has_a_nonempty_why() -> None:
    recs = recommend(_big_cuda_profile(), task="coding")
    assert recs
    for r in recs:
        assert r.why.strip(), f"{r.model_id} has an empty why"


def test_tiny_profile_prefers_small_models_but_still_returns_three() -> None:
    recs = recommend(_tiny_cpu_profile(), task="general-chat")
    assert len(recs) >= 3
    # The top pick should fit on 4GB and be a small model.
    top = recs[0]
    assert top.fits is True
    assert "0.5b" in top.model_id or "0.5B" in top.display_name
    # fitting recommendations rank ahead of non-fitting ones
    fits_flags = [r.fits for r in recs]
    assert fits_flags == sorted(fits_flags, reverse=True)


def test_tiny_profile_marks_large_models_as_not_fitting() -> None:
    recs = recommend(_tiny_cpu_profile(), task="general-chat", top_k=10)
    not_fitting = [r for r in recs if not r.fits]
    assert not_fitting, "expected at least one model too large for 4GB"
    for r in not_fitting:
        assert r.tradeoffs, f"{r.model_id} does not fit but lists no tradeoffs"
        assert any("memory" in t.lower() or "fit" in t.lower() for t in r.tradeoffs)


def test_prefers_largest_quant_that_fits_but_caps_at_q8() -> None:
    # On a 24GB GPU a 3B model fits even at F16, but quant selection is capped at
    # a near-lossless point (Q8_0): F16 doubles memory and halves speed for no
    # quality gain, so Q8_0 is the sensible top choice, not F16.
    recs = recommend(_big_cuda_profile(), task="general-chat", top_k=10)
    llama = next(r for r in recs if r.model_id == "llama-3.2-3b-instruct")
    assert llama.quant == "Q8_0"
    assert llama.fits is True


def test_top_k_must_be_positive() -> None:
    for bad in (0, -1, -5):
        with pytest.raises(ValueError, match="top_k"):
            recommend(_big_cuda_profile(), task="coding", top_k=bad)


def test_headroom_ratio_stays_below_one_when_just_not_fitting() -> None:
    # A model whose memory need is just barely above usable must report
    # headroom_ratio < 1.0 even though usable/total rounds to 1.0.
    model = CatalogModel(
        model_id="edge-1b",
        display_name="Edge 1B",
        params_b=1.0,
        quants=[QuantOption(name="Q4_K_M", bits=4.5)],
        tasks=["coding"],
        license="apache-2.0",
        recommended_runtimes=["llama.cpp"],
        context_options=[4096],
        default_context=4096,
        n_layers=16,
        hidden_size=2048,
        n_heads=16,
        n_kv_heads=4,
        quality_score=0.5,
    )
    est = estimate_memory(1.0, 4.5, 4096, n_layers=16, hidden_size=2048, n_kv_heads=4, n_heads=16)
    usable = est.total_gb * 0.9997  # just under: does not fit, but ratio rounds to 1.0
    profile = HardwareProfile(
        os="Linux",
        os_version="6",
        arch="x86_64",
        cpu=CPUInfo(arch="x86_64", physical_cores=4, logical_cores=8),
        ram_total_gb=64.0,
        ram_available_gb=8.0,
        disk_free_gb=100.0,
        gpus=[GPUInfo(vendor=GpuVendor.nvidia, name="X", vram_total_gb=usable)],
        accelerator=Accelerator.cuda,
        unified_memory=False,
    )
    rec = recommend(profile, task="coding", catalog=[model])[0]
    assert rec.fits is False
    assert rec.headroom_ratio < 1.0


def test_commercial_required_filters_non_commercial_licenses() -> None:
    non_commercial = CatalogModel(
        model_id="research-only-7b",
        display_name="Research Only 7B",
        params_b=7.0,
        quants=[QuantOption(name="Q4_K_M", bits=4.5)],
        tasks=["coding"],
        license="CC-BY-NC-4.0",
        recommended_runtimes=["llama.cpp"],
        context_options=[4096],
        default_context=4096,
        n_layers=32,
        hidden_size=4096,
        n_heads=32,
        n_kv_heads=8,
        commercial_use=False,
        quality_score=0.9,
    )
    catalog = [*load_catalog(), non_commercial]
    recs = recommend(_big_cuda_profile(), task="coding", commercial_required=True, catalog=catalog, top_k=10)
    assert all(r.model_id != "research-only-7b" for r in recs)
    # without the flag, it is eligible
    recs_all = recommend(_big_cuda_profile(), task="coding", catalog=catalog, top_k=10)
    assert any(r.model_id == "research-only-7b" for r in recs_all)


def test_unknown_task_returns_empty_list() -> None:
    recs = recommend(_big_cuda_profile(), task="does-not-exist")
    assert recs == []


def test_top_k_limits_results() -> None:
    recs = recommend(_big_cuda_profile(), task="general-chat", top_k=2)
    assert len(recs) == 2


def test_embeddings_task_returns_embedding_model() -> None:
    recs = recommend(_big_cuda_profile(), task="embeddings", top_k=5)
    assert recs
    assert any(r.model_id == "nomic-embed-text-v1.5" for r in recs)


def test_headroom_ratio_and_estimate_are_consistent() -> None:
    recs = recommend(_big_cuda_profile(), task="coding")
    for r in recs:
        assert r.estimate.total_gb > 0
        # headroom = usable / total ; >= 1.0 exactly when it fits
        if r.fits:
            assert r.headroom_ratio >= 1.0
        else:
            assert r.headroom_ratio < 1.0


def test_latency_low_prefers_faster_smaller_models() -> None:
    balanced = recommend(_big_cuda_profile(), task="general-chat", latency="balanced", top_k=10)
    low = recommend(_big_cuda_profile(), task="general-chat", latency="low", top_k=10)

    # The small/fast model should rank no worse under low-latency preference.
    def rank_of(recs: list, model_id: str) -> int:
        return next(i for i, r in enumerate(recs) if r.model_id == model_id)

    small_id = "qwen2.5-0.5b-instruct"
    assert rank_of(low, small_id) <= rank_of(balanced, small_id)


def test_predict_tps_orders_by_accelerator_and_size() -> None:
    # GPU should beat CPU for the same model/quant.
    gpu_tps = predict_tps(7.0, Accelerator.cuda, 4.5)
    cpu_tps = predict_tps(7.0, Accelerator.cpu, 4.5)
    assert gpu_tps > cpu_tps > 0
    # Smaller models should be faster than larger ones on the same accelerator.
    small = predict_tps(0.5, Accelerator.cuda, 4.5)
    large = predict_tps(7.0, Accelerator.cuda, 4.5)
    assert small > large


def test_predict_tps_degrades_gracefully_on_bad_input() -> None:
    # Zero/negative params must not raise or divide by zero.
    assert predict_tps(0.0, Accelerator.cpu, 4.5) >= 0.0
