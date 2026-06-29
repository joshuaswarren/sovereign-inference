# SPDX-License-Identifier: AGPL-3.0-or-later
"""Hardware profiler for the Sovereign Inference Node (``sin scan``).

Produces a machine-readable :class:`~sin_node.models.HardwareProfile` and a
plain-text human summary. Detection is best-effort and degrades gracefully:
every external call (subprocess, ``shutil.which``, HTTP probe) is injected so
unit tests stay deterministic, and any failure resolves to empty/unknown rather
than raising.

The catalog of what we detect:
    - OS name/version + CPU architecture (``platform``).
    - CPU model + physical/logical cores + a best-effort feature list (``psutil``).
    - RAM total/available and free disk on the home directory (``psutil``).
    - GPUs via ``nvidia-smi`` (NVIDIA) or ``rocm-smi`` (AMD); Apple Silicon is
      treated as a single unified-memory ``metal`` GPU.
    - Installed runtimes (Ollama, llama.cpp, LM Studio).
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import httpx
import psutil

from .models import (
    Accelerator,
    CPUInfo,
    GPUInfo,
    GpuVendor,
    HardwareProfile,
    RuntimeInfo,
)

# Injectable external-call types. Defaults touch the real system; tests pass fakes.
Runner = Callable[[list[str]], str]
Which = Callable[[str], str | None]
HttpProbe = Callable[[str], str | None]

_MIB_PER_GB = 1024.0
_BYTES_PER_GB = 1024.0**3
_OLLAMA_VERSION_URL = "http://localhost:11434/api/version"


def _default_runner(cmd: list[str]) -> str:
    """Run ``cmd`` and return stdout, or ``""`` on any failure.

    Never raises: a missing binary, non-zero exit, or timeout all degrade to an
    empty string so callers can treat "no output" as "feature absent".
    """
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout


def _default_http_probe(url: str) -> str | None:
    """GET ``url`` and return the body text, or ``None`` on any failure."""
    try:
        response = httpx.get(url, timeout=1.0)
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    return response.text


def _to_gb_from_mib(raw: str) -> float | None:
    """Parse an nvidia-smi MiB field (``"24564"`` or ``"[N/A]"``) to GB."""
    token = raw.strip()
    if not token or token.upper().strip("[]") in {"N/A", "NA", "NOTSUPPORTED"}:
        return None
    try:
        mib = float(token)
    except ValueError:
        return None
    return round(mib / _MIB_PER_GB, 2)


def parse_nvidia_smi(csv_text: str) -> list[GPUInfo]:
    """Parse ``nvidia-smi --query-gpu=...,--format=csv,noheader,nounits`` output.

    Each line is ``name, memory.total, memory.free, driver_version`` with memory
    in MiB. Malformed rows are skipped rather than fatal.
    """
    gpus: list[GPUInfo] = []
    for line in csv_text.splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        name, total_raw, free_raw, driver = parts[0], parts[1], parts[2], parts[3]
        if not name:
            continue
        gpus.append(
            GPUInfo(
                vendor=GpuVendor.nvidia,
                name=name,
                vram_total_gb=_to_gb_from_mib(total_raw),
                vram_free_gb=_to_gb_from_mib(free_raw),
                driver=driver or None,
            )
        )
    return gpus


def parse_rocm_smi(csv_text: str) -> list[GPUInfo]:
    """Best-effort parse of ``rocm-smi --showproductname --showmeminfo vram --csv``.

    Expects a header row plus one row per card. We look up columns by fuzzy
    header match so minor format drift across ROCm versions degrades to empty
    rather than crashing.
    """
    lines = [ln for ln in csv_text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return []
    header = [h.strip().lower() for h in lines[0].split(",")]

    def _find(*needles: str) -> int | None:
        for idx, col in enumerate(header):
            if all(needle in col for needle in needles):
                return idx
        return None

    name_idx = _find("card", "series") or _find("series")
    used_idx = _find("vram", "used")

    def _find_total() -> int | None:
        # rocm-smi's "used" header ("VRAM Total Used Memory (B)") also contains
        # vram/total/memory, so we must exclude it (and any "used" column) and
        # not depend on column ordering.
        for idx, col in enumerate(header):
            if idx == used_idx or "used" in col:
                continue
            if all(needle in col for needle in ("vram", "total", "memory")):
                return idx
        return None

    total_idx = _find_total()

    gpus: list[GPUInfo] = []
    for line in lines[1:]:
        cells = [c.strip() for c in line.split(",")]
        name = _cell(cells, name_idx) or "AMD GPU"
        total_gb = _bytes_to_gb(_cell(cells, total_idx))
        used_gb = _bytes_to_gb(_cell(cells, used_idx))
        free_gb = None
        if total_gb is not None and used_gb is not None:
            free_gb = round(max(total_gb - used_gb, 0.0), 2)
        gpus.append(
            GPUInfo(
                vendor=GpuVendor.amd,
                name=name,
                vram_total_gb=total_gb,
                vram_free_gb=free_gb,
            )
        )
    return gpus


def _cell(cells: Sequence[str], idx: int | None) -> str:
    return cells[idx] if idx is not None and idx < len(cells) else ""


def _bytes_to_gb(raw: str) -> float | None:
    token = raw.strip()
    if not token:
        return None
    try:
        value = float(token)
    except ValueError:
        return None
    return round(value / _BYTES_PER_GB, 2)


def _is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}


def _cpu_features(arch: str) -> list[str]:
    """Best-effort CPU feature flags. Conservative: only add what we can infer."""
    features: list[str] = []
    arch_l = arch.lower()
    if arch_l in {"arm64", "aarch64"}:
        features.append("neon")
    # x86 AVX2 detection without a CPUID dependency: probe /proc/cpuinfo on Linux.
    if arch_l in {"x86_64", "amd64"}:
        cpuinfo = Path("/proc/cpuinfo")
        try:
            if cpuinfo.exists() and "avx2" in cpuinfo.read_text(encoding="utf-8", errors="ignore"):
                features.append("avx2")
        except OSError:
            pass
    return features


def _detect_cpu() -> CPUInfo:
    arch = platform.machine()
    model = platform.processor() or None
    if not model and _is_apple_silicon():
        model = "Apple Silicon"
    return CPUInfo(
        arch=arch,
        model=model,
        physical_cores=psutil.cpu_count(logical=False),
        logical_cores=psutil.cpu_count(logical=True),
        features=_cpu_features(arch),
    )


def _detect_gpus(runner: Runner, which: Which, *, is_apple_silicon: bool) -> list[GPUInfo]:
    """Detect GPUs across vendors, degrading to an empty list on any failure."""
    if is_apple_silicon:
        # Apple Silicon: the SoC GPU shares unified memory; report one GPU.
        model = platform.processor() or "Apple Silicon"
        return [GPUInfo(vendor=GpuVendor.apple, name=f"{model} GPU")]

    gpus: list[GPUInfo] = []
    if which("nvidia-smi"):
        out = runner(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free,driver_version",
                "--format=csv,noheader,nounits",
            ]
        )
        gpus.extend(parse_nvidia_smi(out))
    if which("rocm-smi"):
        out = runner(["rocm-smi", "--showproductname", "--showmeminfo", "vram", "--csv"])
        gpus.extend(parse_rocm_smi(out))
    return gpus


def resolve_accelerator(gpus: Sequence[GPUInfo], *, is_apple_silicon: bool) -> Accelerator:
    """Pick the compute backend: cuda > rocm > metal > cpu.

    NVIDIA wins over AMD if both are present (CUDA is the more common path).
    """
    vendors = {g.vendor for g in gpus}
    if GpuVendor.nvidia in vendors:
        return Accelerator.cuda
    if GpuVendor.amd in vendors:
        return Accelerator.rocm
    if is_apple_silicon or GpuVendor.apple in vendors:
        return Accelerator.metal
    return Accelerator.cpu


def detect_runtimes(*, which: Which, http_probe: HttpProbe) -> list[RuntimeInfo]:
    """Detect installed local runtimes.

    - ollama: present if the ``ollama`` binary is on PATH OR the local API
      answers; the API also yields a version + endpoint.
    - llama.cpp: present if ``llama-server`` or ``llama-cli`` is on PATH.
    - lmstudio: present if the ``lms`` CLI is on PATH.
    """
    return [
        _detect_ollama(which, http_probe),
        _detect_llamacpp(which),
        _detect_lmstudio(which),
    ]


def _detect_ollama(which: Which, http_probe: HttpProbe) -> RuntimeInfo:
    has_binary = which("ollama") is not None
    version: str | None = None
    endpoint: str | None = None
    body = http_probe(_OLLAMA_VERSION_URL)
    api_up = body is not None
    if api_up:
        endpoint = "http://localhost:11434"
        version = _parse_ollama_version(body)
    return RuntimeInfo(
        name="ollama",
        available=has_binary or api_up,
        version=version,
        endpoint=endpoint,
    )


def _parse_ollama_version(body: str | None) -> str | None:
    if not body:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    version = data.get("version") if isinstance(data, dict) else None
    return str(version) if version is not None else None


def _detect_llamacpp(which: Which) -> RuntimeInfo:
    server = which("llama-server")
    cli = which("llama-cli")
    available = server is not None or cli is not None
    return RuntimeInfo(name="llama.cpp", available=available)


def _detect_lmstudio(which: Which) -> RuntimeInfo:
    return RuntimeInfo(name="lmstudio", available=which("lms") is not None)


def _on_battery() -> bool | None:
    """Whether the machine is currently running on battery, or None if unknown."""
    try:
        battery = psutil.sensors_battery()
    except (AttributeError, OSError, NotImplementedError):
        return None
    if battery is None:
        return None
    return not battery.power_plugged


def scan(
    *,
    runner: Runner = _default_runner,
    which: Which = shutil.which,
    http_probe: HttpProbe = _default_http_probe,
    is_apple_silicon: bool | None = None,
) -> HardwareProfile:
    """Build a :class:`HardwareProfile` for this machine.

    All external calls are injected so the function is fully testable; in
    production the real defaults touch the system. ``is_apple_silicon`` defaults
    to live platform detection but can be forced (e.g. to exercise the
    discrete-GPU path on an Apple-Silicon CI host). Any individual detection
    failure degrades to empty/unknown rather than raising.
    """
    os_name = platform.system() or "unknown"
    os_version = (platform.mac_ver()[0] or platform.release()) if os_name == "Darwin" else platform.release()
    arch = platform.machine() or "unknown"

    vmem = psutil.virtual_memory()
    ram_total_gb = round(vmem.total / _BYTES_PER_GB, 2)
    ram_available_gb = round(vmem.available / _BYTES_PER_GB, 2)
    disk_free_gb = _home_disk_free_gb()

    apple = _is_apple_silicon() if is_apple_silicon is None else is_apple_silicon
    gpus = _detect_gpus(runner, which, is_apple_silicon=apple)
    accelerator = resolve_accelerator(gpus, is_apple_silicon=apple)

    return HardwareProfile(
        os=os_name,
        os_version=os_version or "unknown",
        arch=arch,
        cpu=_detect_cpu(),
        ram_total_gb=ram_total_gb,
        ram_available_gb=ram_available_gb,
        disk_free_gb=disk_free_gb,
        gpus=gpus,
        accelerator=accelerator,
        unified_memory=apple,
        runtimes=detect_runtimes(which=which, http_probe=http_probe),
        on_battery=_on_battery(),
    )


def _home_disk_free_gb() -> float:
    try:
        usage = psutil.disk_usage(str(Path.home()))
    except (OSError, ValueError):
        return 0.0
    return round(usage.free / _BYTES_PER_GB, 2)


def render(profile: HardwareProfile) -> str:
    """A concise, plain-text human summary of a hardware profile."""
    lines: list[str] = []
    lines.append(f"System:  {profile.os} {profile.os_version} ({profile.arch})")

    cpu = profile.cpu
    cores = _format_cores(cpu.physical_cores, cpu.logical_cores)
    cpu_model = cpu.model or "unknown CPU"
    feature_suffix = f" [{', '.join(cpu.features)}]" if cpu.features else ""
    lines.append(f"CPU:     {cpu_model} ({cores}){feature_suffix}")

    lines.append(
        f"Memory:  {profile.ram_available_gb:.1f} GB free of {profile.ram_total_gb:.1f} GB"
        + (" (unified)" if profile.unified_memory else "")
    )
    lines.append(f"Disk:    {profile.disk_free_gb:.1f} GB free")
    lines.append(f"Compute: {profile.accelerator.value}")

    if profile.gpus:
        for gpu in profile.gpus:
            vram = f" — {gpu.vram_total_gb:.1f} GB VRAM" if gpu.vram_total_gb else ""
            lines.append(f"GPU:     {gpu.name} [{gpu.vendor.value}]{vram}")
    else:
        lines.append("GPU:     none detected")

    available = [r.name for r in profile.runtimes if r.available]
    lines.append("Runtimes: " + (", ".join(available) if available else "none detected"))

    if profile.on_battery is not None:
        lines.append("Power:   " + ("on battery" if profile.on_battery else "plugged in"))

    return "\n".join(lines)


def _format_cores(physical: int | None, logical: int | None) -> str:
    if physical and logical:
        return f"{physical} cores / {logical} threads"
    if logical:
        return f"{logical} threads"
    if physical:
        return f"{physical} cores"
    return "unknown cores"
