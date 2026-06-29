# SPDX-License-Identifier: AGPL-3.0-or-later
"""Behavioral tests for the provider gateway.

These exercise the four WIRE CONTRACT endpoints end-to-end against a real
``FastAPI`` app driven by ``TestClient``, using a deterministic ``MockAdapter``
and a freshly generated provider ``KeyPair``. The only thing mocked is the
model runtime boundary (the adapter); signing, schema validation, and HTTP
routing are all real.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sip_protocol import (
    KeyPair,
    hash_response_body,
    verify_provider_manifest,
    verify_quote,
    verify_receipt,
)

from sip_gateway import MockAdapter, create_app

ALLOWED = ["echo-model", "echo-model-2"]


@pytest.fixture
def keypair() -> KeyPair:
    return KeyPair.generate()


def make_client(keypair: KeyPair, **kwargs: object) -> TestClient:
    app = create_app(
        adapter=MockAdapter(),
        keypair=keypair,
        allowed_models=ALLOWED,
        **kwargs,  # type: ignore[arg-type]
    )
    return TestClient(app)


# --------------------------------------------------------------------------- #
# MockAdapter
# --------------------------------------------------------------------------- #
def test_mock_adapter_echoes_last_user_message() -> None:
    adapter = MockAdapter()
    result = adapter.chat(
        "echo-model",
        [
            {"role": "system", "content": "be nice"},
            {"role": "user", "content": "hello there friend"},
        ],
        max_tokens=64,
    )
    assert result.content == "echo: hello there friend"
    assert result.input_tokens > 0
    assert result.output_tokens > 0
    assert adapter.name in {
        "llama.cpp",
        "ollama",
        "vllm",
        "sglang",
        "localai",
        "lmstudio",
        "ramalama",
    }


# --------------------------------------------------------------------------- #
# /sip/v1/health
# --------------------------------------------------------------------------- #
def test_health_shape(keypair: KeyPair) -> None:
    client = make_client(keypair)
    resp = client.get("/sip/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["provider_pubkey"] == keypair.public_key_str
    assert body["models"] == ALLOWED


# --------------------------------------------------------------------------- #
# /sip/v1/provider-manifest
# --------------------------------------------------------------------------- #
def test_provider_manifest_verifies(keypair: KeyPair) -> None:
    client = make_client(keypair)
    resp = client.get("/sip/v1/provider-manifest")
    assert resp.status_code == 200
    manifest = resp.json()
    assert manifest["schema"] == "sip-ai.provider_manifest.v1"
    assert manifest["provider_pubkey"] == keypair.public_key_str
    assert verify_provider_manifest(manifest) is True


# --------------------------------------------------------------------------- #
# /sip/v1/quote
# --------------------------------------------------------------------------- #
def test_quote_is_signed_and_verifies(keypair: KeyPair) -> None:
    client = make_client(keypair)
    resp = client.post(
        "/sip/v1/quote",
        json={"request_id": "req-1", "model": "echo-model", "max_output_tokens": 128},
    )
    assert resp.status_code == 200
    quote = resp.json()
    assert quote["quote_version"] == "sip-ai.quote.v1"
    assert quote["model_alias"] == "echo-model"
    assert quote["max_output_tokens"] == 128
    assert verify_quote(quote).valid is True


def test_quote_requires_token_when_configured(keypair: KeyPair) -> None:
    client = make_client(keypair, token="s3cret")
    resp = client.post(
        "/sip/v1/quote",
        json={"request_id": "req-1", "model": "echo-model", "max_output_tokens": 16},
    )
    assert resp.status_code == 401


def test_quote_accepts_valid_token(keypair: KeyPair) -> None:
    client = make_client(keypair, token="s3cret")
    resp = client.post(
        "/sip/v1/quote",
        headers={"Authorization": "Bearer s3cret"},
        json={"request_id": "req-1", "model": "echo-model", "max_output_tokens": 16},
    )
    assert resp.status_code == 200
    assert verify_quote(resp.json()).valid is True


def test_quote_unknown_model_404(keypair: KeyPair) -> None:
    client = make_client(keypair)
    resp = client.post(
        "/sip/v1/quote",
        json={"request_id": "req-1", "model": "nope", "max_output_tokens": 16},
    )
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# /v1/chat/completions
# --------------------------------------------------------------------------- #
def test_chat_happy_path_returns_valid_receipt(keypair: KeyPair) -> None:
    client = make_client(keypair)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "echo-model",
            "messages": [{"role": "user", "content": "ping pong"}],
            "max_tokens": 64,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "echo-model"
    content = body["choices"][0]["message"]["content"]
    assert content == "echo: ping pong"
    assert body["choices"][0]["finish_reason"] == "stop"
    usage = body["usage"]
    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]

    receipt = body["sip_receipt"]
    result = verify_receipt(receipt)
    assert result.valid is True, result.errors
    assert receipt["provider_pubkey"] == keypair.public_key_str
    assert receipt["model_alias"] == "echo-model"
    assert receipt["response_hash"] == hash_response_body(content)


def test_chat_wrong_token_401(keypair: KeyPair) -> None:
    client = make_client(keypair, token="s3cret")
    resp = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer WRONG"},
        json={"model": "echo-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


def test_chat_missing_token_401(keypair: KeyPair) -> None:
    client = make_client(keypair, token="s3cret")
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "echo-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


def test_chat_unknown_model_404(keypair: KeyPair) -> None:
    client = make_client(keypair)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "ghost", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 404


def test_chat_max_tokens_over_cap_413(keypair: KeyPair) -> None:
    client = make_client(keypair, max_output_tokens=32)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "echo-model",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 9999,
        },
    )
    assert resp.status_code == 413


def test_chat_input_too_large_413(keypair: KeyPair) -> None:
    client = make_client(keypair, max_input_chars=5)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "echo-model",
            "messages": [{"role": "user", "content": "this is far too long"}],
            "max_tokens": 16,
        },
    )
    assert resp.status_code == 413


def test_chat_rate_limited_429(keypair: KeyPair) -> None:
    ticks: Iterator[float] = iter([0.0, 1.0, 2.0, 3.0, 4.0])

    def clock() -> float:
        return next(ticks)

    client = make_client(keypair, rate_limit_per_minute=1, clock=clock)
    payload = {
        "model": "echo-model",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 16,
    }
    first = client.post("/v1/chat/completions", json=payload)
    assert first.status_code == 200
    second = client.post("/v1/chat/completions", json=payload)
    assert second.status_code == 429


def test_chat_malformed_json_400(keypair: KeyPair) -> None:
    client = make_client(keypair)
    resp = client.post(
        "/v1/chat/completions",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400


def test_chat_missing_fields_400(keypair: KeyPair) -> None:
    client = make_client(keypair)
    resp = client.post("/v1/chat/completions", json={"messages": []})
    assert resp.status_code == 400


def test_receipt_price_is_zero_when_prices_zero(keypair: KeyPair) -> None:
    client = make_client(keypair)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "echo-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    receipt = resp.json()["sip_receipt"]
    assert receipt["price_amount"] == "0"
    assert receipt["price_units"] == "test"


def test_receipt_price_computed_from_per_1m(keypair: KeyPair) -> None:
    client = make_client(keypair, input_per_1m="1000000", output_per_1m="2000000")
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "echo-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    receipt = resp.json()["sip_receipt"]
    # With 1.0/1M input and 2.0/1M output priced at 1e6 and 2e6 per 1M,
    # price == input_tokens + 2*output_tokens (as a whole number).
    expected = float(receipt["input_tokens"]) + 2.0 * float(receipt["output_tokens"])
    assert float(receipt["price_amount"]) == pytest.approx(expected)


def test_now_is_injectable_for_deterministic_timestamps(keypair: KeyPair) -> None:
    fixed = datetime(2026, 6, 29, 12, 0, 0, tzinfo=UTC)
    client = make_client(keypair, now=lambda: fixed)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "echo-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    receipt = resp.json()["sip_receipt"]
    assert receipt["started_at"] == "2026-06-29T12:00:00Z"
    assert receipt["completed_at"] == "2026-06-29T12:00:00Z"
