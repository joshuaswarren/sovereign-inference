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
from sip_runtime_ollama.adapter import DEFAULT_BASE_URL, OllamaAdapter, OllamaPullError, _pull_client


def make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url=DEFAULT_BASE_URL)


def test_pull_client_has_finite_read_timeout() -> None:
    # The production pull path (no injected client) must NOT disable the read
    # timeout, or a stalled stream would hang `sin install` forever.
    client = _pull_client()
    try:
        assert client.timeout.read is not None
        assert client.timeout.connect is not None
    finally:
        client.close()


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


def _ndjson(*objects: dict[str, object]) -> bytes:
    return ("".join(json.dumps(o) + "\n" for o in objects)).encode()


def _pull_handler(
    pull: Callable[[httpx.Request], httpx.Response],
    installed: list[str],
) -> Callable[[httpx.Request], httpx.Response]:
    """Route ``/api/pull`` to ``pull`` and answer ``/api/tags`` with ``installed``."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": name} for name in installed]})
        assert request.url.path == "/api/pull"
        return pull(request)

    return handler


def test_pull_succeeds_when_stream_ok_and_model_in_tags() -> None:
    posted: dict[str, object] = {}

    def pull(request: httpx.Request) -> httpx.Response:
        posted["body"] = json.loads(request.content)
        body = _ndjson(
            {"status": "pulling manifest"},
            {"status": "downloading", "completed": 50, "total": 100},
            {"status": "success"},
        )
        return httpx.Response(200, content=body)

    adapter = OllamaAdapter(client=make_client(_pull_handler(pull, ["llama3.2:latest"])))
    adapter.pull("llama3.2:latest")  # should complete without raising

    assert posted["body"] == {"name": "llama3.2:latest", "stream": True}


def test_pull_matches_bare_name_against_latest_tag() -> None:
    def pull(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_ndjson({"status": "success"}))

    adapter = OllamaAdapter(client=make_client(_pull_handler(pull, ["llama3.2:latest"])))
    adapter.pull("llama3.2")  # Ollama stores a bare name under ":latest"


def test_pull_raises_on_http_404() -> None:
    def pull(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "pull model manifest: file does not exist"})

    adapter = OllamaAdapter(client=make_client(_pull_handler(pull, [])))
    with pytest.raises(OllamaPullError) as exc:
        adapter.pull("definitely-not-a-real-model")

    assert exc.value.model == "definitely-not-a-real-model"
    assert "404" in str(exc.value)
    assert "file does not exist" in str(exc.value)


def test_pull_raises_on_http_error_without_json_body() -> None:
    def pull(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"internal error")

    adapter = OllamaAdapter(client=make_client(_pull_handler(pull, [])))
    with pytest.raises(OllamaPullError, match="HTTP 500"):
        adapter.pull("llama3.2:latest")


def test_pull_raises_on_http_error_with_json_body_lacking_error() -> None:
    def pull(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"detail": "bad gateway"})

    adapter = OllamaAdapter(client=make_client(_pull_handler(pull, [])))
    with pytest.raises(OllamaPullError) as exc:
        adapter.pull("llama3.2:latest")

    assert exc.value.reason == "HTTP 502 from /api/pull"


def test_pull_raises_on_stream_error_object() -> None:
    def pull(request: httpx.Request) -> httpx.Response:
        body = _ndjson(
            {"status": "pulling manifest"},
            {"error": "pull model manifest: file does not exist"},
        )
        return httpx.Response(200, content=body)

    # Even if the tags list somehow has the name, an in-band error wins.
    adapter = OllamaAdapter(client=make_client(_pull_handler(pull, ["llama3.2:latest"])))
    with pytest.raises(OllamaPullError, match="file does not exist"):
        adapter.pull("llama3.2:latest")


def test_pull_ignores_non_json_stream_lines() -> None:
    def pull(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json\n\n" + _ndjson({"status": "success"}))

    adapter = OllamaAdapter(client=make_client(_pull_handler(pull, ["llama3.2:latest"])))
    adapter.pull("llama3.2:latest")


def test_pull_raises_on_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    adapter = OllamaAdapter(client=make_client(handler))
    with pytest.raises(OllamaPullError, match="offline") as exc:
        adapter.pull("llama3.2:latest")

    assert isinstance(exc.value.__cause__, httpx.ConnectError)


def test_pull_raises_when_model_absent_from_tags() -> None:
    def pull(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_ndjson({"status": "success"}))

    adapter = OllamaAdapter(client=make_client(_pull_handler(pull, [])))
    with pytest.raises(OllamaPullError, match="not present in /api/tags"):
        adapter.pull("llama3.2:latest")


def test_pull_error_is_exported_from_package() -> None:
    import sip_runtime_ollama

    assert sip_runtime_ollama.OllamaPullError is OllamaPullError
    assert issubclass(OllamaPullError, RuntimeError)


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
