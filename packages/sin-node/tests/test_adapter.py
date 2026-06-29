# SPDX-License-Identifier: AGPL-3.0-or-later
import httpx
import pytest

from sin_node.adapter import AdapterRegistry, OpenAICompatibleAdapter, RuntimeAdapter
from sin_node.models import ChatResult


def _adapter(handler) -> OpenAICompatibleAdapter:
    return OpenAICompatibleAdapter("http://x", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_base_chat_delegates_to_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
        )

    res = _adapter(handler).chat("m", [{"role": "user", "content": "hi"}])
    assert isinstance(res, ChatResult)
    assert res.content == "ok"


def test_base_health_true_on_2xx() -> None:
    assert _adapter(lambda r: httpx.Response(200, json={"data": []})).health() is True


def test_base_health_false_on_5xx() -> None:
    assert _adapter(lambda r: httpx.Response(503)).health() is False


def test_registry_register_get_and_names() -> None:
    reg = AdapterRegistry()
    reg.register("fake", lambda base="http://y": OpenAICompatibleAdapter(base))
    assert reg.names() == ["fake"]
    got = reg.get("fake")
    assert isinstance(got, OpenAICompatibleAdapter)


def test_registry_unknown_name_raises() -> None:
    reg = AdapterRegistry()
    with pytest.raises(KeyError):
        reg.get("nope")


def test_complete_adapter_satisfies_runtime_protocol() -> None:
    class Dummy:
        name = "dummy"

        def detect(self): ...
        def is_available(self) -> bool:
            return True

        def list_models(self) -> list[str]:
            return []

        def pull(self, model: str) -> None: ...
        def serve(self, model: str, **kwargs): ...
        def chat(self, model, messages, **kwargs): ...
        def health(self) -> bool:
            return True

        def stop(self) -> None: ...

    assert isinstance(Dummy(), RuntimeAdapter)
