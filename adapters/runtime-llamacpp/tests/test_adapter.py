# SPDX-License-Identifier: Apache-2.0
"""Tests for the llama.cpp runtime adapter.

External calls (subprocess spawn, ``shutil.which``, health probes, sleep) are
injected so these unit tests never touch the real system or spawn a process.
"""

from __future__ import annotations

import subprocess

import httpx
import pytest
from sip_runtime_llamacpp.adapter import LlamaCppAdapter

from sin_node.adapter import OpenAICompatibleAdapter, ServerHandle, get_adapter


class FakeProcess:
    """Stand-in for ``subprocess.Popen`` returned by a fake spawn.

    A ``wedged`` process ignores SIGTERM: the post-terminate ``wait`` times out
    until it is ``kill``ed, modeling a server that must be escalated to SIGKILL.
    """

    def __init__(self, pid: int = 4321, *, wedged: bool = False) -> None:
        self.pid = pid
        self.terminated = False
        self.killed = False
        self.wait_calls = 0
        self._wedged = wedged

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self._wedged and not self.killed:
            raise subprocess.TimeoutExpired(cmd="llama-server", timeout=timeout)
        return 0


def _mock_client(handler: object) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


def test_name_and_subclass() -> None:
    adapter = LlamaCppAdapter()
    assert adapter.name == "llama.cpp"
    assert isinstance(adapter, OpenAICompatibleAdapter)


def test_build_command_defaults() -> None:
    adapter = LlamaCppAdapter()
    cmd = adapter.build_command("/models/qwen.gguf")
    assert cmd == [
        "llama-server",
        "-m",
        "/models/qwen.gguf",
        "--port",
        "8080",
        "-c",
        "4096",
    ]


def test_build_command_custom_port_and_ctx() -> None:
    adapter = LlamaCppAdapter()
    cmd = adapter.build_command("/m/model.gguf", port=9090, ctx_size=8192)
    assert cmd == [
        "llama-server",
        "-m",
        "/m/model.gguf",
        "--port",
        "9090",
        "-c",
        "8192",
    ]


def test_build_command_n_gpu_layers() -> None:
    adapter = LlamaCppAdapter()
    cmd = adapter.build_command("/m/model.gguf", n_gpu_layers=35)
    assert "--n-gpu-layers" in cmd
    assert cmd[cmd.index("--n-gpu-layers") + 1] == "35"


def test_build_command_extra_args_appended() -> None:
    adapter = LlamaCppAdapter()
    cmd = adapter.build_command("/m/model.gguf", extra=["--flash-attn", "--no-mmap"])
    assert cmd[-2:] == ["--flash-attn", "--no-mmap"]


def test_detect_available_when_binary_found() -> None:
    adapter = LlamaCppAdapter(which=lambda name: "/usr/local/bin/llama-server")
    info = adapter.detect()
    assert info.name == "llama.cpp"
    assert info.available is True


def test_detect_unavailable_when_binary_missing() -> None:
    adapter = LlamaCppAdapter(which=lambda name: None)
    info = adapter.detect()
    assert info.name == "llama.cpp"
    assert info.available is False


def test_is_available_reflects_which() -> None:
    present = LlamaCppAdapter(which=lambda name: "/usr/bin/llama-server")
    absent = LlamaCppAdapter(which=lambda name: None)
    assert present.is_available() is True
    assert absent.is_available() is False


def test_serve_polls_health_until_ready_and_returns_handle() -> None:
    proc = FakeProcess(pid=777)
    spawn_calls: list[list[str]] = []
    sleeps: list[float] = []
    health_states = iter([False, False, True])

    def fake_spawn(cmd: list[str]) -> FakeProcess:
        spawn_calls.append(cmd)
        return proc

    handle = LlamaCppAdapter().serve(
        "/models/qwen.gguf",
        port=8080,
        spawn=fake_spawn,
        health_check=lambda base_url: next(health_states),
        sleep=sleeps.append,
        retries=30,
    )

    assert isinstance(handle, ServerHandle)
    assert handle.base_url == "http://localhost:8080"
    assert handle.runtime == "llama.cpp"
    assert handle.pid == 777
    # Spawned the expected command exactly once.
    assert len(spawn_calls) == 1
    assert spawn_calls[0][0] == "llama-server"
    # Polled health three times (two failures then success) -> slept twice.
    assert len(sleeps) == 2


def test_serve_handle_stop_terminates_process() -> None:
    proc = FakeProcess()
    handle = LlamaCppAdapter().serve(
        "/models/m.gguf",
        spawn=lambda cmd: proc,
        health_check=lambda base_url: True,
        sleep=lambda s: None,
    )
    assert handle.stop is not None
    handle.stop()
    assert proc.terminated is True


def test_serve_health_check_receives_base_url() -> None:
    seen: list[str] = []

    def health_check(base_url: str) -> bool:
        seen.append(base_url)
        return True

    LlamaCppAdapter().serve(
        "/models/m.gguf",
        port=9000,
        spawn=lambda cmd: FakeProcess(),
        health_check=health_check,
        sleep=lambda s: None,
    )
    assert seen == ["http://localhost:9000"]


def test_serve_times_out_after_retries() -> None:
    sleeps: list[float] = []
    with pytest.raises(TimeoutError):
        LlamaCppAdapter().serve(
            "/models/m.gguf",
            spawn=lambda cmd: FakeProcess(),
            health_check=lambda base_url: False,
            sleep=sleeps.append,
            retries=3,
        )
    # Three health checks, sleeping only between them (not after the last).
    assert len(sleeps) == 2


def test_health_true_on_200_from_health_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "ok"})

    adapter = LlamaCppAdapter(base_url="http://localhost:8080", client=_mock_client(handler))
    assert adapter.health() is True


def test_health_false_on_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    adapter = LlamaCppAdapter(base_url="http://localhost:8080", client=_mock_client(handler))
    assert adapter.health() is False


def test_health_false_on_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    adapter = LlamaCppAdapter(base_url="http://localhost:8080", client=_mock_client(handler))
    assert adapter.health() is False


def test_list_models_returns_served_model_or_empty() -> None:
    assert LlamaCppAdapter().list_models() == []
    served = LlamaCppAdapter()
    served.serve(
        "/models/qwen.gguf",
        spawn=lambda cmd: FakeProcess(),
        health_check=lambda base_url: True,
        sleep=lambda s: None,
    )
    assert served.list_models() == ["/models/qwen.gguf"]


def test_pull_raises_not_implemented_with_guidance() -> None:
    adapter = LlamaCppAdapter()
    with pytest.raises(NotImplementedError) as excinfo:
        adapter.pull("qwen-coder-7b")
    assert "gguf" in str(excinfo.value).lower()


def test_stop_terminates_running_process() -> None:
    proc = FakeProcess()
    adapter = LlamaCppAdapter()
    adapter.serve(
        "/models/m.gguf",
        spawn=lambda cmd: proc,
        health_check=lambda base_url: True,
        sleep=lambda s: None,
    )
    adapter.stop()
    assert proc.terminated is True


def test_stop_is_safe_without_running_process() -> None:
    # Should degrade gracefully (no crash) when nothing is running.
    LlamaCppAdapter().stop()


def test_stop_reaps_process_and_does_not_kill_on_clean_exit() -> None:
    proc = FakeProcess()
    adapter = LlamaCppAdapter()
    adapter.serve(
        "/models/m.gguf",
        spawn=lambda cmd: proc,
        health_check=lambda base_url: True,
        sleep=lambda s: None,
    )
    adapter.stop()
    assert proc.terminated is True
    assert proc.wait_calls >= 1  # reaped, not left a zombie
    assert proc.killed is False  # clean SIGTERM exit needs no SIGKILL


def test_stop_escalates_to_kill_when_terminate_is_ignored() -> None:
    proc = FakeProcess(wedged=True)
    adapter = LlamaCppAdapter()
    adapter.serve(
        "/models/m.gguf",
        spawn=lambda cmd: proc,
        health_check=lambda base_url: True,
        sleep=lambda s: None,
    )
    adapter.stop()
    assert proc.terminated is True
    assert proc.killed is True  # wedged server escalated to SIGKILL
    assert proc.wait_calls >= 2  # waited, timed out, killed, reaped


def test_registered_in_registry() -> None:
    import sip_runtime_llamacpp  # noqa: F401  (import triggers registration)

    adapter = get_adapter("llama.cpp")
    assert isinstance(adapter, LlamaCppAdapter)
    assert adapter.name == "llama.cpp"
