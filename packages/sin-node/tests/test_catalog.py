# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the bundled model catalog."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sin_node.catalog import load_catalog
from sin_node.models import CatalogModel
from sip_protocol import validate_model_manifest

# Curated GGUF manifests this component ships alongside the catalog.
_MANIFEST_DIR = Path(__file__).resolve().parents[3] / "registry" / "model-manifests"
_NEW_MANIFESTS = [
    "llama-3.2-3b-instruct-gguf-q4_k_m.json",
    "qwen2.5-0.5b-instruct-gguf-q4_k_m.json",
    "nomic-embed-text-v1.5-gguf-q8_0.json",
    "phi-3.5-mini-instruct-gguf-q4_k_m.json",
]

# Tasks recognized by the model manifest schema; the catalog should stay within
# this vocabulary so recommendations map cleanly onto published manifests.
_VALID_TASKS = {
    "coding",
    "general-chat",
    "rag",
    "embeddings",
    "vision",
    "long-context",
    "reasoning",
}


def test_load_catalog_returns_at_least_five_models() -> None:
    catalog = load_catalog()
    assert isinstance(catalog, list)
    assert len(catalog) >= 5
    assert all(isinstance(m, CatalogModel) for m in catalog)


def test_catalog_model_ids_are_unique() -> None:
    catalog = load_catalog()
    ids = [m.model_id for m in catalog]
    assert len(ids) == len(set(ids))


def test_every_model_has_required_fields_populated() -> None:
    catalog = load_catalog()
    for m in catalog:
        assert m.model_id
        assert m.display_name
        assert m.params_b > 0
        assert m.quants, f"{m.model_id} has no quant options"
        assert m.tasks, f"{m.model_id} has no tasks"
        assert m.license, f"{m.model_id} has no license"
        assert m.recommended_runtimes, f"{m.model_id} has no runtimes"
        assert m.context_options, f"{m.model_id} has no context options"
        assert m.default_context in m.context_options


def test_every_model_uses_known_task_vocabulary() -> None:
    catalog = load_catalog()
    for m in catalog:
        for task in m.tasks:
            assert task in _VALID_TASKS, f"{m.model_id} has unknown task {task!r}"


def test_quality_scores_are_normalized() -> None:
    catalog = load_catalog()
    for m in catalog:
        assert 0.0 <= m.quality_score <= 1.0, f"{m.model_id} quality_score out of range"


def test_architecture_fields_present_for_kv_estimation() -> None:
    # Every non-embedding model should carry the architecture fields the memory
    # estimator uses so KV-cache estimates are not pure heuristic guesses.
    catalog = load_catalog()
    for m in catalog:
        if "embeddings" in m.tasks and len(m.tasks) == 1:
            continue
        assert m.n_layers and m.n_layers > 0, f"{m.model_id} missing n_layers"
        assert m.hidden_size and m.hidden_size > 0, f"{m.model_id} missing hidden_size"
        assert m.n_heads and m.n_heads > 0, f"{m.model_id} missing n_heads"


def test_catalog_spans_chat_coding_embeddings_and_small_fast() -> None:
    catalog = load_catalog()
    tasks_present = {t for m in catalog for t in m.tasks}
    assert "coding" in tasks_present
    assert "general-chat" in tasks_present
    assert "embeddings" in tasks_present
    # at least one genuinely small/fast model (<= 1B params)
    assert any(m.params_b <= 1.0 for m in catalog)


def test_quants_have_plausible_effective_bits() -> None:
    catalog = load_catalog()
    for m in catalog:
        for q in m.quants:
            assert 2.0 <= q.bits <= 16.0, f"{m.model_id}/{q.name} bits implausible"


def test_load_catalog_is_repeatable() -> None:
    first = load_catalog()
    second = load_catalog()
    assert [m.model_id for m in first] == [m.model_id for m in second]


@pytest.mark.parametrize("manifest_name", _NEW_MANIFESTS)
def test_new_model_manifests_validate(manifest_name: str) -> None:
    path = _MANIFEST_DIR / manifest_name
    assert path.exists(), f"missing manifest {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    # Raises on any schema violation; passing means the manifest is well-formed.
    validate_model_manifest(data)
