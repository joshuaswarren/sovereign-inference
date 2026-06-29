# SPDX-License-Identifier: AGPL-3.0-or-later
"""Curated, bundled model catalog.

The catalog is a small set of real open-weight models spanning chat, coding,
embeddings, and small/fast use. It ships as a JSON data file inside the package
so the advisor works offline with no network access. See docs/prd/sin.md
("Model catalog: 5 curated models across chat, coding, embeddings, and
small/fast use").
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files

from .models import CatalogModel

_DATA_RESOURCE = "data/catalog.json"


def _read_catalog_json() -> list[dict[str, object]]:
    """Read and parse the bundled catalog JSON via importlib.resources."""
    raw = files("sin_node").joinpath(_DATA_RESOURCE).read_text(encoding="utf-8")
    payload = json.loads(raw)
    models = payload.get("models", [])
    if not isinstance(models, list):
        raise ValueError("catalog.json 'models' must be a list")
    return models


@lru_cache(maxsize=1)
def _load_cached() -> tuple[CatalogModel, ...]:
    return tuple(CatalogModel.model_validate(entry) for entry in _read_catalog_json())


def load_catalog() -> list[CatalogModel]:
    """Return the bundled catalog as validated :class:`CatalogModel` objects.

    The result is cached after the first read; a fresh list is returned on each
    call so callers may freely sort or filter without mutating shared state.
    """
    return list(_load_cached())
