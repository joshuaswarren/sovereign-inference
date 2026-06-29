# SPDX-License-Identifier: AGPL-3.0-or-later
"""The provider gateway HTTP app.

A hardened front door for a model runtime. It speaks the SIP-AI wire contract:

* ``GET  /sip/v1/health``            — liveness + advertised models (no auth).
* ``GET  /sip/v1/provider-manifest`` — the signed provider manifest (no auth).
* ``POST /sip/v1/quote``             — a signed price commitment for one request.
* ``POST /v1/chat/completions``      — OpenAI-compatible inference + signed receipt.

Auth, the model allowlist, output/input size caps, and a simple in-memory rate
limiter are enforced before the runtime is ever called. Every served response
carries a provider-signed receipt so a client can later audit what it paid for.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, TypeGuard

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from sin_node.models import ChatResult
from sip_protocol import (
    KeyPair,
    build_quote,
    build_receipt,
    hash_response_body,
    sign_provider_manifest,
    sign_quote,
    sign_receipt,
)

DEFAULT_MODEL_MANIFEST_HASH = "sha256:" + "0" * 64
DEFAULT_PRIVACY_MODE = "direct"


class Adapter(Protocol):
    """The minimal runtime-adapter surface the gateway depends on."""

    name: str

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = ...,
        **kwargs: Any,
    ) -> ChatResult: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_amount(value: float) -> str:
    """Render a rounded price as a plain decimal string (no exponent, no junk).

    ``"0"`` stays ``"0"``; ``2.5`` becomes ``"2.5"``; ``3.0`` becomes ``"3"``.
    The result always matches the receipt/quote ``^[0-9]+(\\.[0-9]+)?$`` pattern.
    """
    rounded = round(value, 6)
    text = f"{rounded:.6f}".rstrip("0").rstrip(".")
    return text or "0"


class _RateLimiter:
    """A simple in-memory sliding-window limiter keyed off an injected clock."""

    def __init__(self, limit: int, clock: Callable[[], float]) -> None:
        self._limit = limit
        self._clock = clock
        self._hits: deque[float] = deque()

    def allow(self) -> bool:
        now = self._clock()
        window_start = now - 60.0
        while self._hits and self._hits[0] <= window_start:
            self._hits.popleft()
        if len(self._hits) >= self._limit:
            return False
        self._hits.append(now)
        return True


def _synthesize_manifest(
    *,
    keypair: KeyPair,
    allowed_models: list[str],
    adapter_name: str,
    price_units: str,
    input_per_1m: str,
    output_per_1m: str,
    max_context: int,
    logging_policy: str,
    now: Callable[[], datetime],
) -> dict[str, Any]:
    """Build a minimal signed provider manifest from the gateway config."""
    manifest: dict[str, Any] = {
        "schema": "sip-ai.provider_manifest.v1",
        "provider_pubkey": keypair.public_key_str,
        "node_type": "sovereign-node",
        "models": list(allowed_models),
        "runtime_adapters": [adapter_name],
        "pricing": {
            "unit": price_units,
            "input_per_1m": float(input_per_1m),
            "output_per_1m": float(output_per_1m),
        },
        "max_context": max_context,
        "logging_policy": logging_policy,
        "privacy_modes": [DEFAULT_PRIVACY_MODE],
        "published_at": now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return sign_provider_manifest(manifest, keypair)


def create_app(
    *,
    adapter: Adapter,
    keypair: KeyPair,
    allowed_models: list[str],
    token: str | None = None,
    max_output_tokens: int = 512,
    max_input_chars: int = 100_000,
    rate_limit_per_minute: int | None = None,
    logging_policy: str = "no_prompt_logging",
    model_manifest_hash: str = DEFAULT_MODEL_MANIFEST_HASH,
    price_units: str = "test",
    input_per_1m: str = "0",
    output_per_1m: str = "0",
    provider_manifest: dict[str, Any] | None = None,
    clock: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] = _utc_now,
) -> FastAPI:
    """Build and return the configured provider-gateway :class:`FastAPI` app."""
    allowed = list(allowed_models)
    manifest = provider_manifest or _synthesize_manifest(
        keypair=keypair,
        allowed_models=allowed,
        adapter_name=adapter.name,
        price_units=price_units,
        input_per_1m=input_per_1m,
        output_per_1m=output_per_1m,
        max_context=max_input_chars,
        logging_policy=logging_policy,
        now=now,
    )
    limiter = (
        _RateLimiter(rate_limit_per_minute, clock)
        if rate_limit_per_minute is not None
        else None
    )

    app = FastAPI(title="SIP-AI Provider Gateway")

    def _auth_ok(request: Request) -> bool:
        if token is None:
            return True
        header = request.headers.get("authorization", "")
        scheme, _, presented = header.partition(" ")
        return scheme.lower() == "bearer" and presented == token

    def _price_amount(input_tokens: int, output_tokens: int) -> str:
        amount = (input_tokens / 1e6) * float(input_per_1m) + (
            output_tokens / 1e6
        ) * float(output_per_1m)
        return _format_amount(amount)

    @app.get("/sip/v1/health")
    def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "provider_pubkey": keypair.public_key_str,
                "models": allowed,
            }
        )

    @app.get("/sip/v1/provider-manifest")
    def provider_manifest_endpoint() -> JSONResponse:
        return JSONResponse(manifest)

    @app.post("/sip/v1/quote")
    async def quote(request: Request) -> JSONResponse:
        if not _auth_ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({"error": "malformed JSON"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "body must be an object"}, status_code=400)

        request_id = body.get("request_id")
        model = body.get("model")
        max_out = body.get("max_output_tokens")
        privacy_mode = body.get("privacy_mode")
        if (
            not isinstance(request_id, str)
            or not isinstance(model, str)
            or not isinstance(max_out, int)
            or isinstance(max_out, bool)
            or max_out < 1
        ):
            return JSONResponse({"error": "missing or invalid fields"}, status_code=400)
        if model not in allowed:
            return JSONResponse({"error": "unknown model"}, status_code=404)

        issued = now()
        max_price = _price_amount(0, max_out)
        unsigned = build_quote(
            request_id=request_id,
            provider_pubkey=keypair.public_key_str,
            model_alias=model,
            price_units=price_units,
            input_per_1m=input_per_1m,
            output_per_1m=output_per_1m,
            max_output_tokens=max_out,
            max_price=max_price,
            issued_at=issued,
            expires_at=issued + timedelta(minutes=5),
            privacy_mode=privacy_mode if isinstance(privacy_mode, str) else None,
        )
        return JSONResponse(sign_quote(unsigned, keypair))

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> JSONResponse:
        # 1. auth
        if not _auth_ok(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({"error": "malformed JSON"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "body must be an object"}, status_code=400)

        model = body.get("model")
        messages = body.get("messages")
        if not isinstance(model, str) or not _valid_messages(messages):
            return JSONResponse({"error": "missing or invalid fields"}, status_code=400)
        max_tokens = body.get("max_tokens", 256)
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 1:
            return JSONResponse({"error": "invalid max_tokens"}, status_code=400)

        # 2. model allowlist
        if model not in allowed:
            return JSONResponse({"error": "unknown model"}, status_code=404)

        # 3. output token cap
        if max_tokens > max_output_tokens:
            return JSONResponse(
                {"error": "max_tokens exceeds gateway cap"}, status_code=413
            )

        # 4. input size cap
        total_chars = sum(len(m["content"]) for m in messages)
        if total_chars > max_input_chars:
            return JSONResponse({"error": "input too large"}, status_code=413)

        # 5. rate limit
        if limiter is not None and not limiter.allow():
            return JSONResponse({"error": "rate limited"}, status_code=429)

        privacy_mode = request.headers.get("x-sip-privacy-mode", DEFAULT_PRIVACY_MODE)
        request_id = request.headers.get("x-sip-request-id", "anon")

        # 6. serve
        started = now()
        result = adapter.chat(model, messages, max_tokens=max_tokens)
        completed = now()

        receipt = sign_receipt(
            build_receipt(
                request_id=request_id,
                provider_pubkey=keypair.public_key_str,
                model_manifest_hash=model_manifest_hash,
                model_alias=model,
                runtime=adapter.name,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                price_units=price_units,
                price_amount=_price_amount(result.input_tokens, result.output_tokens),
                privacy_mode=privacy_mode,
                started_at=started,
                completed_at=completed,
                response_hash=hash_response_body(result.content),
            ),
            keypair,
        )

        total = result.input_tokens + result.output_tokens
        return JSONResponse(
            {
                "id": f"chatcmpl-{request_id}",
                "object": "chat.completion",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": result.content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": result.input_tokens,
                    "completion_tokens": result.output_tokens,
                    "total_tokens": total,
                },
                "sip_receipt": receipt,
            }
        )

    return app


def _valid_messages(messages: Any) -> TypeGuard[list[dict[str, str]]]:
    """True if ``messages`` is a non-empty list of {role, content} string maps."""
    if not isinstance(messages, list) or not messages:
        return False
    return all(
        isinstance(m, dict)
        and isinstance(m.get("role"), str)
        and isinstance(m.get("content"), str)
        for m in messages
    )


def serve(app: FastAPI, host: str = "127.0.0.1", port: int = 8090) -> None:  # pragma: no cover
    """Run ``app`` with uvicorn (not exercised by the test suite)."""
    import uvicorn

    uvicorn.run(app, host=host, port=port)
