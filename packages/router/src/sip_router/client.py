# SPDX-License-Identifier: AGPL-3.0-or-later
"""SovereignClient — the SIP-AI routing client SDK.

The client resolves a model id to ranked providers, then walks them in order:
health check -> optional signed quote -> OpenAI-compatible completion. It fails
over to the next provider on transport errors, server/rate-limit responses, or
an unverifiable receipt, and returns a :class:`RouteResult` from the first
provider that serves a trustworthy response.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from sip_protocol import verify_quote, verify_receipt

from .errors import NoProviderAvailable
from .models import ProviderEntry, RouteResult
from .registry import ProviderRegistry
from .resolver import resolve

_DEFAULT_TIMEOUT = 10.0


def _default_client_factory(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=_DEFAULT_TIMEOUT)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SovereignClient:
    """Route chat completions across SIP-AI providers with failover.

    Only the network boundary is configurable (``client_factory``), so the
    client is straightforward to test against fake gateways.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        *,
        token: str | None = None,
        client_factory: Callable[[str], httpx.Client] | None = None,
        now: Callable[[], datetime] = _utc_now,
        request_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._registry = registry
        self._token = token
        self._client_factory = client_factory or _default_client_factory
        self._now = now
        self._request_id_factory = request_id_factory or (lambda: f"req-{uuid4().hex}")

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 256,
        privacy_mode: str = "direct",
        verify_receipts: bool = True,
        get_quote: bool = False,
        max_providers: int | None = None,
        weights: dict[str, float] | None = None,
    ) -> RouteResult:
        """Send ``messages`` to the best available provider serving ``model``.

        Raises :class:`NoProviderAvailable` if every candidate fails (or none
        serve the model). ``attempts`` on the result/exception records each
        provider tried and why it was skipped.
        """
        candidates = resolve(self._registry, model, privacy_mode=privacy_mode, weights=weights)
        if max_providers is not None:
            candidates = candidates[:max_providers]

        request_id = self._request_id_factory()
        attempts: list[dict[str, Any]] = []

        for candidate in candidates:
            outcome = self._try_candidate(
                candidate,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                privacy_mode=privacy_mode,
                verify_receipts=verify_receipts,
                get_quote=get_quote,
                request_id=request_id,
            )
            attempts.append({"base_url": candidate.base_url, "outcome": outcome.label})
            if outcome.result is not None:
                return RouteResult(
                    content=outcome.result.content,
                    receipt=outcome.result.receipt,
                    provider_pubkey=candidate.manifest["provider_pubkey"],
                    base_url=candidate.base_url,
                    quote=outcome.result.quote,
                    attempts=attempts,
                )

        raise NoProviderAvailable(model, attempts)

    def _try_candidate(
        self,
        candidate: ProviderEntry,
        *,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        privacy_mode: str,
        verify_receipts: bool,
        get_quote: bool,
        request_id: str,
    ) -> _Attempt:
        client = self._client_factory(candidate.base_url)
        try:
            return self._serve(
                client,
                candidate,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                privacy_mode=privacy_mode,
                verify_receipts=verify_receipts,
                get_quote=get_quote,
                request_id=request_id,
            )
        except (httpx.TransportError, httpx.HTTPError) as exc:
            return _Attempt(label=f"transport_error: {type(exc).__name__}")
        finally:
            client.close()

    def _serve(
        self,
        client: httpx.Client,
        candidate: ProviderEntry,
        *,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        privacy_mode: str,
        verify_receipts: bool,
        get_quote: bool,
        request_id: str,
    ) -> _Attempt:
        if not self._health_ok(client):
            return _Attempt(label="unhealthy")

        quote: dict[str, Any] | None = None
        if get_quote:
            quote = self._fetch_quote(
                client, model=model, max_tokens=max_tokens, privacy_mode=privacy_mode, request_id=request_id
            )
            if quote is None:
                return _Attempt(label="quote_invalid")

        response = client.post(
            "/v1/chat/completions",
            headers=self._completion_headers(request_id=request_id, privacy_mode=privacy_mode),
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
        )
        if response.status_code >= 500 or response.status_code == 429:
            return _Attempt(label=f"http_{response.status_code}")
        if response.status_code != 200:
            return _Attempt(label=f"http_{response.status_code}")

        body = response.json()
        content = _extract_content(body)
        if content is None:
            return _Attempt(label="malformed_response")

        receipt = body.get("sip_receipt")
        if verify_receipts and not self._receipt_trusted(receipt, candidate):
            return _Attempt(label="receipt_unverified")

        return _Attempt(result=_Served(content=content, receipt=receipt or {}, quote=quote))

    def _health_ok(self, client: httpx.Client) -> bool:
        response = client.get("/sip/v1/health")
        if response.status_code != 200:
            return False
        body = response.json()
        return bool(body.get("status") == "ok")

    def _fetch_quote(
        self,
        client: httpx.Client,
        *,
        model: str,
        max_tokens: int,
        privacy_mode: str,
        request_id: str,
    ) -> dict[str, Any] | None:
        headers = {}
        if self._token is not None:
            headers["Authorization"] = f"Bearer {self._token}"
        response = client.post(
            "/sip/v1/quote",
            headers=headers,
            json={
                "request_id": request_id,
                "model": model,
                "max_output_tokens": max_tokens,
                "privacy_mode": privacy_mode,
            },
        )
        if response.status_code != 200:
            return None
        quote: dict[str, Any] = response.json()
        if not isinstance(quote, dict) or not verify_quote(quote).valid:
            return None
        return quote

    def _completion_headers(self, *, request_id: str, privacy_mode: str) -> dict[str, str]:
        headers = {
            "X-SIP-Request-Id": request_id,
            "X-SIP-Privacy-Mode": privacy_mode,
        }
        if self._token is not None:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    @staticmethod
    def _receipt_trusted(receipt: Any, candidate: ProviderEntry) -> bool:
        if not isinstance(receipt, dict):
            return False
        if not verify_receipt(receipt).valid:
            return False
        expected = candidate.manifest.get("provider_pubkey")
        return receipt.get("provider_pubkey") == expected


class _Served:
    """A trustworthy served response from one provider."""

    __slots__ = ("content", "quote", "receipt")

    def __init__(self, *, content: str, receipt: dict[str, Any], quote: dict[str, Any] | None) -> None:
        self.content = content
        self.receipt = receipt
        self.quote = quote


class _Attempt:
    """The outcome of trying one candidate: a served result or a failure label."""

    __slots__ = ("label", "result")

    def __init__(self, *, label: str = "ok", result: _Served | None = None) -> None:
        self.result = result
        self.label = "ok" if result is not None else label


def _extract_content(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content if isinstance(content, str) else None
