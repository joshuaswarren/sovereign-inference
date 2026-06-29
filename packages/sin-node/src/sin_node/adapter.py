# SPDX-License-Identifier: AGPL-3.0-or-later
"""Runtime adapter contract and a reusable OpenAI-compatible base.

Concrete adapters (Ollama, llama.cpp, ...) live in their own packages and
implement :class:`RuntimeAdapter`. They may subclass
:class:`OpenAICompatibleAdapter` to inherit chat/stream/health over a standard
``/v1`` endpoint, adding only detection, pulling, and serving.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import httpx

from . import http
from .http import StreamStats
from .models import ChatResult, RuntimeInfo

Messages = list[dict[str, str]]


@dataclass
class ServerHandle:
    base_url: str
    runtime: str
    pid: int | None = None
    stop: Callable[[], None] | None = None


@runtime_checkable
class RuntimeAdapter(Protocol):
    """The interface every runtime adapter implements."""

    name: str

    def detect(self) -> RuntimeInfo: ...
    def is_available(self) -> bool: ...
    def list_models(self) -> list[str]: ...
    def pull(self, model: str) -> None: ...
    def serve(self, model: str, **kwargs: Any) -> ServerHandle: ...
    def chat(self, model: str, messages: Messages, **kwargs: Any) -> ChatResult: ...
    def health(self) -> bool: ...
    def stop(self) -> None: ...


class OpenAICompatibleAdapter:
    """Reusable base for adapters that speak OpenAI-compatible HTTP."""

    name = "openai-compatible"

    def __init__(self, base_url: str, *, client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client

    def chat(self, model: str, messages: Messages, **kwargs: Any) -> ChatResult:
        return http.chat(self.base_url, model, messages, client=self._client, **kwargs)

    def stream(self, model: str, messages: Messages, **kwargs: Any) -> StreamStats:
        return http.stream_chat(self.base_url, model, messages, client=self._client, **kwargs)

    def health(self) -> bool:
        owns = self._client is None
        client = self._client or httpx.Client(timeout=2.0)
        try:
            response = client.get(f"{self.base_url}/v1/models")
            return response.status_code < 500
        except httpx.HTTPError:
            return False
        finally:
            if owns:
                client.close()


class AdapterRegistry:
    """Maps adapter names to factories so the CLI can wire adapters by name."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, factory: Callable[..., Any]) -> None:
        self._factories[name] = factory

    def get(self, name: str, *args: Any, **kwargs: Any) -> Any:
        if name not in self._factories:
            raise KeyError(f"no runtime adapter registered as {name!r}")
        return self._factories[name](*args, **kwargs)

    def names(self) -> list[str]:
        return sorted(self._factories)


registry = AdapterRegistry()


def register_adapter(name: str, factory: Callable[..., Any]) -> None:
    registry.register(name, factory)


def get_adapter(name: str, *args: Any, **kwargs: Any) -> Any:
    return registry.get(name, *args, **kwargs)


def available_adapter_names() -> list[str]:
    return registry.names()
