# SPDX-License-Identifier: AGPL-3.0-or-later
"""Client helper for routing an inference request through a privacy relay.

:func:`relay_chat` posts a completion to a relay, then — because the relay is
untrusted — verifies the provider's signed receipt and checks that the receipt's
``response_hash`` matches the returned content. A relay that tampered with the
answer (or substituted a different receipt) is detected: ``verified`` is False.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from sip_protocol import hash_request, hash_response_body, verify_receipt


@dataclass(frozen=True, slots=True)
class RelayResult:
    """The outcome of a relayed completion."""

    content: str
    receipt: dict[str, Any]
    status_code: int
    verified: bool


def _content_of(payload: dict[str, Any]) -> str:
    try:
        return str(payload["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError):
        return ""


def relay_chat(
    relay_client: httpx.Client,
    *,
    target: dict[str, Any],
    completion: dict[str, Any],
    verify_receipts: bool = True,
) -> RelayResult:
    """Route ``completion`` to ``target`` through ``relay_client`` and verify the receipt."""
    response = relay_client.post("/sip/v1/relay", json={"target": target, "completion": completion})
    raw_payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    content = _content_of(payload)
    raw_receipt = payload.get("sip_receipt")
    receipt: dict[str, Any] = raw_receipt if isinstance(raw_receipt, dict) else {}

    verified = False
    if verify_receipts and receipt:
        signature_ok = bool(verify_receipt(receipt).valid)
        response_ok = receipt.get("response_hash") == hash_response_body(content.encode("utf-8"))
        # Bind the receipt to THIS request: a relay can't substitute a genuine
        # receipt+answer from a different prompt (its request_hash won't match).
        expected_request = hash_request(completion.get("model", ""), completion.get("messages", []))
        request_ok = receipt.get("request_hash") == expected_request
        verified = signature_ok and response_ok and request_ok

    return RelayResult(content=content, receipt=receipt, status_code=response.status_code, verified=verified)
