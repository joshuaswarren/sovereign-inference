# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest

from sin_node.memory import estimate_memory


def test_weights_are_params_times_bits_over_eight() -> None:
    est = estimate_memory(params_b=7.0, quant_bits=4.5, context=4096, overhead_gb=0.0)
    assert est.weights_gb == pytest.approx(3.9375, rel=1e-6)


def test_kv_cache_with_layers_and_hidden_no_gqa() -> None:
    est = estimate_memory(params_b=7.0, quant_bits=4.5, context=8192, n_layers=32, hidden_size=4096, overhead_gb=0.0)
    expected_kv = 2 * 32 * 4096 * 8192 * 2 / 1e9
    assert est.kv_cache_gb == pytest.approx(expected_kv, rel=1e-6)
    assert est.total_gb == pytest.approx(est.weights_gb + expected_kv, rel=1e-6)


def test_gqa_reduces_kv_cache_proportionally() -> None:
    full = estimate_memory(params_b=7.0, quant_bits=4.5, context=8192, n_layers=32, hidden_size=4096)
    gqa = estimate_memory(
        params_b=7.0,
        quant_bits=4.5,
        context=8192,
        n_layers=32,
        hidden_size=4096,
        n_kv_heads=4,
        n_heads=32,
    )
    assert gqa.kv_cache_gb == pytest.approx(full.kv_cache_gb * (4 / 32), rel=1e-6)


def test_fallback_kv_estimate_when_no_architecture() -> None:
    est = estimate_memory(params_b=7.0, quant_bits=4.5, context=8192, overhead_gb=0.0)
    # fallback heuristic: params_b * (context / 4096) * 0.25 = 7 * 2 * 0.25
    assert est.kv_cache_gb == pytest.approx(3.5, rel=1e-6)


def test_total_includes_overhead() -> None:
    est = estimate_memory(params_b=1.0, quant_bits=8.0, context=2048, n_layers=1, hidden_size=1, overhead_gb=0.7)
    assert est.total_gb == pytest.approx(est.weights_gb + est.kv_cache_gb + 0.7, rel=1e-6)


def test_larger_context_increases_total() -> None:
    small = estimate_memory(params_b=7.0, quant_bits=4.5, context=2048, n_layers=32, hidden_size=4096)
    large = estimate_memory(params_b=7.0, quant_bits=4.5, context=16384, n_layers=32, hidden_size=4096)
    assert large.total_gb > small.total_gb
