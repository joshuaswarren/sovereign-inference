# sip-pic

Private Inference Credits (PIC): an issuer/mint, a wallet, redemption with
**double-spend prevention**, provider accounting, and an x402 direct-pay path.

**Status:** Phase 3 implemented.

**License:** AGPL-3.0-or-later — see [LICENSING.md](../../LICENSING.md).

## What's here
- `Issuer` — mints issuer-signed bearer vouchers (`sip-ai.voucher.v1`).
- `Wallet` — holds vouchers; `balance()` / `select(amount, unit)`.
- `SpentSet` — persistent, atomic double-spend guard (spend with rollback).
- `redeem_payment` — verify and (on `commit`) consume a payment; **all-or-nothing**
  for PIC batches; `commit=False` enables charge-on-success.
- `x402` — payer-signed, **single-use** (nonce) payments **bound** to one provider
  and request, so a captured payment can't be replayed.
- `Ledger` — provider-side accounting of redeemed value.
- `payment_required` — the HTTP 402 challenge body.

All money math uses `decimal.Decimal`.

## Privacy (honest v1)
A voucher carries no buyer identity, so a provider that redeems it learns nothing
about who bought it (**bearer privacy**). v1 does **not** by itself give
issuer-unlinkability — the issuer sees the same `voucher_id` at issuance and
settlement; the documented upgrade is blind signatures (Chaumian ecash /
Privacy Pass), which keep this same artifact at the redemption boundary. See
[docs/spec/private-inference-credits.md](../../docs/spec/private-inference-credits.md).
