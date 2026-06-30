# SPDX-License-Identifier: Apache-2.0
"""Discover and register Sovereign Inference extensions via Python entry points.

Third-party packages extend the system by declaring entry points in the SIP-AI
groups (``sip_ai.runtime_adapters``, ``sip_ai.compute_providers``,
``sip_ai.directories``). :func:`discover` loads them (skipping any that fail to
import — one bad plugin must not break the host), and the ``load_*`` helpers
register them with the corresponding registry. The entry-point source and the
registrar are injectable, so the loader is unit-testable without installing
packages.
"""

from __future__ import annotations

import importlib.metadata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol

RUNTIME_GROUP = "sip_ai.runtime_adapters"
COMPUTE_GROUP = "sip_ai.compute_providers"
DIRECTORY_GROUP = "sip_ai.directories"

Registrar = Callable[[str, Any], None]


class _EntryPoint(Protocol):
    name: str

    def load(self) -> Any: ...


@dataclass(frozen=True, slots=True)
class Plugin:
    """A successfully-loaded plugin: its entry-point name, group, and object."""

    name: str
    group: str
    obj: Any


def discover(group: str, *, entry_points: Iterable[Any] | None = None) -> list[Plugin]:
    """Load every entry point in ``group`` (skipping ones that fail to import)."""
    eps = entry_points if entry_points is not None else importlib.metadata.entry_points(group=group)
    plugins: list[Plugin] = []
    for ep in eps:
        try:
            obj = ep.load()
        except Exception:  # a broken plugin must not take down the host
            continue
        plugins.append(Plugin(name=ep.name, group=group, obj=obj))
    return plugins


def _default_runtime_registrar(name: str, factory: Any) -> None:
    from sin_node.adapter import register_adapter

    register_adapter(name, factory)


def _default_compute_registrar(name: str, factory: Any) -> None:
    from sip_compute import register_provider

    register_provider(name, factory)


def _load(group: str, registrar: Registrar, entry_points: Iterable[Any] | None) -> list[str]:
    names: list[str] = []
    for plugin in discover(group, entry_points=entry_points):
        registrar(plugin.name, plugin.obj)
        names.append(plugin.name)
    return names


def load_runtime_adapters(*, entry_points: Iterable[Any] | None = None, register: Registrar | None = None) -> list[str]:
    """Register all installed runtime-adapter plugins; return their names."""
    return _load(RUNTIME_GROUP, register or _default_runtime_registrar, entry_points)


def load_compute_providers(
    *, entry_points: Iterable[Any] | None = None, register: Registrar | None = None
) -> list[str]:
    """Register all installed compute-provider plugins; return their names."""
    return _load(COMPUTE_GROUP, register or _default_compute_registrar, entry_points)


def load_all() -> dict[str, list[str]]:
    """Register every installed runtime-adapter and compute-provider plugin."""
    return {
        "runtime_adapters": load_runtime_adapters(),
        "compute_providers": load_compute_providers(),
    }
