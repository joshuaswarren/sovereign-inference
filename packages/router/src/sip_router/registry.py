# SPDX-License-Identifier: AGPL-3.0-or-later
"""In-memory provider registry with JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ProviderEntry


class ProviderRegistry:
    """A collection of known providers, queryable by supported model.

    The registry preserves insertion order so deterministic scoring ties resolve
    predictably. Persistence is a plain JSON list of ``{base_url, manifest}``.
    """

    def __init__(self, entries: list[ProviderEntry] | None = None) -> None:
        self._entries: list[ProviderEntry] = list(entries) if entries else []

    def add(self, entry: ProviderEntry) -> None:
        """Register a provider entry."""
        self._entries.append(entry)

    def all(self) -> list[ProviderEntry]:
        """Return every registered entry, in insertion order."""
        return list(self._entries)

    def for_model(self, model_id: str) -> list[ProviderEntry]:
        """Return entries whose manifest advertises ``model_id``."""
        return [entry for entry in self._entries if model_id in entry.manifest.get("models", [])]

    def save(self, path: str | Path) -> None:
        """Write the registry to ``path`` as a JSON list of ``{base_url, manifest}``."""
        payload = [{"base_url": e.base_url, "manifest": e.manifest} for e in self._entries]
        Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> ProviderRegistry:
        """Load a registry from ``path``.

        Degrades gracefully: a missing, unreadable, or malformed file yields an
        empty registry rather than raising.
        """
        file_path = Path(path)
        try:
            raw = file_path.read_text(encoding="utf-8")
        except OSError:
            return cls()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return cls()
        if not isinstance(data, list):
            return cls()
        entries: list[ProviderEntry] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            base_url = item.get("base_url")
            manifest = item.get("manifest")
            if isinstance(base_url, str) and isinstance(manifest, dict):
                entries.append(ProviderEntry(base_url=base_url, manifest=manifest))
        return cls(entries)
