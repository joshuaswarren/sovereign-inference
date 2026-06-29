# SPDX-License-Identifier: AGPL-3.0-or-later
"""Benchmark runner for the Sovereign Inference Node (``sin benchmark``).

Measures tokens/sec, time-to-first-token, output length, and (best effort) peak
memory for a served model, then packages the result into a signed provider
manifest other nodes/clients can verify.

All external calls (HTTP client, clock, wall-clock ``now``) are injected so the
unit tests run without touching the network or the real system clock.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from sip_protocol import KeyPair, sign_provider_manifest

from .http import stream_chat
from .models import BenchmarkResult, HardwareProfile

DEFAULT_PROMPT = "Write a haiku about the sea."


def _utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string ending in ``Z``."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def benchmark_endpoint(
    base_url: str,
    model: str,
    *,
    runtime: str = "unknown",
    prompt: str = DEFAULT_PROMPT,
    max_tokens: int = 128,
    client: httpx.Client | None = None,
    clock: Callable[[], float] = time.perf_counter,
    now: Callable[[], str] = _utc_now_iso,
) -> BenchmarkResult:
    """Stream one completion and turn the timing into a :class:`BenchmarkResult`.

    ``ttft_ms`` is the streamed time-to-first-token in milliseconds and
    ``tokens_per_second`` is the steady-state generation throughput, both taken
    from :func:`sin_node.http.stream_chat`. ``measured_at`` is stamped from
    ``now()``.
    """
    messages = [{"role": "user", "content": prompt}]
    stats = stream_chat(
        base_url,
        model,
        messages,
        max_tokens=max_tokens,
        client=client,
        clock=clock,
    )
    return BenchmarkResult(
        model_alias=model,
        runtime=runtime,
        ttft_ms=stats.ttft_s * 1000.0,
        tokens_per_second=stats.tokens_per_second,
        output_tokens=stats.output_tokens,
        measured_at=now(),
    )


class _Prober(Protocol):
    def __call__(self, context: int) -> bool: ...


def probe_max_stable_context(
    contexts: Sequence[int],
    prober: _Prober,
) -> int | None:
    """Return the largest context that succeeds before the first failure.

    ``contexts`` is assumed to be in ascending order. We probe each in turn and
    stop at the first failure, returning the last context that passed (or
    ``None`` if the very first probe failed / there are no contexts). Stopping
    on first failure avoids hammering a node that is already out of memory.
    """
    best: int | None = None
    for context in contexts:
        if prober(context):
            best = context
        else:
            break
    return best


def peak_memory_mb(pid: int) -> float | None:
    """Best-effort resident set size of a process in MB, or ``None``.

    Degrades to ``None`` if ``psutil`` is unavailable or the process cannot be
    inspected (gone, access denied, etc.) — never raises.
    """
    try:
        import psutil
    except ImportError:
        return None
    try:
        process = psutil.Process(pid)
        rss_bytes = process.memory_info().rss
    except Exception:
        return None
    return round(rss_bytes / (1024 * 1024), 1)


def _runtime_adapters(profile: HardwareProfile, result: BenchmarkResult) -> list[str]:
    """Adapter names to advertise: detected-and-available runtimes, else the
    runtime that produced the benchmark."""
    available = [r.name for r in profile.runtimes if r.available]
    if available:
        return available
    return [result.runtime]


def to_provider_manifest(
    profile: HardwareProfile,
    *,
    models: Sequence[str],
    result: BenchmarkResult,
    pricing: dict[str, Any],
    privacy_modes: Sequence[str],
    keypair: KeyPair,
    node_type: str = "sovereign-node",
    published_at: str,
    logging_policy: str = "no_prompt_logging",
) -> dict[str, Any]:
    """Build and sign a ``sip-ai.provider_manifest.v1`` manifest.

    The benchmark is embedded with sensibly rounded numbers and the document is
    signed via :func:`sip_protocol.sign_provider_manifest`, so the result passes
    :func:`sip_protocol.verify_provider_manifest`.
    """
    max_context = result.max_stable_context
    if max_context is None:
        max_context = 4096
    manifest: dict[str, Any] = {
        "schema": "sip-ai.provider_manifest.v1",
        "provider_pubkey": keypair.public_key_str,
        "node_type": node_type,
        "models": list(models),
        "runtime_adapters": _runtime_adapters(profile, result),
        "pricing": dict(pricing),
        "max_context": max_context,
        "logging_policy": logging_policy,
        "privacy_modes": list(privacy_modes),
        "benchmark": {
            "tokens_per_second": round(result.tokens_per_second, 1),
            "ttft_ms": round(result.ttft_ms),
        },
        "published_at": published_at,
    }
    signed: dict[str, Any] = sign_provider_manifest(manifest, keypair)
    return signed
