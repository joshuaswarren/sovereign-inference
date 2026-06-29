# SPDX-License-Identifier: AGPL-3.0-or-later
"""Minimal OpenAI-compatible HTTP client used by runtime adapters and benchmarks.

Two entry points: a blocking ``chat`` and a streaming ``stream_chat`` that
measures time-to-first-token and tokens/sec. Timing uses an injectable ``clock``
so it is deterministic under test.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from .models import ChatResult

Messages = list[dict[str, str]]


def _headers(api_key: str | None) -> dict[str, str]:
    headers = {"content-type": "application/json"}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    return headers


def chat(
    base_url: str,
    model: str,
    messages: Messages,
    *,
    api_key: str | None = None,
    max_tokens: int = 256,
    temperature: float = 0.0,
    timeout: float = 60.0,
    client: httpx.Client | None = None,
) -> ChatResult:
    """Call an OpenAI-compatible /v1/chat/completions endpoint (non-streaming)."""
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    owns = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        response = client.post(f"{base_url}/v1/chat/completions", json=payload, headers=_headers(api_key))
        response.raise_for_status()
        data = response.json()
    finally:
        if owns:
            client.close()

    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    return ChatResult(
        content=content,
        input_tokens=int(usage.get("prompt_tokens", 0)),
        output_tokens=int(usage.get("completion_tokens", 0)),
        model=model,
    )


@dataclass
class StreamStats:
    content: str
    ttft_s: float
    total_s: float
    generation_s: float
    output_tokens: int
    tokens_per_second: float


def stream_chat(
    base_url: str,
    model: str,
    messages: Messages,
    *,
    api_key: str | None = None,
    max_tokens: int = 256,
    temperature: float = 0.0,
    timeout: float = 120.0,
    client: httpx.Client | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> StreamStats:
    """Stream a completion, measuring time-to-first-token and tokens/sec.

    ``clock`` is called once at start, once when the first content token
    arrives, and once at the end — making timing deterministic in tests.
    """
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    owns = client is None
    client = client or httpx.Client(timeout=timeout)

    content_parts: list[str] = []
    ttft: float | None = None
    usage_output_tokens: int | None = None
    chunk_count = 0
    t_start = clock()
    t_end = t_start
    try:
        with client.stream(
            "POST", f"{base_url}/v1/chat/completions", json=payload, headers=_headers(api_key)
        ) as response:
            response.raise_for_status()
            for raw in response.iter_lines():
                if not raw:
                    continue
                line = raw[len("data: ") :] if raw.startswith("data: ") else raw
                if line.strip() == "[DONE]":
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or []
                delta = choices[0].get("delta", {}) if choices else {}
                piece = delta.get("content")
                if piece:
                    if ttft is None:
                        ttft = clock() - t_start
                    content_parts.append(piece)
                    chunk_count += 1
                usage = obj.get("usage")
                if usage and usage.get("completion_tokens") is not None:
                    usage_output_tokens = int(usage["completion_tokens"])
            t_end = clock()
    finally:
        if owns:
            client.close()

    if ttft is None:
        # No content arrived; treat TTFT as the whole window.
        ttft = clock() - t_start
    output_tokens = usage_output_tokens if usage_output_tokens is not None else chunk_count
    total_s = t_end - t_start
    generation_s = max(total_s - ttft, 0.0)
    tps = output_tokens / generation_s if generation_s > 0 else 0.0
    return StreamStats(
        content="".join(content_parts),
        ttft_s=ttft,
        total_s=total_s,
        generation_s=generation_s,
        output_tokens=output_tokens,
        tokens_per_second=tps,
    )
