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
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

import httpx

import sip_pic
from sip_protocol import KeyPair, hash_response_body, quote_is_expired, verify_quote, verify_receipt

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
        wallet: sip_pic.Wallet | None = None,
        x402_keypair: KeyPair | None = None,
    ) -> RouteResult:
        """Send ``messages`` to the best available provider serving ``model``.

        Raises :class:`NoProviderAvailable` if every candidate fails (or none
        serve the model). ``attempts`` on the result/exception records each
        provider tried and why it was skipped.

        When a provider answers a completion with HTTP 402 (payment required),
        the client pays the exact quoted price and retries that same provider
        once: with ``wallet`` it spends held PIC vouchers, or with
        ``x402_keypair`` it signs an x402 payment. A provider that cannot be
        paid (no matching scheme, insufficient funds, or a rejected paid retry)
        fails over to the next candidate, and any PIC vouchers reserved for a
        rejected batch are returned to the wallet.
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
                wallet=wallet,
                x402_keypair=x402_keypair,
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
        wallet: sip_pic.Wallet | None,
        x402_keypair: KeyPair | None,
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
                wallet=wallet,
                x402_keypair=x402_keypair,
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
        wallet: sip_pic.Wallet | None,
        x402_keypair: KeyPair | None,
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

        headers = self._completion_headers(request_id=request_id, privacy_mode=privacy_mode)
        response = self._post_completion(client, headers, model=model, messages=messages, max_tokens=max_tokens)

        # Reactive 402: pay the exact quoted price and retry the SAME provider once.
        reserved: list[dict[str, Any]] | None = None
        if response.status_code == 402:
            attempt, payment, reserved = self._prepare_payment(response, wallet=wallet, x402_keypair=x402_keypair)
            if attempt is not None:
                return attempt
            response = self._post_completion(
                client, headers, model=model, messages=messages, max_tokens=max_tokens, payment=payment
            )

        if response.status_code >= 500 or response.status_code == 429:
            return self._payment_failover("payment_rejected", reserved, wallet, response.status_code)
        if response.status_code != 200:
            return self._payment_failover("payment_rejected", reserved, wallet, response.status_code)

        body = _safe_json(response)
        content = _extract_content(body)
        if content is None:
            return self._payment_failover("payment_rejected", reserved, wallet, "malformed_response")

        receipt = body.get("sip_receipt") if isinstance(body, dict) else None
        if verify_receipts and not self._receipt_trusted(receipt, candidate, content):
            return self._payment_failover("payment_rejected", reserved, wallet, "receipt_unverified")

        if quote is not None and not self._quote_honored(quote, receipt, candidate):
            return self._payment_failover("payment_rejected", reserved, wallet, "quote_violated")

        return _Attempt(result=_Served(content=content, receipt=receipt or {}, quote=quote))

    def _post_completion(
        self,
        client: httpx.Client,
        headers: dict[str, str],
        *,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        payment: dict[str, Any] | None = None,
    ) -> httpx.Response:
        body: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if payment is not None:
            body["sip_payment"] = payment
        return client.post("/v1/chat/completions", headers=headers, json=body)

    def _prepare_payment(
        self,
        response: httpx.Response,
        *,
        wallet: sip_pic.Wallet | None,
        x402_keypair: KeyPair | None,
    ) -> tuple[_Attempt | None, dict[str, Any] | None, list[dict[str, Any]] | None]:
        """Build a payment for a 402 challenge, or a failover attempt if unpayable.

        Returns ``(attempt, payment, reserved)``: exactly one of ``attempt`` (the
        provider cannot be paid -> fail over) or ``payment`` (retry the provider)
        is set. ``reserved`` holds any PIC vouchers removed from the wallet so the
        caller can return them if the paid retry is rejected.
        """
        body = _safe_json(response)
        challenge = body.get("sip_payment_required") if isinstance(body, dict) else None
        if not isinstance(challenge, dict):
            return _Attempt(label="payment_required"), None, None
        price = str(challenge.get("price_amount"))
        unit = str(challenge.get("price_units"))
        accepted = challenge.get("accepted_schemes")
        accepted = accepted if isinstance(accepted, list) else []

        if wallet is not None and "pic" in accepted:
            try:
                vouchers = wallet.select(price, unit)
            except sip_pic.InsufficientFunds:
                return _Attempt(label="insufficient_funds"), None, None
            return None, sip_pic.build_pic_payment(vouchers), vouchers

        if x402_keypair is not None and "x402" in accepted:
            payment = sip_pic.build_x402_payment(payer_keypair=x402_keypair, amount=price, unit=unit, now=self._now)
            return None, payment, None

        return _Attempt(label="payment_required"), None, None

    @staticmethod
    def _payment_failover(
        label: str,
        reserved: list[dict[str, Any]] | None,
        wallet: sip_pic.Wallet | None,
        detail: object,
    ) -> _Attempt:
        """Fail over after a completion error, returning reserved PIC vouchers.

        When no payment was made (``reserved is None``) this is the pre-existing
        failover path, labeled by the HTTP/parse ``detail`` exactly as before.
        """
        if reserved is None:
            return _Attempt(label=f"http_{detail}" if isinstance(detail, int) else str(detail))
        if wallet is not None:
            wallet.add(*reserved)
        return _Attempt(label=label)

    def _health_ok(self, client: httpx.Client) -> bool:
        response = client.get("/sip/v1/health")
        if response.status_code != 200:
            return False
        body = _safe_json(response)
        return isinstance(body, dict) and body.get("status") == "ok"

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
        quote = _safe_json(response)
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
    def _receipt_trusted(receipt: Any, candidate: ProviderEntry, content: str) -> bool:
        if not isinstance(receipt, dict):
            return False
        if not verify_receipt(receipt).valid:
            return False
        if receipt.get("provider_pubkey") != candidate.manifest.get("provider_pubkey"):
            return False
        # Bind the receipt to the response body we actually received: a valid,
        # correctly-keyed receipt over some *other* answer must not be trusted.
        return receipt.get("response_hash") == hash_response_body(content)

    def _quote_honored(self, quote: dict[str, Any], receipt: Any, candidate: ProviderEntry) -> bool:
        """A provider must honor the quote it signed: same provider, not expired,
        and the receipt price must not exceed the committed ``max_price``."""
        if quote.get("provider_pubkey") != candidate.manifest.get("provider_pubkey"):
            return False
        if quote_is_expired(quote, self._now()):
            return False
        if not isinstance(receipt, dict) or receipt.get("price_units") != quote.get("price_units"):
            return False
        try:
            charged = Decimal(str(receipt.get("price_amount")))
            committed = Decimal(str(quote.get("max_price")))
        except (InvalidOperation, TypeError):
            return False
        return charged <= committed


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


def _safe_json(response: httpx.Response) -> Any:
    """Parse a response body as JSON, returning None on a malformed body.

    A provider that returns HTTP 200 with a non-JSON body must be skipped so the
    router fails over — ``response.json()`` raises ``json.JSONDecodeError`` (a
    ``ValueError``), which the transport-error failover catch would otherwise miss.
    """
    try:
        return response.json()
    except ValueError:
        return None


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
