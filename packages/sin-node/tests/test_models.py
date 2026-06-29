# SPDX-License-Identifier: AGPL-3.0-or-later
from sin_node.models import (
    Accelerator,
    CPUInfo,
    GPUInfo,
    GpuVendor,
    HardwareProfile,
)


def _profile(**over) -> HardwareProfile:
    base: dict = {
        "os": "Linux",
        "os_version": "6.0",
        "arch": "x86_64",
        "cpu": CPUInfo(arch="x86_64", model="Test", physical_cores=8, logical_cores=16),
        "ram_total_gb": 32.0,
        "ram_available_gb": 20.4,
        "disk_free_gb": 100.0,
        "gpus": [],
        "accelerator": Accelerator.cpu,
        "unified_memory": False,
        "runtimes": [],
    }
    base.update(over)
    return HardwareProfile(**base)


def test_unified_memory_usable_is_70_percent_of_total() -> None:
    p = _profile(
        os="Darwin",
        arch="arm64",
        ram_total_gb=16.0,
        gpus=[GPUInfo(vendor=GpuVendor.apple, name="Apple M2 GPU")],
        accelerator=Accelerator.metal,
        unified_memory=True,
    )
    assert p.usable_memory_gb() == 11.2  # 16 * 0.7


def test_discrete_gpu_usable_is_max_vram() -> None:
    p = _profile(
        ram_total_gb=64.0,
        ram_available_gb=50.0,
        gpus=[GPUInfo(vendor=GpuVendor.nvidia, name="RTX 4090", vram_total_gb=24.0)],
        accelerator=Accelerator.cuda,
    )
    assert p.usable_memory_gb() == 24.0


def test_cpu_only_usable_is_available_ram() -> None:
    assert _profile().usable_memory_gb() == 20.4


def test_primary_gpu_returns_highest_vram() -> None:
    p = _profile(
        gpus=[
            GPUInfo(vendor=GpuVendor.nvidia, name="A", vram_total_gb=8.0),
            GPUInfo(vendor=GpuVendor.nvidia, name="B", vram_total_gb=24.0),
        ],
        accelerator=Accelerator.cuda,
    )
    assert p.primary_gpu() is not None
    assert p.primary_gpu().name == "B"


def test_no_gpu_primary_is_none() -> None:
    assert _profile().primary_gpu() is None
