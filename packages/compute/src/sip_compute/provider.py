# SPDX-License-Identifier: Apache-2.0
"""The compute-provider contract and a small factory registry.

A :class:`ComputeProvider` is the narrow interface every external-compute
adapter (Nosana, Akash) implements: take an :class:`InferenceSpec`, provision a
workload, report its status, expose its endpoint, and tear it down. The registry
mirrors :func:`sin_node.adapter.register_adapter` so callers can resolve a
provider by name without importing the adapter package directly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from .errors import ComputeError
from .spec import Deployment, InferenceSpec


@runtime_checkable
class ComputeProvider(Protocol):
    """Provision and manage an inference workload on an external network."""

    name: str

    def deploy(self, spec: InferenceSpec) -> Deployment:
        """Provision ``spec`` and return a handle (possibly not yet ready)."""
        ...

    def status(self, deployment: Deployment) -> Deployment:
        """Return a refreshed handle with the current status and endpoint."""
        ...

    def await_ready(self, deployment: Deployment) -> Deployment:
        """Block until the deployment is ready (or terminal) and return it."""
        ...

    def teardown(self, deployment: Deployment) -> None:
        """Release the deployment's resources."""
        ...


ProviderFactory = Callable[..., ComputeProvider]

_REGISTRY: dict[str, ProviderFactory] = {}


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Register a compute-provider factory under ``name`` (idempotent overwrite)."""
    _REGISTRY[name] = factory


def get_provider_factory(name: str) -> ProviderFactory:
    """Return the factory registered under ``name`` or raise :class:`ComputeError`."""
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise ComputeError(f"unknown compute provider {name!r}; registered: {known}") from None


def available_providers() -> list[str]:
    """Return the sorted names of all registered compute providers."""
    return sorted(_REGISTRY)


def build_provider(name: str, **kwargs: Any) -> ComputeProvider:
    """Resolve ``name`` and instantiate its provider with ``kwargs``."""
    return get_provider_factory(name)(**kwargs)
