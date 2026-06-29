# SPDX-License-Identifier: AGPL-3.0-or-later
import json

import httpx
import pytest

from sin_node.http import chat, stream_chat
from sin_node.models import ChatResult


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_chat_parses_content_and_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "m"
        assert body["stream"] is False
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": "hi there"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            },
        )

    res = chat("http://x", "m", [{"role": "user", "content": "hi"}], client=_client(handler))
    assert isinstance(res, ChatResult)
    assert res.content == "hi there"
    assert res.input_tokens == 5
    assert res.output_tokens == 2


def test_chat_raises_on_server_error() -> None:
    res = _client(lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(httpx.HTTPStatusError):
        chat("http://x", "m", [{"role": "user", "content": "hi"}], client=res)


def test_stream_chat_computes_ttft_and_tps() -> None:
    sse = "".join(
        [
            'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n',
            'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n',
            'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":3,"completion_tokens":20}}\n\n',
            "data: [DONE]\n\n",
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["stream"] is True
        return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})

    clock_values = iter([0.0, 0.5, 2.5])  # start, first-content-token, end
    stats = stream_chat(
        "http://x",
        "m",
        [{"role": "user", "content": "hi"}],
        client=_client(handler),
        clock=lambda: next(clock_values),
    )
    assert stats.content == "Hello world"
    assert stats.ttft_s == pytest.approx(0.5)
    assert stats.output_tokens == 20
    # tps = output_tokens / (end - first_token) = 20 / (2.5 - 0.5)
    assert stats.tokens_per_second == pytest.approx(10.0)


def test_stream_chat_counts_chunks_when_usage_absent() -> None:
    sse = "".join(
        [
            'data: {"choices":[{"delta":{"content":"a"}}]}\n\n',
            'data: {"choices":[{"delta":{"content":"b"}}]}\n\n',
            'data: {"choices":[{"delta":{"content":"c"}}]}\n\n',
            "data: [DONE]\n\n",
        ]
    )
    clock_values = iter([0.0, 1.0, 4.0])
    stats = stream_chat(
        "http://x",
        "m",
        [{"role": "user", "content": "hi"}],
        client=_client(lambda r: httpx.Response(200, text=sse)),
        clock=lambda: next(clock_values),
    )
    assert stats.output_tokens == 3  # fell back to counting content chunks
