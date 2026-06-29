# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared data models for the Sovereign Inference Node.

These are the fixed contracts every Phase 1 component builds on: the hardware
profile, the model catalog/recommendation shapes, chat results, and benchmark
results. Pure data with a little derived logic on ``HardwareProfile``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class GpuVendor(StrEnum):
    nvidia = "nvidia"
    amd = "amd"
    apple = "apple"
    intel = "intel"
    unknown = "unknown"


class Accelerator(StrEnum):
    cuda = "cuda"
    rocm = "rocm"
    metal = "metal"
    vulkan = "vulkan"
    cpu = "cpu"


class CPUInfo(BaseModel):
    arch: str
    model: str | None = None
    physical_cores: int | None = None
    logical_cores: int | None = None
    features: list[str] = Field(default_factory=list)


class GPUInfo(BaseModel):
    vendor: GpuVendor
    name: str
    vram_total_gb: float | None = None
    vram_free_gb: float | None = None
    driver: str | None = None


class RuntimeInfo(BaseModel):
    name: str
    available: bool = False
    version: str | None = None
    endpoint: str | None = None


class HardwareProfile(BaseModel):
    os: str
    os_version: str
    arch: str
    cpu: CPUInfo
    ram_total_gb: float
    ram_available_gb: float
    disk_free_gb: float
    gpus: list[GPUInfo] = Field(default_factory=list)
    accelerator: Accelerator = Accelerator.cpu
    unified_memory: bool = False
    runtimes: list[RuntimeInfo] = Field(default_factory=list)
    on_battery: bool | None = None

    def primary_gpu(self) -> GPUInfo | None:
        """The GPU with the most VRAM, or None if there are no GPUs."""
        if not self.gpus:
            return None
        return max(self.gpus, key=lambda g: g.vram_total_gb or 0.0)

    def usable_memory_gb(self) -> float:
        """Best-effort budget of memory available to load a model.

        - Unified memory (Apple Silicon): ~70% of total RAM (leave room for OS).
        - Discrete CUDA/ROCm GPU: the primary GPU's total VRAM.
        - CPU-only: currently available system RAM.
        """
        if self.unified_memory:
            return round(self.ram_total_gb * 0.7, 1)
        gpu = self.primary_gpu()
        if self.accelerator in (Accelerator.cuda, Accelerator.rocm) and gpu and gpu.vram_total_gb:
            return float(gpu.vram_total_gb)
        return round(self.ram_available_gb, 1)


class MemoryEstimate(BaseModel):
    weights_gb: float
    kv_cache_gb: float
    overhead_gb: float
    total_gb: float


class QuantOption(BaseModel):
    name: str  # e.g. "Q4_K_M"
    bits: float  # effective bits per weight


class CatalogModel(BaseModel):
    model_id: str
    display_name: str
    params_b: float
    quants: list[QuantOption]
    tasks: list[str]
    license: str
    recommended_runtimes: list[str]
    context_options: list[int]
    default_context: int
    n_layers: int | None = None
    hidden_size: int | None = None
    n_heads: int | None = None
    n_kv_heads: int | None = None
    commercial_use: bool = True
    quality_score: float = 0.0  # 0..1 reference quality for the model's tasks
    source_repo: str | None = None


class Recommendation(BaseModel):
    model_id: str
    display_name: str
    runtime: str
    quant: str
    context: int
    estimate: MemoryEstimate
    fits: bool
    headroom_ratio: float
    predicted_tps: float | None = None
    quality_score: float = 0.0
    score: float = 0.0
    why: str = ""
    tradeoffs: list[str] = Field(default_factory=list)


class ChatResult(BaseModel):
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


class BenchmarkResult(BaseModel):
    model_alias: str
    runtime: str
    ttft_ms: float
    tokens_per_second: float
    output_tokens: int = 0
    input_tokens: int = 0
    peak_memory_mb: float | None = None
    max_stable_context: int | None = None
    measured_at: str | None = None
