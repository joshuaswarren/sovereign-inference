# SPDX-License-Identifier: Apache-2.0
"""Behavioral tests for the Ollama runtime adapter.

External calls (httpx + ``shutil.which``) are injected, so these tests never
touch a real Ollama install or the network. HTTP is faked with
``httpx.MockTransport``.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from sip_runtime_ollama.adapter import DEFAULT_BASE_URL, OllamaAdapter


def make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url=DEFAULT_BASE_URL)


def test_name_and_default_base_url() -> None:
    adapter = OllamaAdapter()
    assert adapter.name == "ollama"
    assert adapter.base_url == "http://localhost:11434"


def test_detect_available_via_which() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/version"
        return httpx.Response(200, json={"version": "0.5.7"})

    adapter = OllamaAdapter(client=make_client(handler), which=lambda _: "/usr/local/bin/ollama")
    info = adapter.detect()

    assert info.name == "ollama"
    assert info.available is True
    assert info.version == "0.5.7"
    assert info.endpoint == "http://localhost:11434"


def test_detect_available_via_version_endpoint_without_binary() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": "0.6.0"})

    # which() returns None (no binary on PATH) but the API answers -> available.
    adapter = OllamaAdapter(client=make_client(handler), which=lambda _: None)
    info = adapter.detect()

    assert info.available is True
    assert info.version == "0.6.0"


def test_detect_unavailable_when_no_binary_and_endpoint_down() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    adapter = OllamaAdapter(client=make_client(handler), which=lambda _: None)
    info = adapter.detect()

    assert info.available is False
    assert info.version is None
    assert info.endpoint == "http://localhost:11434"


def test_is_available_true_when_endpoint_responds() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": "0.5.7"})

    adapter = OllamaAdapter(client=make_client(handler), which=lambda _: None)
    assert adapter.is_available() is True


def test_is_available_false_on_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope", request=request)

    adapter = OllamaAdapter(client=make_client(handler), which=lambda _: None)
    assert adapter.is_available() is False


def test_list_models_parses_tags() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "llama3.2:latest", "size": 123},
                    {"name": "qwen2.5-coder:7b", "size": 456},
                ]
            },
        )

    adapter = OllamaAdapter(client=make_client(handler))
    assert adapter.list_models() == ["llama3.2:latest", "qwen2.5-coder:7b"]


def test_list_models_empty_on_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    adapter = OllamaAdapter(client=make_client(handler))
    assert adapter.list_models() == []


def test_list_models_empty_on_missing_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    adapter = OllamaAdapter(client=make_client(handler))
    assert adapter.list_models() == []


def test_pull_consumes_stream() -> None:
    posted: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/pull"
        posted["body"] = json.loads(request.content)
        lines = [
            json.dumps({"status": "pulling manifest"}),
            json.dumps({"status": "downloading", "completed": 50, "total": 100}),
            json.dumps({"status": "success"}),
        ]
        return httpx.Response(200, content=("\n".join(lines) + "\n").encode())

    adapter = OllamaAdapter(client=make_client(handler))
    adapter.pull("llama3.2:latest")  # should complete without raising

    assert posted["body"] == {"name": "llama3.2:latest", "stream": True}


def test_pull_degrades_on_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    adapter = OllamaAdapter(client=make_client(handler))
    # Pull must never crash the caller on a transport failure.
    adapter.pull("llama3.2:latest")


def test_serve_returns_handle_when_reachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": "0.5.7"})

    adapter = OllamaAdapter(client=make_client(handler), which=lambda _: None)
    handle = adapter.serve("llama3.2:latest")

    assert handle.base_url == "http://localhost:11434"
    assert handle.runtime == "ollama"
    assert handle.pid is None


def test_serve_raises_when_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    adapter = OllamaAdapter(client=make_client(handler), which=lambda _: None)
    with pytest.raises(RuntimeError):
        adapter.serve("llama3.2:latest")


def test_stop_is_noop() -> None:
    adapter = OllamaAdapter(client=make_client(lambda r: httpx.Response(200)))
    assert adapter.stop() is None


def test_chat_uses_v1_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello there"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    adapter = OllamaAdapter(client=make_client(handler))
    result = adapter.chat("llama3.2:latest", [{"role": "user", "content": "hi"}])

    assert result.content == "hello there"
    assert result.input_tokens == 3
    assert result.output_tokens == 2
    assert result.model == "llama3.2:latest"


def test_importing_package_registers_ollama() -> None:
    import sip_runtime_ollama  # noqa: F401  (import triggers registration)

    from sin_node.adapter import available_adapter_names, get_adapter

    assert "ollama" in available_adapter_names()
    built = get_adapter("ollama")
    assert isinstance(built, OllamaAdapter)
    assert built.name == "ollama"
