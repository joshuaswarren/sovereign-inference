# SPDX-License-Identifier: Apache-2.0
"""sip-compute — shared contract for external decentralized compute providers.

Provides the provider-agnostic :class:`InferenceSpec`/:class:`Deployment` types,
the :class:`ComputeProvider` protocol and its registry, and
:func:`provider_manifest_for`, which turns a provisioned endpoint into a signed
SIP-AI provider manifest. Concrete adapters (Nosana, Akash) live in their own
packages and register themselves here.
"""

from __future__ import annotations

from .errors import ComputeError
from .manifest import provider_manifest_for
from .provider import (
    ComputeProvider,
    ProviderFactory,
    available_providers,
    build_provider,
    get_provider_factory,
    register_provider,
)
from .spec import Deployment, DeploymentStatus, InferenceSpec

__version__ = "0.1.2"

__all__ = [
    "ComputeError",
    "ComputeProvider",
    "Deployment",
    "DeploymentStatus",
    "InferenceSpec",
    "ProviderFactory",
    "available_providers",
    "build_provider",
    "get_provider_factory",
    "provider_manifest_for",
    "register_provider",
]
