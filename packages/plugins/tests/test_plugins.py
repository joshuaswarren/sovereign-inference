# SPDX-License-Identifier: Apache-2.0
"""Tests for the plugin discovery + registration SDK."""

from __future__ import annotations

from typing import Any

from sip_plugins import (
    COMPUTE_GROUP,
    RUNTIME_GROUP,
    discover,
    load_all,
    load_compute_providers,
    load_runtime_adapters,
)


class _FakeEntryPoint:
    """Mimics importlib.metadata.EntryPoint: a name and a load()."""

    def __init__(self, name: str, obj: Any, *, broken: bool = False) -> None:
        self.name = name
        self._obj = obj
        self._broken = broken

    def load(self) -> Any:
        if self._broken:
            raise ImportError("plugin failed to import")
        return self._obj


# -- discover -------------------------------------------------------------------


def test_discover_loads_each_entry_point() -> None:
    eps = [_FakeEntryPoint("a", "obj-a"), _FakeEntryPoint("b", "obj-b")]
    plugins = discover(RUNTIME_GROUP, entry_points=eps)
    assert [(p.name, p.obj) for p in plugins] == [("a", "obj-a"), ("b", "obj-b")]
    assert all(p.group == RUNTIME_GROUP for p in plugins)


def test_discover_skips_a_broken_plugin() -> None:
    eps = [_FakeEntryPoint("bad", None, broken=True), _FakeEntryPoint("good", "ok")]
    plugins = discover(RUNTIME_GROUP, entry_points=eps)
    assert [p.name for p in plugins] == ["good"]  # one bad plugin can't break the host


def test_discover_no_plugins_returns_empty() -> None:
    assert discover("sip_ai.nonexistent_group_xyz") == []


# -- load_runtime_adapters ------------------------------------------------------


def test_load_runtime_adapters_registers_each() -> None:
    registered: dict[str, Any] = {}
    eps = [_FakeEntryPoint("r1", "factory1"), _FakeEntryPoint("r2", "factory2")]
    names = load_runtime_adapters(entry_points=eps, register=lambda n, f: registered.__setitem__(n, f))
    assert names == ["r1", "r2"]
    assert registered == {"r1": "factory1", "r2": "factory2"}


# -- load_compute_providers -----------------------------------------------------


def test_load_compute_providers_registers_each() -> None:
    registered: dict[str, Any] = {}
    eps = [_FakeEntryPoint("c1", "prov1")]
    names = load_compute_providers(entry_points=eps, register=lambda n, f: registered.__setitem__(n, f))
    assert names == ["c1"]
    assert registered == {"c1": "prov1"}
    assert COMPUTE_GROUP  # the group constant is exported


# -- load_all -------------------------------------------------------------------


def test_load_all_returns_groups_and_is_safe_with_no_plugins() -> None:
    result = load_all()
    assert set(result) == {"runtime_adapters", "compute_providers"}
    assert result["runtime_adapters"] == []  # nothing installed in the test env
    assert result["compute_providers"] == []
