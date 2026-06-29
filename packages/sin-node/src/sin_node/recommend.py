# SPDX-License-Identifier: AGPL-3.0-or-later
"""Transparent model recommendation engine.

Given a hardware profile and a task, rank model/runtime/quantization choices by
a weighted blend of memory fit, reference quality, and predicted speed. Every
recommendation explains *why* it was chosen and what tradeoffs it carries, per
the SIN goal that recommendations be explainable (docs/prd/sin.md, Section 7.7
"Model recommendation engine").

The engine is pure and deterministic: it reads the bundled catalog and the
memory estimator, with no network or subprocess calls.
"""

from __future__ import annotations

from .catalog import load_catalog
from .memory import estimate_memory
from .models import (
    Accelerator,
    CatalogModel,
    HardwareProfile,
    MemoryEstimate,
    QuantOption,
    Recommendation,
)

# Licenses whose SPDX id (or common shorthand) signals a non-commercial grant.
# Used as a secondary guard alongside the catalog's ``commercial_use`` flag.
_NON_COMMERCIAL_MARKERS = ("-nc", "noncommercial", "non-commercial", "cc-by-nc")

# Latency presets map to how much the score weights predicted throughput.
_LATENCY_SPEED_WEIGHT = {
    "low": 0.45,
    "balanced": 0.25,
    "quality": 0.10,
}

# Rough single-stream throughput ceilings (tokens/sec) per accelerator for a
# ~1B-parameter Q4 model. Real numbers come from the local benchmark later;
# these only need to order candidates sensibly.
_ACCEL_BASE_TPS = {
    Accelerator.cuda: 220.0,
    Accelerator.rocm: 170.0,
    Accelerator.metal: 130.0,
    Accelerator.vulkan: 90.0,
    Accelerator.cpu: 28.0,
}


def predict_tps(params_b: float, accelerator: Accelerator, quant_bits: float) -> float:
    """Heuristic single-stream tokens/sec for a model on an accelerator.

    Throughput scales roughly inversely with the number of parameters and with
    quantization width (more bits per weight means more memory traffic). This is
    a transparent ordering heuristic, not a calibrated prediction. Degrades to
    ``0.0`` on non-positive parameter counts rather than raising.
    """
    if params_b <= 0.0:
        return 0.0
    base = _ACCEL_BASE_TPS.get(accelerator, _ACCEL_BASE_TPS[Accelerator.cpu])
    # Normalize against a 1B-param Q4 (4.5-bit) baseline.
    size_factor = 1.0 / params_b
    quant_factor = 4.5 / max(quant_bits, 1.0)
    return round(base * size_factor * quant_factor, 1)


def _is_non_commercial(model: CatalogModel) -> bool:
    if not model.commercial_use:
        return True
    license_id = model.license.lower()
    return any(marker in license_id for marker in _NON_COMMERCIAL_MARKERS)


def _estimate_for(model: CatalogModel, quant: QuantOption, context: int) -> MemoryEstimate:
    return estimate_memory(
        model.params_b,
        quant.bits,
        context,
        n_layers=model.n_layers,
        hidden_size=model.hidden_size,
        n_kv_heads=model.n_kv_heads,
        n_heads=model.n_heads,
    )


def _select_quant(model: CatalogModel, usable_gb: float, context: int) -> tuple[QuantOption, MemoryEstimate, bool]:
    """Pick the largest quant that fits; else the smallest quant (marked unfit).

    Returns ``(quant, estimate, fits)``. "Largest" and "smallest" are by
    effective bits per weight, since more bits means higher quality but more
    memory.
    """
    by_bits = sorted(model.quants, key=lambda q: q.bits)
    best_fit: tuple[QuantOption, MemoryEstimate] | None = None
    for quant in by_bits:  # ascending bits
        estimate = _estimate_for(model, quant, context)
        if estimate.total_gb <= usable_gb:
            best_fit = (quant, estimate)  # keep climbing for the largest fit
    if best_fit is not None:
        return best_fit[0], best_fit[1], True
    smallest = by_bits[0]
    return smallest, _estimate_for(model, smallest, context), False


def _score(
    *,
    fits: bool,
    headroom_ratio: float,
    quality_score: float,
    predicted_tps: float,
    speed_weight: float,
) -> float:
    """Weighted blend of fit, quality, and speed in [0, 1]-ish range.

    Fitting models are always ranked ahead of non-fitting ones via a large
    constant offset, so a brilliant model that cannot load never outranks a
    workable one.
    """
    fit_component = min(headroom_ratio / 2.0, 1.0)  # saturates once we have 2x headroom
    speed_component = min(predicted_tps / 200.0, 1.0)
    quality_weight = max(0.0, 0.75 - speed_weight)
    fit_weight = 1.0 - speed_weight - quality_weight
    blended = fit_weight * fit_component + quality_weight * quality_score + speed_weight * speed_component
    return round((1.0 if fits else 0.0) + blended, 4)


def _build_why(model: CatalogModel, quant: QuantOption, context: int, fits: bool, usable_gb: float) -> str:
    if fits:
        return (
            f"{model.display_name} at {quant.name} fits in {usable_gb:.1f} GB usable memory "
            f"with a {context} token context; strong {'/'.join(model.tasks)} quality "
            f"(score {model.quality_score:.2f})."
        )
    return (
        f"{model.display_name} is a strong {'/'.join(model.tasks)} option but its smallest quant "
        f"({quant.name}) does not fit in {usable_gb:.1f} GB at {context} tokens."
    )


def _build_tradeoffs(
    model: CatalogModel, quant: QuantOption, estimate: MemoryEstimate, fits: bool, usable_gb: float
) -> list[str]:
    tradeoffs: list[str] = []
    if not fits:
        tradeoffs.append(
            f"Does not fit: needs ~{estimate.total_gb:.1f} GB but only {usable_gb:.1f} GB is usable "
            f"(reduce context, pick a smaller model, or add memory)."
        )
    if quant.bits <= 4.5:
        tradeoffs.append(f"{quant.name} is aggressively quantized; expect some quality loss versus higher-bit quants.")
    if model.params_b >= 7.0:
        tradeoffs.append("Larger model: higher quality but slower tokens/sec and more memory.")
    if _is_non_commercial(model):
        tradeoffs.append("License restricts commercial use; verify terms before deploying.")
    return tradeoffs


def recommend(
    profile: HardwareProfile,
    task: str,
    *,
    commercial_required: bool = False,
    latency: str = "balanced",
    top_k: int = 3,
    catalog: list[CatalogModel] | None = None,
) -> list[Recommendation]:
    """Rank model recommendations for ``task`` on ``profile``.

    Filters by task (and license when ``commercial_required``), picks the
    largest quant that fits per model at its default context, estimates memory,
    predicts throughput, and scores a weighted blend. Returns up to ``top_k``
    recommendations ranked by score, fitting models first. Returns ``[]`` when
    no catalog model serves the task.
    """
    models = catalog if catalog is not None else load_catalog()
    speed_weight = _LATENCY_SPEED_WEIGHT.get(latency, _LATENCY_SPEED_WEIGHT["balanced"])
    usable_gb = profile.usable_memory_gb()

    candidates = [m for m in models if task in m.tasks]
    if commercial_required:
        candidates = [m for m in candidates if not _is_non_commercial(m)]
    if not candidates:
        return []

    recommendations: list[Recommendation] = []
    for model in candidates:
        context = model.default_context
        quant, estimate, fits = _select_quant(model, usable_gb, context)
        headroom_ratio = round(usable_gb / estimate.total_gb, 3) if estimate.total_gb > 0 else 0.0
        runtime = model.recommended_runtimes[0] if model.recommended_runtimes else "llama.cpp"
        predicted_tps = predict_tps(model.params_b, profile.accelerator, quant.bits)
        score = _score(
            fits=fits,
            headroom_ratio=headroom_ratio,
            quality_score=model.quality_score,
            predicted_tps=predicted_tps,
            speed_weight=speed_weight,
        )
        recommendations.append(
            Recommendation(
                model_id=model.model_id,
                display_name=model.display_name,
                runtime=runtime,
                quant=quant.name,
                context=context,
                estimate=estimate,
                fits=fits,
                headroom_ratio=headroom_ratio,
                predicted_tps=predicted_tps,
                quality_score=model.quality_score,
                score=score,
                why=_build_why(model, quant, context, fits, usable_gb),
                tradeoffs=_build_tradeoffs(model, quant, estimate, fits, usable_gb),
            )
        )

    recommendations.sort(key=lambda r: (r.fits, r.score), reverse=True)
    return recommendations[:top_k]
