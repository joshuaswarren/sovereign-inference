# SPDX-License-Identifier: Apache-2.0
"""Ollama runtime adapter.

Ollama exposes two surfaces: an OpenAI-compatible API under ``/v1`` (used for
chat/stream/health via :class:`~sin_node.adapter.OpenAICompatibleAdapter`) and a
native API at the root (``/api/version``, ``/api/tags``, ``/api/pull``) used for
detection, model listing, and pulling.

Every external call (HTTP and ``shutil.which``) is injectable so unit tests run
without a real Ollama install, and every failure degrades to empty/unknown
rather than crashing the caller.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from typing import Any

import httpx

from sin_node.adapter import (
    OpenAICompatibleAdapter,
    ServerHandle,
    register_adapter,
)
from sin_node.models import RuntimeInfo

DEFAULT_BASE_URL = "http://localhost:11434"

WhichFn = Callable[[str], str | None]


class OllamaAdapter(OpenAICompatibleAdapter):
    """Runtime adapter for a local Ollama server."""

    name = "ollama"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        client: httpx.Client | None = None,
        which: WhichFn = shutil.which,
    ) -> None:
        super().__init__(base_url, client=client)
        self._which = which

    # -- native Ollama API helpers -------------------------------------------

    def _get_version(self) -> str | None:
        """Return the Ollama version from ``/api/version``, or None if unreachable."""
        owns = self._client is None
        client = self._client or httpx.Client(timeout=2.0)
        try:
            response = client.get(f"{self.base_url}/api/version")
            response.raise_for_status()
            version = response.json().get("version")
            return str(version) if version is not None else None
        except (httpx.HTTPError, ValueError):
            return None
        finally:
            if owns:
                client.close()

    # -- RuntimeAdapter protocol ---------------------------------------------

    def detect(self) -> RuntimeInfo:
        """Detect Ollama via the binary on PATH or a responsive native API."""
        version = self._get_version()
        has_binary = self._which("ollama") is not None
        available = has_binary or version is not None
        return RuntimeInfo(
            name=self.name,
            available=available,
            version=version,
            endpoint=self.base_url,
        )

    def is_available(self) -> bool:
        return bool(self.detect().available)

    def list_models(self) -> list[str]:
        """List locally available model names via ``/api/tags`` (empty on failure)."""
        owns = self._client is None
        client = self._client or httpx.Client(timeout=5.0)
        try:
            response = client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            models = response.json().get("models") or []
            return [str(m["name"]) for m in models if isinstance(m, dict) and "name" in m]
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return []
        finally:
            if owns:
                client.close()

    def pull(self, model: str) -> None:
        """Pull a model via ``/api/pull``, consuming the progress stream.

        Failures degrade silently; callers verify availability separately.
        """
        owns = self._client is None
        client = self._client or httpx.Client(timeout=None)
        try:
            with client.stream(
                "POST",
                f"{self.base_url}/api/pull",
                json={"name": model, "stream": True},
            ) as response:
                response.raise_for_status()
                for _ in response.iter_lines():
                    # Drain the NDJSON progress stream until the pull completes.
                    pass
        except httpx.HTTPError:
            return
        finally:
            if owns:
                client.close()

    def serve(self, model: str, **kwargs: Any) -> ServerHandle:
        """Ollama auto-serves; verify reachability and return a handle."""
        if self._get_version() is None:
            raise RuntimeError(f"Ollama is not reachable at {self.base_url}; start it with `ollama serve`.")
        return ServerHandle(base_url=self.base_url, runtime=self.name)

    def stop(self) -> None:
        """No-op: the Ollama daemon is managed outside this process."""
        return None


register_adapter("ollama", OllamaAdapter)
