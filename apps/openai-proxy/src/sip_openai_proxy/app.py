# SPDX-License-Identifier: AGPL-3.0-or-later
"""A local OpenAI-compatible HTTP endpoint over the SIP-AI network.

``build_backend`` filters a provider registry through a :class:`sip_policy.Policy`
and wires a :class:`sip_router.SovereignClient`; ``create_proxy_app`` exposes the
familiar OpenAI surface (``/v1/models``, ``/v1/chat/completions`` with streaming)
so any OpenAI client can use the network by pointing its base URL here.

The route, failover, payment, and receipt verification are the real router; this
layer only translates between the OpenAI wire shape and ``SovereignClient.chat``.
"""

from __future__ import annotations

import argparse
import hmac
import json
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

import sip_pic
from sip_policy import Policy
from sip_router import NoProviderAvailable, ProviderEntry, ProviderRegistry, SovereignClient

OWNER = "sovereign-inference"
_DEFAULT_MAX_TOKENS = 512


@dataclass(frozen=True, slots=True)
class ProxyBackend:
    """A policy-filtered routing client plus the models it can serve."""

    client: SovereignClient
    models: list[str]


def build_backend(
    registry: ProviderRegistry,
    *,
    policy: Policy | None = None,
    get_score: Any = None,
    token: str | None = None,
    client_factory: Any = None,
) -> ProxyBackend:
    """Filter ``registry`` by ``policy`` and build the routing client + model list."""
    entries = registry.all()
    if policy is not None:
        entries = policy.filter_entries(entries, get_score=get_score)
    filtered = ProviderRegistry()
    for entry in entries:
        filtered.add(entry)
    models = sorted({m for entry in entries for m in entry.manifest.get("models", [])})
    client = SovereignClient(filtered, token=token, client_factory=client_factory)
    return ProxyBackend(client=client, models=models)


class _ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")  # drop tool_calls/name/tool_call_id
    role: str
    # OpenAI allows content to be a string, null (tool-call turns), or an array of
    # content parts (text/image). Accept all; we route the text.
    content: str | list[dict[str, Any]] | None = None


class _ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")  # tolerate temperature/top_p/etc.
    model: str
    messages: list[_ChatMessage]
    max_tokens: int | None = Field(default=None, ge=1)
    stream: bool = False


def _text_of(content: str | list[dict[str, Any]] | None) -> str:
    """Coerce OpenAI message content (string / null / parts array) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
    return "".join(str(t) for t in parts)


def _completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex}"


def _usage(receipt: dict[str, Any]) -> dict[str, int]:
    prompt = int(receipt.get("input_tokens", 0))
    completion = int(receipt.get("output_tokens", 0))
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion}


def create_proxy_app(
    backend: ProxyBackend,
    *,
    api_key: str | None = None,
    default_max_tokens: int = _DEFAULT_MAX_TOKENS,
    wallet: sip_pic.Wallet | None = None,
) -> FastAPI:
    """Build the OpenAI-compatible FastAPI proxy over ``backend``."""
    app = FastAPI(title="Sovereign Inference — OpenAI-compatible proxy")

    @app.exception_handler(RequestValidationError)
    async def _on_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # Speak the OpenAI error envelope (400) rather than FastAPI's {"detail": …}.
        summary = "; ".join(f"{'/'.join(str(p) for p in e.get('loc', []))}: {e.get('msg', '')}" for e in exc.errors())
        return _error(summary or "invalid request", "invalid_request_error", 400)

    def _authorized(authorization: str | None) -> bool:
        if api_key is None:
            return True
        scheme, _, presented = (authorization or "").partition(" ")
        # Compare as bytes so a non-ASCII token fails closed instead of raising.
        return scheme.lower() == "bearer" and hmac.compare_digest(presented.encode("utf-8"), api_key.encode("utf-8"))

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": "ok", "models": backend.models}

    @app.get("/v1/models")
    def list_models(authorization: Annotated[str | None, Header()] = None) -> JSONResponse:
        if not _authorized(authorization):
            return _error("missing or invalid API key", "unauthorized", 401)
        data = [{"id": m, "object": "model", "created": 0, "owned_by": OWNER} for m in backend.models]
        return JSONResponse({"object": "list", "data": data})

    @app.post("/v1/chat/completions")
    def chat_completions(req: _ChatRequest, authorization: Annotated[str | None, Header()] = None) -> Any:
        if not _authorized(authorization):
            return _error("missing or invalid API key", "unauthorized", 401)
        messages = [{"role": m.role, "content": _text_of(m.content)} for m in req.messages]
        try:
            result = backend.client.chat(
                req.model, messages, max_tokens=req.max_tokens or default_max_tokens, wallet=wallet
            )
        except NoProviderAvailable as exc:
            return _error(f"no provider available for model {req.model!r}: {exc}", "no_provider", 502)

        created = int(time.time())
        completion_id = _completion_id()
        if req.stream:
            return StreamingResponse(
                _sse(completion_id, created, req.model, result.content),
                media_type="text/event-stream",
            )
        return JSONResponse(
            {
                "id": completion_id,
                "object": "chat.completion",
                "created": created,
                "model": req.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": result.content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": _usage(result.receipt),
                "sip": {
                    "provider_pubkey": result.provider_pubkey,
                    "base_url": result.base_url,
                    "receipt_verified": True,
                    "receipt": result.receipt,
                },
            }
        )

    return app


def _error(message: str, kind: str, status: int) -> JSONResponse:
    return JSONResponse({"error": {"message": message, "type": kind}}, status_code=status)


def _sse(completion_id: str, created: int, model: str, content: str) -> Iterator[bytes]:
    """Emit an OpenAI ``chat.completion.chunk`` stream for ``content``.

    The network returns the full completion, so this is buffered streaming (one
    content chunk) — enough for OpenAI streaming clients; true token streaming
    needs provider-side SSE and is future work.
    """

    def chunk(delta: dict[str, Any], finish: str | None) -> bytes:
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
        return f"data: {json.dumps(payload)}\n\n".encode()

    yield chunk({"role": "assistant"}, None)
    yield chunk({"content": content}, None)
    yield chunk({}, "stop")
    yield b"data: [DONE]\n\n"


def run() -> int:  # pragma: no cover - serves until interrupted
    """Console-script entry point: build the proxy from CLI flags and serve it."""
    import uvicorn

    from sip_discovery import FileDirectory

    parser = argparse.ArgumentParser(prog="sip-openai-proxy", description="Local OpenAI-compatible SIP-AI endpoint.")
    parser.add_argument("--registry", help="provider registry JSON (sip_router.ProviderRegistry.load)")
    parser.add_argument("--directory", help="discovery directory JSON to also pull providers from")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11435)
    parser.add_argument("--api-key", help="require this bearer key from clients")
    parser.add_argument("--token", help="bearer token presented to provider gateways")
    parser.add_argument("--require-attestation", action="store_true")
    parser.add_argument("--accepted-tee-type", action="append")
    parser.add_argument("--accepted-unit", action="append")
    parser.add_argument("--max-input-per-1m", type=float)
    parser.add_argument("--max-output-per-1m", type=float)
    parser.add_argument("--required-privacy-mode", action="append")
    args = parser.parse_args()

    registry = ProviderRegistry.load(args.registry) if args.registry else ProviderRegistry()
    if args.directory:
        for provider in FileDirectory(args.directory).discover():
            registry.add(ProviderEntry(base_url=provider.base_url, manifest=provider.manifest))

    policy = Policy(
        require_attestation=args.require_attestation,
        accepted_tee_types=tuple(args.accepted_tee_type or ()),
        accepted_units=tuple(args.accepted_unit or ()),
        max_input_per_1m=args.max_input_per_1m,
        max_output_per_1m=args.max_output_per_1m,
        required_privacy_modes=tuple(args.required_privacy_mode or ()),
    )
    backend = build_backend(registry, policy=policy, token=args.token)
    print(f"Sovereign Inference proxy on http://{args.host}:{args.port}/v1 — models: {backend.models or '(none)'}")
    uvicorn.run(create_proxy_app(backend, api_key=args.api_key), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
