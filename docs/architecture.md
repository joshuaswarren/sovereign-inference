# Architecture

How the two products fit together and the principles that keep the system
provider-neutral, local-first, and safe. This is the system we are building for
real; the [MVP plan](mvp-and-demo.md) is its first milestone, not its ceiling.

## Two products, one access layer

- **SIP-AI — Sovereign Inference Protocol**: the neutral protocol + SDK layer for
  model discovery, provider selection, privacy-preserving payments, transport
  modes, signed receipts, and routing across decentralized or self-hosted
  providers. See [PRD: SIP-AI](prd/sip-ai.md).
- **SIN — Sovereign Inference Node**: the local-first node that inspects your
  hardware, recommends and installs an open model, runs it locally, benchmarks
  it, and optionally offers spare capacity to the network. See
  [PRD: SIN](prd/sin.md).

The **core novelty is the orchestration layer** that makes existing pieces
(local runtimes, compute markets, storage, payment, privacy networks)
composable, usable, and provider-neutral — not a new GPU marketplace, a new
local runner, or a new anonymity network.

## Logical system

```text
User app or CLI
  -> SIP-AI Client SDK
     -> Resolver and model registry
     -> Router and provider selector
     -> Payment mode: x402 or Private Inference Credits (PIC)
     -> Transport adapter: HTTPS, relay, Tor/I2P/Nym-compatible, or batch
        -> Provider gateway on a Sovereign Inference Node
           -> Runtime adapter: llama.cpp, Ollama, vLLM, SGLang, LocalAI, LM Studio
           -> Full model execution on one provider node
        <- Response plus signed inference receipt
     <- Optional public receipt anchor and reputation update
```

## Core roles

| Role | Description | Package |
| --- | --- | --- |
| Client | App, CLI, SDK, or browser extension requesting inference. | [`router`](../packages/router), [`sdk-js`](../sdk-js) |
| Resolver | Finds model manifests, provider manifests, pricing, and trust data. | [`router`](../packages/router) |
| Router | Selects one provider per request from a scoring policy; handles quotes and failover. | [`router`](../packages/router) |
| Provider gateway | Hardened front door over the runtime: auth, quotas, policy, logging, receipts. | [`provider-gateway`](../packages/provider-gateway) |
| Runtime adapter | Connector to Ollama, llama.cpp, vLLM, SGLang, LocalAI, LM Studio. | [`adapters/*`](../adapters) |
| PIC issuer | Issues unlinkable inference credits redeemable by providers. | [`pic-vouchers`](../packages/pic-vouchers) |
| Settlement | Lets providers redeem credits or direct x402 payments. | [`pic-vouchers`](../packages/pic-vouchers) |
| Registry / storage | Public model + provider manifests, spec versions, attestations (Arweave-anchored). | [`registry`](../registry) |
| Protocol core | Canonical JSON, Ed25519 signing, manifests, receipts, schema validation. | [`sip-protocol`](../packages/sip-protocol) |

## Key design decisions

1. **One provider per request in v1.** Each inference request is served in full
   by one selected provider node. Failover happens *between* providers, never
   *within* one model execution. This is deliberately not Petals-style sharded
   inference — it keeps latency, security, accountability, and verification
   tractable. (Petals is prior art, explicitly out of scope for v1 routing.)
2. **Adapter-first protocol.** SIP-AI does not require every provider to run the
   same engine, chain, or marketplace. The protocol defines *manifests, quotes,
   payments, receipts, and transport expectations*; SIN and adapters do the
   runtime-specific work.
3. **Public provenance, private prompts.** Model/provider manifests and public
   receipts can be anchored on durable storage (Arweave). User prompts and
   completions are never published.
4. **Safe by default.** A runtime is never exposed to the open internet without
   a hardened gateway. Public sharing is explicit opt-in, capped, and pausable.
5. **Evidence over ideology.** Every claim is backed by code, measurements,
   traces, manifests, and reproducible demos — see the
   [evidence plan](hackathon/evidence-plan.md).

## Trust & verification

Verification in v1 is an **accountability artifact**, not a cryptographic proof
of model execution. A [signed inference receipt](spec/receipts.md) binds the
provider key, claimed model manifest hash, runtime, token counts, price, and a
hash of the response under an Ed25519 signature any client can check offline.
Optional TEE attestation is a later, stronger trust mode.

## Implementation status

| Layer | Status |
| --- | --- |
| `sip-protocol` (canonical JSON, Ed25519, receipts, manifests, schemas) | **Implemented + tested** |
| `sip-receipt` verifier CLI | **Implemented + tested** |
| Router, provider gateway, SIN node/CLI, PIC, adapters, dashboard | Scaffolded — see [ROADMAP](../ROADMAP.md) |

_See the [protocol spec](spec/protocol-spec.md) for the authoritative formats and endpoints._
