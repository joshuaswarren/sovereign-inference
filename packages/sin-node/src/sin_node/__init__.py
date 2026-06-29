# SPDX-License-Identifier: AGPL-3.0-or-later
"""sin_node — the Sovereign Inference Node core.

Shared contracts (this module) plus feature modules:
    hardware   — `sin scan` hardware profiler
    catalog    — curated model catalog
    recommend  — model recommendation engine
    benchmark  — node benchmarking + signed capability manifest
    api        — local status API for the dashboard
"""

from __future__ import annotations

from .adapter import (
    AdapterRegistry,
    OpenAICompatibleAdapter,
    RuntimeAdapter,
    ServerHandle,
    available_adapter_names,
    get_adapter,
    register_adapter,
    registry,
)
from .http import StreamStats, chat, stream_chat
from .memory import estimate_memory
from .models import (
    Accelerator,
    BenchmarkResult,
    CatalogModel,
    ChatResult,
    CPUInfo,
    GPUInfo,
    GpuVendor,
    HardwareProfile,
    MemoryEstimate,
    QuantOption,
    Recommendation,
    RuntimeInfo,
)

__version__ = "0.1.2"

__all__ = [
    "Accelerator",
    "AdapterRegistry",
    "BenchmarkResult",
    "CPUInfo",
    "CatalogModel",
    "ChatResult",
    "GPUInfo",
    "GpuVendor",
    "HardwareProfile",
    "MemoryEstimate",
    "OpenAICompatibleAdapter",
    "QuantOption",
    "Recommendation",
    "RuntimeAdapter",
    "RuntimeInfo",
    "ServerHandle",
    "StreamStats",
    "__version__",
    "available_adapter_names",
    "chat",
    "estimate_memory",
    "get_adapter",
    "register_adapter",
    "registry",
    "stream_chat",
]
