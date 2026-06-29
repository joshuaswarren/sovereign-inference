# SPDX-License-Identifier: AGPL-3.0-or-later
"""End-to-end proof of Phase 3: paid routing across a real paying gateway.

These tests wire the *real* :class:`sip_router.SovereignClient` against a *real*
:func:`sip_gateway.create_app` gateway with ``require_payment=True`` over an
in-process httpx ASGI transport (no sockets, no ports). Only the network
boundary is bridged — the gateway runs its real auth, pricing, payment
redemption (real ``sip_pic`` voucher verification + double-spend guard), and
receipt-signing code, and the client runs its real resolution, reactive HTTP
402 -> pay -> 200 flow, and receipt verification.

What is proven, end to end:

* A paid request returns a provider-signed, verifiable receipt; the wallet is
  debited and the provider ledger is credited by the same amount.
* A voucher redeemed once cannot be redeemed again: a second redemption against
  the same shared :class:`sip_pic.SpentSet` is rejected as a double-spend, and a
  client re-presenting an already-spent voucher batch is 402'd by the gateway.
* A client with no wallet against a paying gateway fails over to a free provider
  (or raises :class:`NoProviderAvailable` when none can serve it).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

import sip_pic
import sip_protocol
from sip_protocol import KeyPair
from sip_router import NoProviderAvailable, ProviderRegistry, SovereignClient
from sip_router_demo.demo import (
    MODEL,
    TOKEN,
    build_client,
    down_client_factory,
    sync_client_factory,
)
from sip_router_demo.pay_demo import (
    PRICE_PER_WORD,
    build_free_gateway_app,
    build_paid_gateway_app,
    main,
    make_paid_provider_entry,
    mint_wallet,
)

# A three-word prompt -> billed_input == 3 words -> price == 3 * PRICE_PER_WORD.
PROMPT = "explain sovereign inference"
MESSAGES = [{"role": "user", "content": PROMPT}]
EXPECTED_PRICE = str(Decimal(PRICE_PER_WORD) * 3)  # "0.03"
PIC = "pic"

PAID_URL = "http://paid-provider"
FREE_URL = "http://free-provider"


def _now() -> datetime:
    return datetime.now(UTC)


def test_paid_request_succeeds_and_debits_wallet_credits_ledger() -> None:
    """A paid route returns a verified receipt; wallet down, ledger up by price."""
    provider_kp = KeyPair.generate()
    issuer = sip_pic.Issuer(KeyPair.generate(), unit=PIC)
    ledger = sip_pic.Ledger()
    app = build_paid_gateway_app(provider_kp, issuer=issuer, ledger=ledger)

    wallet = mint_wallet(issuer)  # five 0.01-pic vouchers -> 0.05 pic held.
    before = wallet.balance(PIC)

    registry = ProviderRegistry()
    registry.add(make_paid_provider_entry(PAID_URL, app))
    client = build_client(registry, sync_client_factory({PAID_URL: app}))

    result = client.chat(MODEL, MESSAGES, wallet=wallet)

    # A real, provider-signed receipt that the frozen protocol accepts.
    assert result.base_url == PAID_URL
    assert result.content == f"echo: {PROMPT}"
    assert sip_protocol.verify_receipt(result.receipt).valid is True
    assert result.receipt["provider_pubkey"] == provider_kp.public_key_str

    # The reactive 402 -> pay -> 200 flow happened on the same provider.
    assert result.attempts[-1]["outcome"] == "ok"

    # Wallet debited by exactly the price; ledger credited by exactly the price.
    after = wallet.balance(PIC)
    assert after < before
    assert before - after == Decimal(EXPECTED_PRICE)
    assert ledger.balance(provider_kp.public_key_str, PIC) == Decimal(EXPECTED_PRICE)
    assert ledger.total(PIC) == Decimal(EXPECTED_PRICE)


def test_double_spend_is_rejected_end_to_end() -> None:
    """A voucher spent via a real gateway redemption cannot be redeemed again."""
    provider_kp = KeyPair.generate()
    issuer = sip_pic.Issuer(KeyPair.generate(), unit=PIC)
    spent_set = sip_pic.SpentSet()  # shared by the gateway and the replay below.
    ledger = sip_pic.Ledger()
    app = build_paid_gateway_app(provider_kp, issuer=issuer, spent_set=spent_set, ledger=ledger)

    registry = ProviderRegistry()
    registry.add(make_paid_provider_entry(PAID_URL, app))

    # Build the exact voucher batch that will pay for one request, and keep a
    # copy so we can replay the *same* vouchers after the gateway consumes them.
    voucher_batch = issuer.issue(EXPECTED_PRICE, count=1)
    payment = sip_pic.build_pic_payment(list(voucher_batch))
    wallet = sip_pic.Wallet(list(voucher_batch))

    client = build_client(registry, sync_client_factory({PAID_URL: app}))
    result = client.chat(MODEL, MESSAGES, wallet=wallet)
    assert result.base_url == PAID_URL
    assert sip_protocol.verify_receipt(result.receipt).valid is True

    # The voucher really was consumed by the gateway's shared spent-set.
    voucher_id = voucher_batch[0]["voucher_id"]
    assert spent_set.is_spent(voucher_id) is True

    # 1) Direct re-redemption of the same batch against the same spent-set fails.
    replay = sip_pic.redeem_payment(
        payment,
        price=EXPECTED_PRICE,
        unit=PIC,
        issuer_pubkeys=[issuer.pubkey],
        spent_set=spent_set,
        now=_now(),
    )
    assert replay.ok is False
    assert replay.reason == "double_spend"

    # 2) Re-presenting the same voucher batch to the gateway is 402'd.
    factory = sync_client_factory({PAID_URL: app})
    http = factory(PAID_URL)
    try:
        resp = http.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {TOKEN}", "X-SIP-Request-Id": "replay"},
            json={"model": MODEL, "messages": MESSAGES, "max_tokens": 16, "sip_payment": payment},
        )
    finally:
        http.close()
    assert resp.status_code == 402
    assert resp.json()["error"] == "payment required"

    # The ledger was credited exactly once (the rejected replay added nothing).
    assert ledger.total(PIC) == Decimal(EXPECTED_PRICE)


def test_unpaid_request_against_paying_gateway_fails_over() -> None:
    """A wallet-less client against a paying gateway fails over to a free one."""
    paid_kp = KeyPair.generate()
    free_kp = KeyPair.generate()
    issuer = sip_pic.Issuer(KeyPair.generate(), unit=PIC)
    paid_app = build_paid_gateway_app(paid_kp, issuer=issuer)
    free_app = build_free_gateway_app(free_kp)

    # Register the free provider from its OWN app manifest so its price matches
    # the paid one — the two then tie on score and the stable rank preserves
    # registration order, guaranteeing the paid provider is tried first.
    registry = ProviderRegistry()
    registry.add(make_paid_provider_entry(PAID_URL, paid_app))
    registry.add(make_paid_provider_entry(FREE_URL, free_app))
    apps: dict[str, object] = {PAID_URL: paid_app, FREE_URL: free_app}

    # No wallet, no x402 keypair: the paying provider cannot be paid -> fail over.
    client = build_client(registry, sync_client_factory(apps))
    result = client.chat(MODEL, MESSAGES)

    assert result.base_url == FREE_URL
    assert result.content == f"echo: {PROMPT}"
    assert sip_protocol.verify_receipt(result.receipt).valid is True
    assert result.attempts[0]["base_url"] == PAID_URL
    assert result.attempts[0]["outcome"] == "payment_required"


def test_no_provider_available_when_only_paying_and_unpayable() -> None:
    """With only an unpayable paying provider and no wallet, the client raises."""
    paid_kp = KeyPair.generate()
    issuer = sip_pic.Issuer(KeyPair.generate(), unit=PIC)
    paid_app = build_paid_gateway_app(paid_kp, issuer=issuer)

    registry = ProviderRegistry()
    registry.add(make_paid_provider_entry(PAID_URL, paid_app))
    client = build_client(registry, sync_client_factory({PAID_URL: paid_app}))

    with pytest.raises(NoProviderAvailable):
        client.chat(MODEL, MESSAGES)


def test_failover_factory_skips_down_paid_provider() -> None:
    """A funded client still fails over when the paid provider is hard-down."""
    paid_kp = KeyPair.generate()
    free_kp = KeyPair.generate()
    issuer = sip_pic.Issuer(KeyPair.generate(), unit=PIC)
    paid_app = build_paid_gateway_app(paid_kp, issuer=issuer)
    free_app = build_free_gateway_app(free_kp)

    registry = ProviderRegistry()
    registry.add(make_paid_provider_entry(PAID_URL, paid_app))
    registry.add(make_paid_provider_entry(FREE_URL, free_app))
    apps: dict[str, object] = {PAID_URL: paid_app, FREE_URL: free_app}

    wallet = mint_wallet(issuer)
    factory = down_client_factory(apps, down={PAID_URL})
    client = build_client(registry, factory)
    result = client.chat(MODEL, MESSAGES, wallet=wallet)

    assert result.base_url == FREE_URL
    assert result.attempts[0]["outcome"] != "ok"
    # No vouchers were spent against the down provider.
    assert wallet.balance(PIC) == Decimal(PRICE_PER_WORD) * 5


def test_main_runs_and_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """The demo proves the paid flow, debit/credit, 402 reactive flow, double-spend."""
    exit_code = main()
    out = capsys.readouterr().out.lower()

    assert exit_code == 0
    assert "served by" in out
    assert "receipt verified" in out
    assert "wallet balance" in out
    assert "ledger" in out
    assert "402" in out
    assert "double-spend" in out or "double spend" in out
    assert "rejected" in out


def test_demo_helpers_share_the_sync_transport() -> None:
    """The paid demo reuses the demo's in-process ASGI bridge (no real sockets)."""
    paid_kp = KeyPair.generate()
    issuer = sip_pic.Issuer(KeyPair.generate(), unit=PIC)
    app = build_paid_gateway_app(paid_kp, issuer=issuer)
    factory = sync_client_factory({PAID_URL: app})
    http = factory(PAID_URL)
    try:
        health = http.get("/sip/v1/health")
    finally:
        http.close()
    assert isinstance(http, httpx.Client)
    assert health.status_code == 200
    assert health.json()["provider_pubkey"] == paid_kp.public_key_str


def test_client_constructs_from_registry() -> None:
    """A SovereignClient builds against the paid registry with the demo token."""
    paid_kp = KeyPair.generate()
    issuer = sip_pic.Issuer(KeyPair.generate(), unit=PIC)
    app = build_paid_gateway_app(paid_kp, issuer=issuer)
    registry = ProviderRegistry()
    registry.add(make_paid_provider_entry(PAID_URL, app))
    client = build_client(registry, sync_client_factory({PAID_URL: app}))
    assert isinstance(client, SovereignClient)
