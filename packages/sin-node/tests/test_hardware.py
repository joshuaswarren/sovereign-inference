# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the hardware profiler (``sin scan``).

Pure parser helpers are tested against realistic sample text. Runtime detection
is tested with fake ``which`` + ``http_probe`` so it never touches the real
system. A single smoke test calls the real ``scan()`` and only asserts sane
types — never exact hardware values.
"""

from __future__ import annotations

from sin_node.hardware import (
    detect_runtimes,
    parse_nvidia_smi,
    parse_rocm_smi,
    render,
    resolve_accelerator,
    scan,
)
from sin_node.models import Accelerator, GPUInfo, GpuVendor, HardwareProfile

# --- nvidia-smi parsing -----------------------------------------------------

# `nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version
#  --format=csv,noheader,nounits` (memory in MiB).
NVIDIA_SMI_TWO_GPU = (
    "NVIDIA GeForce RTX 4090, 24564, 23000, 550.54.14\nNVIDIA GeForce RTX 3090, 24576, 12288, 550.54.14\n"
)


def test_parse_nvidia_smi_two_gpus() -> None:
    gpus = parse_nvidia_smi(NVIDIA_SMI_TWO_GPU)
    assert len(gpus) == 2

    first = gpus[0]
    assert isinstance(first, GPUInfo)
    assert first.vendor == GpuVendor.nvidia
    assert first.name == "NVIDIA GeForce RTX 4090"
    assert first.driver == "550.54.14"
    # 24564 MiB -> ~24.0 GB (MiB / 1024).
    assert first.vram_total_gb is not None
    assert 23.5 < first.vram_total_gb < 24.5
    assert first.vram_free_gb is not None
    assert 22.0 < first.vram_free_gb < 23.0

    assert gpus[1].name == "NVIDIA GeForce RTX 3090"


def test_parse_nvidia_smi_empty_and_garbage() -> None:
    assert parse_nvidia_smi("") == []
    assert parse_nvidia_smi("\n   \n") == []
    # A malformed row is skipped, not fatal.
    assert parse_nvidia_smi("only-a-name\n") == []


def test_parse_nvidia_smi_handles_na_memory() -> None:
    gpus = parse_nvidia_smi("NVIDIA A100, [N/A], [N/A], 535.104.05\n")
    assert len(gpus) == 1
    assert gpus[0].name == "NVIDIA A100"
    assert gpus[0].vram_total_gb is None
    assert gpus[0].vram_free_gb is None
    assert gpus[0].driver == "535.104.05"


# --- rocm-smi parsing -------------------------------------------------------

ROCM_SMI_CSV = (
    "device,Card series,VRAM Total Memory (B),VRAM Total Used Memory (B)\n"
    "card0,Radeon RX 7900 XTX,25753026560,1073741824\n"
)


def test_parse_rocm_smi_one_gpu() -> None:
    gpus = parse_rocm_smi(ROCM_SMI_CSV)
    assert len(gpus) == 1
    gpu = gpus[0]
    assert gpu.vendor == GpuVendor.amd
    assert "7900" in gpu.name
    assert gpu.vram_total_gb is not None
    assert 23.0 < gpu.vram_total_gb < 25.0
    # free = total - used.
    assert gpu.vram_free_gb is not None
    assert gpu.vram_free_gb < gpu.vram_total_gb


def test_parse_rocm_smi_empty() -> None:
    assert parse_rocm_smi("") == []
    assert parse_rocm_smi("device,Card series\n") == []


# Same data, but the "Used" column precedes the "Total" column. The 'used'
# header also contains vram/total/memory, so a naive first-match would mislabel
# total as ~1 GB. Total must still resolve to ~24 GB regardless of order.
ROCM_SMI_CSV_USED_FIRST = (
    "device,Card series,VRAM Total Used Memory (B),VRAM Total Memory (B)\n"
    "card0,Radeon RX 7900 XTX,1073741824,25753026560\n"
)


def test_parse_rocm_smi_used_column_before_total() -> None:
    gpus = parse_rocm_smi(ROCM_SMI_CSV_USED_FIRST)
    assert len(gpus) == 1
    gpu = gpus[0]
    assert gpu.vram_total_gb is not None and 23.0 < gpu.vram_total_gb < 25.0
    assert gpu.vram_free_gb is not None and 22.0 < gpu.vram_free_gb < 24.0


# --- runtime detection ------------------------------------------------------


def test_detect_runtimes_ollama_via_which() -> None:
    def which(name: str) -> str | None:
        return "/usr/local/bin/ollama" if name == "ollama" else None

    def http_probe(url: str) -> str | None:
        return None  # network unavailable

    runtimes = detect_runtimes(which=which, http_probe=http_probe)
    by_name = {r.name: r for r in runtimes}
    assert by_name["ollama"].available is True
    assert by_name["llama.cpp"].available is False
    assert by_name["lmstudio"].available is False


def test_detect_runtimes_ollama_via_http_probe_only() -> None:
    # ollama binary not on PATH, but the API answers -> still available.
    def which(name: str) -> str | None:
        return None

    def http_probe(url: str) -> str | None:
        if "11434" in url:
            return '{"version": "0.3.12"}'
        return None

    runtimes = detect_runtimes(which=which, http_probe=http_probe)
    by_name = {r.name: r for r in runtimes}
    ollama = by_name["ollama"]
    assert ollama.available is True
    assert ollama.version == "0.3.12"
    assert ollama.endpoint is not None and "11434" in ollama.endpoint


def test_detect_runtimes_llamacpp_and_lmstudio() -> None:
    def which(name: str) -> str | None:
        mapping = {
            "llama-server": "/opt/llama.cpp/llama-server",
            "lms": "/usr/bin/lms",
        }
        return mapping.get(name)

    def http_probe(url: str) -> str | None:
        return None

    by_name = {r.name: r for r in detect_runtimes(which=which, http_probe=http_probe)}
    assert by_name["llama.cpp"].available is True
    assert by_name["lmstudio"].available is True
    assert by_name["ollama"].available is False


def test_detect_runtimes_llamacpp_via_cli_fallback() -> None:
    # Only llama-cli present (not llama-server) still counts as available.
    def which(name: str) -> str | None:
        return "/opt/llama.cpp/llama-cli" if name == "llama-cli" else None

    by_name = {r.name: r for r in detect_runtimes(which=which, http_probe=lambda url: None)}
    assert by_name["llama.cpp"].available is True


# --- accelerator resolution -------------------------------------------------


def test_resolve_accelerator_cuda_for_nvidia() -> None:
    gpus = [GPUInfo(vendor=GpuVendor.nvidia, name="RTX 4090", vram_total_gb=24.0)]
    assert resolve_accelerator(gpus, is_apple_silicon=False) == Accelerator.cuda


def test_resolve_accelerator_rocm_for_amd() -> None:
    gpus = [GPUInfo(vendor=GpuVendor.amd, name="RX 7900", vram_total_gb=24.0)]
    assert resolve_accelerator(gpus, is_apple_silicon=False) == Accelerator.rocm


def test_resolve_accelerator_metal_for_apple_silicon() -> None:
    gpus = [GPUInfo(vendor=GpuVendor.apple, name="Apple M3 Max")]
    assert resolve_accelerator(gpus, is_apple_silicon=True) == Accelerator.metal


def test_resolve_accelerator_cpu_when_no_gpu() -> None:
    assert resolve_accelerator([], is_apple_silicon=False) == Accelerator.cpu


def test_resolve_accelerator_prefers_cuda_over_amd() -> None:
    gpus = [
        GPUInfo(vendor=GpuVendor.amd, name="RX 7900", vram_total_gb=24.0),
        GPUInfo(vendor=GpuVendor.nvidia, name="RTX 4090", vram_total_gb=24.0),
    ]
    assert resolve_accelerator(gpus, is_apple_silicon=False) == Accelerator.cuda


# --- render -----------------------------------------------------------------


def test_render_is_plain_text_with_key_fields() -> None:
    profile = HardwareProfile(
        os="Darwin",
        os_version="14.5",
        arch="arm64",
        cpu=__import__("sin_node.models", fromlist=["CPUInfo"]).CPUInfo(
            arch="arm64", model="Apple M3 Max", physical_cores=12, logical_cores=12
        ),
        ram_total_gb=64.0,
        ram_available_gb=40.0,
        disk_free_gb=500.0,
        gpus=[GPUInfo(vendor=GpuVendor.apple, name="Apple M3 Max GPU")],
        accelerator=Accelerator.metal,
        unified_memory=True,
    )
    text = render(profile)
    assert isinstance(text, str)
    assert "Darwin" in text
    assert "arm64" in text
    assert "metal" in text
    # No markup leakage from rich.
    assert "[/" not in text


# --- scan injection (deterministic, no real subprocess) ---------------------


def test_scan_forces_non_apple_path_and_detects_injected_nvidia_gpu() -> None:
    # Force the discrete-GPU path (is_apple_silicon=False) so this is a real
    # assertion even on an Apple-Silicon dev/CI host: the injected nvidia-smi
    # output must be wired into the profile.
    def runner(cmd: list[str]) -> str:
        if cmd and cmd[0] == "nvidia-smi":
            return "NVIDIA RTX 4090, 24564, 23000, 550.54.14\n"
        return ""

    def which(name: str) -> str | None:
        if name in {"nvidia-smi", "ollama"}:
            return f"/usr/bin/{name}"
        return None

    profile = scan(runner=runner, which=which, http_probe=lambda url: None, is_apple_silicon=False)
    assert isinstance(profile, HardwareProfile)
    nvidia = [g for g in profile.gpus if g.vendor == GpuVendor.nvidia]
    assert len(nvidia) == 1
    assert nvidia[0].name == "NVIDIA RTX 4090"
    assert nvidia[0].vram_total_gb is not None and 23.5 < nvidia[0].vram_total_gb < 24.5
    assert profile.accelerator == Accelerator.cuda
    assert profile.unified_memory is False
    assert any(r.name == "ollama" and r.available for r in profile.runtimes)


# --- real-scan smoke test ---------------------------------------------------


def test_scan_smoke_real_machine() -> None:
    """The only test that touches the real system. Asserts sane types only."""
    profile = scan()
    assert isinstance(profile, HardwareProfile)
    assert isinstance(profile.os, str) and profile.os
    assert isinstance(profile.arch, str) and profile.arch
    assert profile.cpu.arch
    assert profile.ram_total_gb > 0
    assert profile.ram_available_gb >= 0
    assert profile.disk_free_gb >= 0
    assert profile.accelerator in set(Accelerator)
    assert isinstance(profile.gpus, list)
    assert isinstance(profile.runtimes, list)
    # render() must not crash on a real profile.
    assert isinstance(render(profile), str)
