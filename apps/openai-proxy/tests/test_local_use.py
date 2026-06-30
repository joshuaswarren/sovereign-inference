# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for using a local model as a verified provider (the 'as simple as Ollama' path).

A locally fronted model runs through the *real* provider gateway in-process, so
even local inference yields a signed, verified receipt — no loopback socket, no
background server, no port to race on.
"""

from __future__ import annotations

from sip_gateway import MockAdapter
from sip_openai_proxy.local_use import (
    LocalProvider,
    RuntimeStatus,
    detect_runtimes,
    front_local_model,
)
from sip_router import ProviderRegistry, SovereignClient, in_process_client

MODEL = "qwen-coder-7b"


class _FakeAdapter:
    def __init__(self, name: str, *, available: bool, models: list[str], boom: bool = False) -> None:
        self.name = name
        self._available = available
        self._models = models
        self._boom = boom

    def is_available(self) -> bool:
        if self._boom:
            raise RuntimeError("daemon down")
        return self._available

    def list_models(self) -> list[str]:
        return list(self._models)


# -- detect_runtimes ------------------------------------------------------------


def test_detect_runtimes_reports_availability_and_models() -> None:
    adapters = [
        _FakeAdapter("ollama", available=True, models=["llama3.1:8b", "qwen2.5-coder:7b"]),
        _FakeAdapter("llama.cpp", available=False, models=[]),
    ]
    statuses = detect_runtimes(adapters=adapters)
    by_name = {s.name: s for s in statuses}
    assert by_name["ollama"] == RuntimeStatus(name="ollama", available=True, models=("llama3.1:8b", "qwen2.5-coder:7b"))
    assert by_name["llama.cpp"].available is False
    assert by_name["llama.cpp"].models == ()


def test_detect_runtimes_survives_a_throwing_adapter() -> None:
    statuses = detect_runtimes(adapters=[_FakeAdapter("ollama", available=True, models=["x"], boom=True)])
    assert statuses[0] == RuntimeStatus(name="ollama", available=False, models=())


# -- front_local_model ----------------------------------------------------------


def test_front_local_model_returns_a_trusted_entry_bound_to_its_signed_uri() -> None:
    local = front_local_model(MODEL, adapter=MockAdapter())
    assert isinstance(local, LocalProvider)
    assert local.model == MODEL
    assert local.runtime == "llama.cpp"
    # routes to the signed manifest_uri, and the entry is internally consistent
    assert local.entry.base_url == local.entry.manifest["manifest_uri"]
    assert MODEL in local.entry.manifest["models"]


def test_front_local_model_routes_in_process_with_a_verified_receipt() -> None:
    local = front_local_model(MODEL, adapter=MockAdapter())
    registry = ProviderRegistry()
    registry.add(local.entry)
    client = SovereignClient(registry, client_factory=lambda base_url: in_process_client(local.app, base_url))

    result = client.chat(MODEL, [{"role": "user", "content": "hello"}])

    assert "echo: hello" in result.content
    assert result.provider_pubkey == local.entry.manifest["provider_pubkey"]
    # a verified signed receipt rode along (SovereignClient verifies before returning)
    assert result.receipt["provider_pubkey"] == local.entry.manifest["provider_pubkey"]
