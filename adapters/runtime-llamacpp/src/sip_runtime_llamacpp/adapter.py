# SPDX-License-Identifier: Apache-2.0
"""llama.cpp runtime adapter.

Manages a ``llama-server`` subprocess that exposes an OpenAI-compatible
endpoint. The adapter subclasses :class:`OpenAICompatibleAdapter` so chat and
streaming come for free; it adds detection, serving, and lifecycle management.

Every external interaction (binary lookup, process spawn, health probe, sleep)
is injected so unit tests never touch the real system, and every such call
degrades gracefully (empty/unknown, never a crash) when it fails.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx

from sin_node.adapter import OpenAICompatibleAdapter, ServerHandle
from sin_node.models import RuntimeInfo

#: The name every other component refers to this adapter by.
RUNTIME_NAME = "llama.cpp"
#: The server binary shipped by llama.cpp.
BINARY = "llama-server"

WhichFn = Callable[[str], str | None]
SpawnFn = Callable[[list[str]], Any]
HealthCheckFn = Callable[[str], bool]
SleepFn = Callable[[float], None]


def _default_health_check(base_url: str) -> bool:
    """Probe ``GET {base_url}/health`` and report readiness.

    Any transport error or non-2xx response is treated as "not ready yet"
    rather than propagating, so polling can simply retry.
    """
    try:
        with httpx.Client(timeout=2.0) as client:
            response = client.get(f"{base_url}/health")
        return response.status_code == 200
    except httpx.HTTPError:
        return False


class LlamaCppAdapter(OpenAICompatibleAdapter):  # base untyped (no py.typed)
    """Runtime adapter that serves GGUF models via ``llama-server``."""

    name = RUNTIME_NAME

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        *,
        client: httpx.Client | None = None,
        which: WhichFn = shutil.which,
    ) -> None:
        super().__init__(base_url, client=client)
        self._which = which
        self._process: Any | None = None
        self._served_model: str | None = None

    # -- detection -------------------------------------------------------

    def detect(self) -> RuntimeInfo:
        """Report whether ``llama-server`` is on PATH."""
        available = self.is_available()
        return RuntimeInfo(name=RUNTIME_NAME, available=available, endpoint=self.base_url)

    def is_available(self) -> bool:
        try:
            return self._which(BINARY) is not None
        except OSError:
            return False

    # -- command construction (pure) -------------------------------------

    def build_command(
        self,
        model_path: str,
        *,
        port: int = 8080,
        ctx_size: int = 4096,
        n_gpu_layers: int | None = None,
        extra: Sequence[str] | None = None,
    ) -> list[str]:
        """Build the ``llama-server`` argv. Pure and deterministic."""
        cmd: list[str] = [
            BINARY,
            "-m",
            model_path,
            "--port",
            str(port),
            "-c",
            str(ctx_size),
        ]
        if n_gpu_layers is not None:
            cmd += ["--n-gpu-layers", str(n_gpu_layers)]
        if extra:
            cmd += list(extra)
        return cmd

    # -- serving ---------------------------------------------------------

    def serve(
        self,
        model_path: str,
        *,
        port: int = 8080,
        ctx_size: int = 4096,
        n_gpu_layers: int | None = None,
        extra: Sequence[str] | None = None,
        spawn: SpawnFn = subprocess.Popen,
        health_check: HealthCheckFn = _default_health_check,
        sleep: SleepFn = time.sleep,
        poll_interval: float = 1.0,
        retries: int = 30,
        **_: Any,
    ) -> ServerHandle:
        """Spawn ``llama-server`` and poll ``/health`` until it is ready.

        Raises :class:`TimeoutError` if the server is not healthy within
        ``retries`` polls. The returned handle's ``stop`` terminates the
        process.
        """
        cmd = self.build_command(
            model_path,
            port=port,
            ctx_size=ctx_size,
            n_gpu_layers=n_gpu_layers,
            extra=extra,
        )
        process = spawn(cmd)
        base_url = f"http://localhost:{port}"

        ready = False
        for attempt in range(retries):
            if health_check(base_url):
                ready = True
                break
            if attempt < retries - 1:
                sleep(poll_interval)
        if not ready:
            self._terminate(process)
            raise TimeoutError(f"llama-server did not become healthy at {base_url} after {retries} attempts")

        self._process = process
        self._served_model = model_path
        self.base_url = base_url
        pid = getattr(process, "pid", None)
        return ServerHandle(
            base_url=base_url,
            runtime=RUNTIME_NAME,
            pid=pid,
            stop=lambda: self._terminate(process),
        )

    # -- model management ------------------------------------------------

    def list_models(self) -> list[str]:
        """llama.cpp serves a single local GGUF; return it if one is loaded."""
        return [self._served_model] if self._served_model else []

    def pull(self, model: str) -> None:
        """llama.cpp has no registry; the user must supply a local GGUF path."""
        raise NotImplementedError(
            "llama.cpp does not pull models. Download a GGUF file (e.g. from "
            "Hugging Face) and pass its local path to serve(model_path=...)."
        )

    # -- lifecycle -------------------------------------------------------

    def health(self) -> bool:
        """Report server readiness via ``GET {base_url}/health``."""
        owns = self._client is None
        client = self._client or httpx.Client(timeout=2.0)
        try:
            response = client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False
        finally:
            if owns:
                client.close()

    def stop(self) -> None:
        """Terminate the managed process, if any. Safe to call repeatedly."""
        if self._process is not None:
            self._terminate(self._process)
            self._process = None
            self._served_model = None

    @staticmethod
    def _terminate(process: Any) -> None:
        terminate = getattr(process, "terminate", None)
        if callable(terminate):
            with contextlib.suppress(OSError):
                terminate()
