# SPDX-License-Identifier: AGPL-3.0-or-later
"""Transparent model memory estimation.

Estimates how much memory a model needs = quantized weights + KV cache +
runtime overhead. The weight rule (params x bits / 8) and a KV-cache formula
give a defensible first estimate; local benchmarks refine it later. See
docs/prd/sin.md (Section 7.7) and references [S32]-[S34].
"""

from __future__ import annotations

from .models import MemoryEstimate


def estimate_memory(
    params_b: float,
    quant_bits: float,
    context: int,
    *,
    n_layers: int | None = None,
    hidden_size: int | None = None,
    n_kv_heads: int | None = None,
    n_heads: int | None = None,
    kv_dtype_bytes: int = 2,
    overhead_gb: float = 0.7,
) -> MemoryEstimate:
    """Estimate total memory (GB) to serve a model at a given context length.

    - ``weights_gb = params_b * quant_bits / 8`` (billions of params, bits/param).
    - KV cache: with ``n_layers`` and ``hidden_size``, use
      ``2 * n_layers * hidden_size * gqa * context * kv_dtype_bytes`` where the
      GQA factor is ``n_kv_heads / n_heads`` when both are known (else 1.0).
      Without architecture details, fall back to a rough proportional heuristic.
    """
    weights_gb = params_b * quant_bits / 8.0

    if n_layers and hidden_size:
        gqa = (n_kv_heads / n_heads) if (n_kv_heads and n_heads) else 1.0
        kv_cache_gb = 2 * n_layers * hidden_size * gqa * context * kv_dtype_bytes / 1e9
    else:
        kv_cache_gb = params_b * (context / 4096) * 0.25

    total_gb = weights_gb + kv_cache_gb + overhead_gb
    return MemoryEstimate(
        weights_gb=weights_gb,
        kv_cache_gb=kv_cache_gb,
        overhead_gb=overhead_gb,
        total_gb=total_gb,
    )
