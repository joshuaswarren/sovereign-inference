# SPDX-License-Identifier: AGPL-3.0-or-later
"""A deterministic, network-free runtime adapter for tests and local demos.

:class:`MockAdapter` implements the minimal slice of the ``sin_node``
``RuntimeAdapter`` surface the gateway needs — a ``name`` attribute and a
``chat`` method returning a :class:`sin_node.models.ChatResult`. It echoes the
last user message and reports rough word-count token usage, so receipts and
usage blocks are populated without ever touching a real model server.
"""

from __future__ import annotations

from typing import Any

from sin_node.models import ChatResult


def _word_count(text: str) -> int:
    return len(text.split())


class MockAdapter:
    """Echoing adapter: ``content = "echo: " + last user message``.

    ``name`` is set to a receipt-schema-valid runtime so receipts built with
    ``runtime = adapter.name`` validate against ``sip-ai.receipt.v1``.
    """

    name = "llama.cpp"

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 256,
        **_kwargs: Any,
    ) -> ChatResult:
        last_user = ""
        for message in messages:
            if message.get("role") == "user":
                last_user = message.get("content", "")
        reply = f"echo: {last_user}"
        input_tokens = sum(_word_count(m.get("content", "")) for m in messages)
        output_tokens = _word_count(reply)
        return ChatResult(
            content=reply,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
        )
