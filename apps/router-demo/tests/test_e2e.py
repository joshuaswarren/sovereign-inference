# SPDX-License-Identifier: AGPL-3.0-or-later
"""End-to-end proof of Phase 2: a real router routing across real gateways.

These tests wire the *real* :class:`sip_router.SovereignClient` against two
*real* :func:`sip_gateway.create_app` ASGI apps over an in-process httpx
transport (no sockets, no ports). Only the network boundary is faked — the
gateways run their real auth, quota, receipt-signing code, and the client runs
its real resolution, failover, and receipt-verification logic.
"""

from __future__ import annotations

import pytest

import sip_protocol
from sip_protocol import KeyPair
from sip_router import NoProviderAvailable, ProviderRegistry, SovereignClient
from sip_router_demo.demo import (
    MODEL,
    build_client,
    build_gateway_app,
    down_client_factory,
    make_provider_entry,
    sync_client_factory,
)

MESSAGES = [{"role": "user", "content": "What is sovereign inference?"}]


def _two_provider_setup() -> tuple[KeyPair, KeyPair, dict[str, object], SovereignClient]:
    """Stand up provider A and provider B as real gateways behind one client."""
    kp_a = KeyPair.generate()
    kp_b = KeyPair.generate()
    app_a = build_gateway_app(kp_a)
    app_b = build_gateway_app(kp_b)
    apps: dict[str, object] = {"http://provider-a": app_a, "http://provider-b": app_b}

    registry = ProviderRegistry()
    registry.add(make_provider_entry("http://provider-a", kp_a))
    registry.add(make_provider_entry("http://provider-b", kp_b))

    client = build_client(registry, sync_client_factory(apps))
    return kp_a, kp_b, apps, client


def test_routes_and_returns_verified_receipt() -> None:
    kp_a, _kp_b, _apps, client = _two_provider_setup()

    result = client.chat(MODEL, MESSAGES)

    # A real, non-empty completion came back.
    assert result.content
    assert isinstance(result.content, str)

    # The receipt is genuinely signed and verifiable via the frozen protocol.
    verification = sip_protocol.verify_receipt(result.receipt)
    assert verification.valid is True

    # It was served by the top-ranked provider (A, first registered), and the
    # advertised pubkey matches the serving gateway's key.
    assert result.provider_pubkey == kp_a.public_key_str
    assert result.receipt["provider_pubkey"] == kp_a.public_key_str
    assert result.base_url == "http://provider-a"


def test_fails_over_when_first_provider_unhealthy() -> None:
    kp_a, kp_b, apps, _client = _two_provider_setup()
    registry = ProviderRegistry()
    registry.add(make_provider_entry("http://provider-a", kp_a))
    registry.add(make_provider_entry("http://provider-b", kp_b))

    # Provider A goes down: every route returns 503, so the router skips it.
    factory = down_client_factory(apps, down={"http://provider-a"})
    client = build_client(registry, factory)

    result = client.chat(MODEL, MESSAGES)

    # The request still succeeds — served by the *other* provider, B.
    assert result.content
    assert result.base_url == "http://provider-b"
    assert result.provider_pubkey == kp_b.public_key_str
    assert sip_protocol.verify_receipt(result.receipt).valid is True

    # Failover is recorded: A was tried first and failed, B served the request.
    assert [a["base_url"] for a in result.attempts] == [
        "http://provider-a",
        "http://provider-b",
    ]
    assert result.attempts[0]["outcome"] != "ok"
    assert result.attempts[-1]["outcome"] == "ok"


def test_raises_when_all_providers_fail() -> None:
    kp_a, kp_b, apps, _client = _two_provider_setup()
    registry = ProviderRegistry()
    registry.add(make_provider_entry("http://provider-a", kp_a))
    registry.add(make_provider_entry("http://provider-b", kp_b))

    # Both providers are down.
    factory = down_client_factory(apps, down={"http://provider-a", "http://provider-b"})
    client = build_client(registry, factory)

    with pytest.raises(NoProviderAvailable) as excinfo:
        client.chat(MODEL, MESSAGES)

    assert {a["base_url"] for a in excinfo.value.attempts} == {
        "http://provider-a",
        "http://provider-b",
    }


def test_main_runs_and_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    from sip_router_demo.demo import main

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    # The demo proves both the happy path and failover, with a verified receipt.
    assert "provider-a" in captured.out
    assert "provider-b" in captured.out
    assert "FAILED OVER" in captured.out
    assert "receipt verified" in captured.out.lower()
