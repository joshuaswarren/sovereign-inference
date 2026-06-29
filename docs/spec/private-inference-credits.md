# Private Inference Credits (PIC)

Private Inference Credits are the privacy-preserving payment primitive of SIP-AI. They let a user pay for inference without directly linking the provider request to the original wallet purchase. This document explains the v1 concept, the requirements, the inspiration, and the explicit upgrade path from a first implementable voucher step to real Chaumian-ecash / Privacy-Pass cryptography.

> **Terminology:** SIP-AI = Sovereign Inference Protocol; SIN = Sovereign Inference Node; PIC = Private Inference Credits.

## Why PIC exists

SIP-AI supports two payment paths. Direct **x402** is excellent for simple API monetization because it uses the existing HTTP 402 Payment Required pattern [S5, S6]. But direct on-chain payments can link wallet, provider, request timing, and usage together. **Private Inference Credits reduce that linkage by separating credit purchase from credit redemption** — the act of buying credits and the act of spending them on a request are not tied to the same observable identity.

## The privacy boundary

The core privacy claim is precise and bounded: PICs separate the **credit issuance identity** (who bought the bundle) from the **provider redemption metadata** (what was spent on a given request). A provider verifies that a voucher is valid and unspent **without learning which wallet bought it**.

What PIC does and does not claim:

- **Does:** reduce linkability between wallet purchase and individual inference requests; make the privacy claim explicit and measurable in docs (PIC-FR-006).
- **Does not:** claim perfect anonymity, claim traffic is undetectable or unblockable, or claim PIC alone hides network-level metadata. Transport-level metadata is addressed separately by transport modes (see [transport-modes.md](transport-modes.md)). PIC's guarantee is about **reduced linkability** at the payment layer, layered with other resilience measures.

## PIC v1 concept flow

1. User buys a bundle of inference credits from an issuer or mint.
2. The issuer returns blinded or otherwise unlinkable bearer vouchers.
3. The client stores vouchers locally.
4. When making an inference request, the client redeems one or more vouchers with the provider gateway.
5. The provider verifies that the voucher is valid and unspent without learning which wallet bought it.
6. The provider later settles redeemed vouchers with the issuer or settlement layer.

```text
Issuer / mint  --(blinded vouchers)-->  Client (stores locally)
Client  --(redeem voucher)-->  Provider gateway  (verifies valid + unspent)
Provider  --(settle redeemed vouchers)-->  Issuer / settlement layer
```

The two sides of the boundary — purchase at the issuer and redemption at the provider — are deliberately kept unlinkable.

## Inspiration: Cashu and Privacy Pass

PIC draws inspiration from two well-studied systems:

- **Cashu** — an open-source Chaumian ecash protocol using digital bearer tokens stored on the user device [S30]. This informs the blinded-bearer-voucher model where the mint cannot link issuance to redemption.
- **Privacy Pass** — a privacy-preserving token architecture (RFC 9576) involving clients, origins, issuers, and attesters [S31]. This informs the separation of roles and the unlinkable redemption pattern.

## The upgrade path: first implementable voucher step to real cryptographic credits

We are building PIC for real, and we are honest about sequencing. The first implementable milestone is a **voucher system** that demonstrates the architecture and the privacy boundary end to end — issuance, local storage, redemption, double-spend prevention, and settlement — without cryptographic overreach in the first step. This first step is explicitly designed with a **defined upgrade path to real Chaumian-ecash / Privacy-Pass cryptographic redemption** [S30, S31].

Concretely:

- **First step:** a voucher service that issues, redeems, prevents double spend, supports expiry/denomination, and shows aggregate settlement — with the privacy boundary made explicit and measurable in docs.
- **Upgrade path:** replace the voucher mechanism with blinded-token cryptography (Chaumian ecash as in Cashu, or Privacy Pass-style tokens), so the unlinkability between purchase and redemption is enforced cryptographically rather than by service design.

This is the first milestone of a real, production-bound payment primitive — not a throwaway. Nothing here is claimed as finished; the cryptographic version is the destination and the voucher step is the implementable starting point.

## PIC v1 requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| PIC-FR-001 | Issue test credits to a client wallet. | P0 |
| PIC-FR-002 | Redeem credits with a provider without exposing the original purchase ID to the provider. | P1 |
| PIC-FR-003 | Prevent double spend in the MVP environment. | P0 |
| PIC-FR-004 | Allow provider settlement and audit of aggregate balances. | P1 |
| PIC-FR-005 | Support expiry and denomination to reduce abuse and simplify accounting. | P1 |
| PIC-FR-006 | Make the credit privacy claim explicit and measurable in docs. | P0 |

## How PIC fits the rest of SIP-AI

- A redeemed voucher's spend is recorded in the signed inference receipt (`price_units: "pic"`, with the amount), giving the client an accountability artifact. See the authoritative receipt format in [receipts.md](receipts.md).
- PIC is one of the privacy modes a provider can advertise in its manifest (`private-payment`). See [manifests.md](manifests.md).
- For the protocol-level view of payment paths and the request lifecycle, see [../prd/sip-ai.md](../prd/sip-ai.md).

---

_Derived from the v0.1.2 Product Requirements Package._
