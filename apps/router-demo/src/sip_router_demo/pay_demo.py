# SPDX-License-Identifier: AGPL-3.0-or-later
"""End-to-end Sovereign Inference PAID routing demo.

This wires the *real* :class:`sip_router.SovereignClient` against a *real*
:func:`sip_gateway.create_app` provider gateway running with
``require_payment=True`` — in-process over an httpx ASGI transport (no sockets,
no ports). Only the network boundary is bridged; every other line of business
logic (pricing, PIC voucher verification, the double-spend guard, ledger
accounting, receipt signing, the reactive HTTP 402 flow) is the real thing.

What it proves, end to end:

1. **Paid routing.** A chat request is routed to a paying provider. The client
   hits a 402 challenge, pays the EXACT quoted price with held PIC vouchers, and
   retries — getting back a provider-signed receipt that
   :func:`sip_protocol.verify_receipt` accepts. The wallet is debited and the
   provider's ledger is credited by the same amount.
2. **The reactive 402 -> pay -> 200 flow** happened (printed explicitly).
3. **Double-spend rejection.** An already-redeemed voucher batch, replayed
   against the same :class:`sip_pic.SpentSet`, is REJECTED.

Run it with ``uv run python -m sip_router_demo.pay_demo``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

import sip_pic
import sip_protocol
from sip_gateway import MockAdapter, create_app
from sip_protocol import KeyPair
from sip_router import NoProviderAvailable, ProviderEntry, ProviderRegistry

from .demo import (
    MODEL,
    TOKEN,
    _short,
    _SyncASGITransport,
    build_client,
    sync_client_factory,
)

# Price one input token (word) at 0.01 pic: a W-word prompt costs W * 0.01 pic.
# Setting input_per_1m = 10_000 gives price = (W / 1e6) * 10_000 = W * 0.01.
PRICE_PER_WORD = "0.01"
_INPUT_PER_1M = "10000"
PIC = "pic"

PAID_PROVIDER = "http://paid-provider"
FREE_PROVIDER = "http://free-provider"

# A three-word prompt -> a deterministic price of 3 * 0.01 = 0.03 pic.
DEMO_PROMPT = "explain sovereign inference"
DEMO_MESSAGES: list[dict[str, str]] = [{"role": "user", "content": DEMO_PROMPT}]


def build_paid_gateway_app(
    keypair: KeyPair,
    *,
    issuer: sip_pic.Issuer,
    spent_set: sip_pic.SpentSet | None = None,
    ledger: sip_pic.Ledger | None = None,
    token: str | None = TOKEN,
) -> Any:
    """Build a real provider gateway that REQUIRES PIC payment for completions.

    Prices input tokens so a W-word prompt costs ``W * PRICE_PER_WORD`` pic, and
    accepts only vouchers minted by ``issuer``. A shared ``spent_set`` and
    ``ledger`` can be injected so callers can observe double-spend rejection and
    provider credit across requests.
    """
    return create_app(
        adapter=MockAdapter(),
        keypair=keypair,
        allowed_models=[MODEL],
        token=token,
        require_payment=True,
        pic_issuers=[issuer.pubkey],
        price_units=PIC,
        input_per_1m=_INPUT_PER_1M,
        output_per_1m="0",
        spent_set=spent_set,
        ledger=ledger,
    )


def build_free_gateway_app(keypair: KeyPair, *, token: str | None = TOKEN) -> Any:
    """Build a real provider gateway that serves WITHOUT requiring payment."""
    return create_app(
        adapter=MockAdapter(),
        keypair=keypair,
        allowed_models=[MODEL],
        token=token,
        price_units=PIC,
        input_per_1m=_INPUT_PER_1M,
        output_per_1m="0",
    )


def make_paid_provider_entry(base_url: str, app: Any) -> ProviderEntry:
    """Register a provider by fetching its signed manifest from a running app."""
    client = httpx.Client(transport=_SyncASGITransport(app), base_url=base_url)
    try:
        manifest: dict[str, Any] = client.get("/sip/v1/provider-manifest").json()
    finally:
        client.close()
    return ProviderEntry(base_url=base_url, manifest=manifest)


def mint_wallet(issuer: sip_pic.Issuer, *, count: int = 5) -> sip_pic.Wallet:
    """Mint ``count`` fresh ``PRICE_PER_WORD``-pic vouchers into a new wallet."""
    wallet = sip_pic.Wallet()
    wallet.add(*issuer.issue(PRICE_PER_WORD, count=count))
    return wallet


def main() -> int:
    """Run the paid-routing demo, printing each proof step. Returns 0 on success."""
    print("=== Sovereign Inference: PAID routing demo ===")
    print(f"model: {MODEL}")
    print(f"prompt: {DEMO_PROMPT!r}  (3 words @ {PRICE_PER_WORD} pic/word)")

    # --- mint credits and stand up a payment-required gateway ------------------
    issuer = sip_pic.Issuer(KeyPair.generate(), unit=PIC)
    provider_kp = KeyPair.generate()
    ledger = sip_pic.Ledger()
    spent_set = sip_pic.SpentSet()
    app = build_paid_gateway_app(provider_kp, issuer=issuer, spent_set=spent_set, ledger=ledger)

    wallet = mint_wallet(issuer)
    print(f"issuer:   {_short_str(issuer.pubkey)}  (minted 5 x {PRICE_PER_WORD} pic)")
    print(f"provider: {_short(provider_kp)}  (require_payment=True)")

    registry = ProviderRegistry()
    registry.add(make_paid_provider_entry(PAID_PROVIDER, app))

    # --- (1) route a paid request ---------------------------------------------
    print("\n--- routing a PAID request (reactive 402 -> pay -> 200) ---")
    balance_before = wallet.balance(PIC)
    print(f"wallet balance before: {balance_before} pic")

    client = build_client(registry, sync_client_factory({PAID_PROVIDER: app}))
    try:
        result = client.chat(MODEL, DEMO_MESSAGES, wallet=wallet)
    except NoProviderAvailable as exc:  # pragma: no cover — defensive; provider is up.
        print(f"ERROR: no provider available: {exc}")
        return 1

    served_by = "paid-provider" if result.base_url == PAID_PROVIDER else result.base_url
    print(f"served by: {result.base_url} ({served_by})")
    print(f"response: {result.content!r}")
    if not sip_protocol.verify_receipt(result.receipt).valid:
        print("ERROR: receipt failed verification")
        return 1
    print("receipt verified: OK (signature + schema valid)")

    balance_after = wallet.balance(PIC)
    debited = balance_before - balance_after
    print(f"wallet balance after:  {balance_after} pic  (debited {debited} pic)")
    ledger_balance = ledger.balance(provider_kp.public_key_str, PIC)
    print(f"provider ledger balance: {ledger_balance} pic  (credited)")
    if debited <= 0 or ledger_balance != debited:
        print("ERROR: wallet/ledger did not balance")
        return 1

    # --- (2) demonstrate the HTTP 402 -> pay -> 200 reactive flow --------------
    print("\n--- reactive payment flow that just happened ---")
    print("client -> POST /v1/chat/completions  (no payment)")
    print("gateway <- HTTP 402 payment required (challenge carries exact price)")
    print(f"client -> POST /v1/chat/completions  (sip_payment: {debited} pic in PIC vouchers)")
    print("gateway <- HTTP 200 + signed receipt")

    # --- (3) double-spend: replay an already-redeemed voucher batch -----------
    print("\n--- double-spend guard ---")
    voucher_batch = issuer.issue(str(debited), count=1)
    payment = sip_pic.build_pic_payment(voucher_batch)
    fresh_spent = sip_pic.SpentSet()
    first = sip_pic.redeem_payment(
        payment,
        price=str(debited),
        unit=PIC,
        issuer_pubkeys=[issuer.pubkey],
        spent_set=fresh_spent,
        now=_utc_now(),
    )
    print(f"first redemption:  ok={first.ok} total={first.total} reason={first.reason!r}")
    second = sip_pic.redeem_payment(
        payment,
        price=str(debited),
        unit=PIC,
        issuer_pubkeys=[issuer.pubkey],
        spent_set=fresh_spent,
        now=_utc_now(),
    )
    print(f"replay redemption: ok={second.ok} reason={second.reason!r}  -> REJECTED (double-spend)")
    if first.ok is not True or second.ok is not False or second.reason != "double_spend":
        print("ERROR: double-spend guard did not behave as expected")
        return 1

    print("\n=== demo complete: paid, verified, debited/credited, and double-spend blocked ===")
    return 0


def _short_str(pubkey: str) -> str:
    """A short, human-readable prefix of a pubkey string for log lines."""
    return pubkey[:18] + "..."


def _utc_now() -> datetime:
    """The wall clock used to redeem the double-spend demonstration vouchers."""
    return datetime.now(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
