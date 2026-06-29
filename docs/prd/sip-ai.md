# PRD 1: Sovereign Inference Protocol (SIP-AI)

SIP-AI is the provider-neutral protocol and SDK for discovering open models, selecting an inference provider, paying for inference, transporting the request, and returning a response with a signed receipt. This document is the product requirements for SIP-AI; it describes the full system we are building, with the MVP framed as the first milestone on the path to the production version.

> **Terminology:** SIP-AI = Sovereign Inference Protocol; SIN = Sovereign Inference Node; PIC = Private Inference Credits.

## Product summary

SIP-AI is a provider-neutral protocol and SDK for discovering open models, selecting an inference provider, paying for inference, sending the request over a chosen transport, and receiving a response with a signed receipt. It is designed to make open-weight AI access resilient, portable, and privacy-preserving without depending on one API vendor or one compute network.

## Goals

1. Let applications call open models through an OpenAI-compatible interface while retaining the ability to route across local, decentralized, and self-hosted providers.
2. Let providers publish capacity, model support, price, privacy policy, trust data, and uptime without hand-building a marketplace.
3. Support both direct x402 payment and privacy-preserving inference credits.
4. Provide signed inference receipts tied to model manifests, provider keys, runtime versions, pricing, and token usage.
5. Support multiple transport modes so the network can adapt to normal, privacy-sensitive, and censorship-heavy environments.
6. Make it easy to plug in existing networks such as Nosana, Akash, Chutes, LibertAI, Morpheus, and NodeGhost as provider backends rather than treating them as competitors.

## Non-goals

- No public multi-node model sharding in v1.
- No claim that traffic is undetectable or unblockable.
- No custom LLM runtime as part of the protocol MVP.
- No storage of private prompts, completions, or user identity on Arweave.
- No full zero-knowledge proof of LLM execution in v1.
- No attempt to force one token, chain, marketplace, or model license.

## Primary users

- Developers who want a drop-in open inference endpoint with routing and failover.
- Apps that want local-first inference with decentralized fallback.
- Users who cannot reliably access centralized AI services.
- Providers who want to monetize spare GPUs or servers.
- Model maintainers who want durable model provenance and easy deployment paths.

## Request lifecycle

1. Client declares intent: model, task, privacy mode, budget, latency preference, max tokens, and verification level.
2. Resolver fetches the model manifest and candidate provider manifests.
3. Router scores available providers and requests a quote from the top candidates.
4. Client authorizes payment using direct x402 flow or redeems a Private Inference Credit voucher.
5. Client sends the inference request to the selected provider gateway over the chosen transport.
6. Provider gateway validates payment, policy, quotas, request size, and model availability.
7. Provider runtime executes the full model locally on that provider node.
8. Provider returns response plus signed inference receipt.
9. Client verifies receipt signature, manifest references, token counts, and payment settlement metadata.
10. Router updates local reputation and optionally publishes non-sensitive receipt or benchmark metadata.

## Functional requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| SIP-FR-001 | Provide an OpenAI-compatible chat completions endpoint or SDK wrapper for basic adoption. | P0 |
| SIP-FR-002 | Resolve model manifests by model alias, hash, or registry ID. | P0 |
| SIP-FR-003 | Resolve provider manifests with model support, price, capabilities, and trust metadata. | P0 |
| SIP-FR-004 | Select one provider per request using a configurable scoring policy. | P0 |
| SIP-FR-005 | Support provider quotes before inference execution. | P0 |
| SIP-FR-006 | Support signed inference receipts with provider public key, model manifest hash, token counts, cost, timestamp, and response hash. | P0 |
| SIP-FR-007 | Support direct x402-style payment path for paid API calls. | P1 |
| SIP-FR-008 | Support Private Inference Credit voucher redemption in testnet or simulated mode. | P1 |
| SIP-FR-009 | Support failover when provider health check, quote, payment, or request execution fails. | P0 |
| SIP-FR-010 | Support transport adapters: normal HTTPS in MVP, relay transport in MVP, Tor/I2P/Nym-compatible adapters later. | P1 |
| SIP-FR-011 | Publish model manifests and provider manifests to a durable registry, with Arweave as the initial permanent anchor. | P1 |
| SIP-FR-012 | Expose provider policy metadata, including logging policy, allowed models, rate limits, and blocked request classes. | P0 |
| SIP-FR-013 | Support provider reputation inputs: uptime, receipt validity, benchmark drift, latency, and dispute history. | P1 |
| SIP-FR-014 | Allow providers to advertise optional TEE attestation support. | P2 |
| SIP-FR-015 | Allow clients to request local-only, direct, private-payment, private-transport, confidential, or batch mode. | P1 |

## Non-functional requirements

| Category | Requirement |
| --- | --- |
| Interoperability | Protocol must work with normal HTTP clients and OpenAI-compatible SDKs. |
| Reliability | Router must detect failed providers and retry with another provider when budget and privacy settings permit. |
| Privacy | Default system must avoid storing prompts in public registries and must make logging policy explicit. |
| Security | Provider gateway must authenticate requests, enforce limits, and isolate runtime access. |
| Extensibility | New runtimes, transports, payment methods, and registries must be plugins. |
| Measurability | Every successful request should generate metrics for latency, token count, cost, and receipt verification status. |

## Provider selection model

The router scores providers with a transparent weighted formula. The first implementable version is simple and deterministic, then becomes user-tunable as the system matures.

```text
provider_score =
  0.25 * model_fit
+ 0.20 * expected_latency_score
+ 0.15 * price_score
+ 0.15 * receipt_trust_score
+ 0.10 * uptime_score
+ 0.10 * privacy_mode_match
+ 0.05 * geographic_or_jurisdiction_preference
```

The router should never make provider location or jurisdiction mandatory unless the user explicitly opts into that criterion. Overly strict routing reduces availability and can accidentally create privacy fingerprints. See [provider-selection.md](../spec/provider-selection.md) for the full breakdown of each weighted term and the reputation inputs that feed scoring.

## Private Inference Credits (PIC)

Private Inference Credits, or PICs, are the privacy-preserving payment primitive. Direct x402 is excellent for simple API monetization because it uses the existing HTTP 402 payment pattern [S5, S6]. But direct on-chain payments can link wallet, provider, request timing, and usage. PICs reduce that linkage by separating credit purchase from credit redemption.

### PIC v1 concept

1. User buys a bundle of inference credits from an issuer or mint.
2. The issuer returns blinded or otherwise unlinkable bearer vouchers.
3. The client stores vouchers locally.
4. When making an inference request, the client redeems one or more vouchers with the provider gateway.
5. The provider verifies that the voucher is valid and unspent without learning which wallet bought it.
6. The provider later settles redeemed vouchers with the issuer or settlement layer.

PIC draws inspiration from Chaumian ecash systems such as Cashu and privacy token systems such as Privacy Pass [S30, S31]. The first implementable milestone is a voucher system that demonstrates the privacy boundary and a defined cryptographic upgrade path to real Chaumian-ecash / Privacy-Pass redemption — not cryptographic overreach in the first step. See [private-inference-credits.md](../spec/private-inference-credits.md) for the in-depth design.

### PIC v1 requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| PIC-FR-001 | Issue test credits to a client wallet. | P0 |
| PIC-FR-002 | Redeem credits with a provider without exposing the original purchase ID to the provider. | P1 |
| PIC-FR-003 | Prevent double spend in the MVP environment. | P0 |
| PIC-FR-004 | Allow provider settlement and audit of aggregate balances. | P1 |
| PIC-FR-005 | Support expiry and denomination to reduce abuse and simplify accounting. | P1 |
| PIC-FR-006 | Make the credit privacy claim explicit and measurable in docs. | P0 |

## Signed inference receipts

A signed inference receipt is not a mathematical proof that a specific model computed a specific answer. It is a verifiable accountability artifact. It lets the client and network verify who served the request, what model manifest was claimed, what runtime and quantization were claimed, what price was charged, and whether the receipt signature is valid.

A receipt binds together the provider public key, the model manifest hash, token counts, price, privacy mode, timestamps, and a hash of the response body, all signed by the provider. The authoritative field-by-field receipt format lives in [../spec/receipts.md](../spec/receipts.md); refer to that document for the canonical schema and signing rules.

## Transport modes

SIP-AI supports multiple transport modes so the network adapts to normal, privacy-sensitive, and censorship-heavy environments. HTTPS is the default fast path; private transports are opt-in.

| Mode | Description | MVP status | Tradeoff |
| --- | --- | --- | --- |
| Direct HTTPS | Client talks to provider or gateway over ordinary HTTPS. | P0 | Fast and simple, but weaker metadata privacy. |
| Relay HTTPS | Client routes through one or more SIP-AI relays. | P0/P1 | Better IP separation, extra latency and trust assumptions. |
| Tor/Snowflake-compatible | Use Tor ecosystem or Snowflake-style circumvention path where appropriate. | P2 | Improves reach in censored networks, but can be slow or blocked [S27]. |
| I2P-compatible | Use I2P hidden service or tunnel path. | P2 | Good for anonymous overlay use, but adoption and UX are harder [S28]. |
| Nym-compatible | Use mixnet-style metadata protection. | P2 | Stronger metadata privacy patterns, higher latency [S29]. |
| Batch/offline | Send delayed request and retrieve later. | P2 | Resilient under censorship, no streaming UX. |

For full detail on each transport adapter, its tradeoffs, and MVP status, see [transport-modes.md](../spec/transport-modes.md).

## Model and provider manifests

Public manifests create portable trust. Arweave is a strong initial storage layer because the competition emphasizes permanent storage and Arweave positions itself as a permanent, permissionless storage network [S3, S9].

Manifests come in two shapes: a **model manifest** describing a model artifact (hash, format, quantization, license, runtime support, recommended settings) and a **provider manifest** describing a node (supported models, price, runtime, benchmark, policy, privacy modes, public key). Manifests are published to a local registry first and optionally anchored on Arweave. The authoritative JSON Schemas live in `docs/spec/schemas/`. See [manifests.md](../spec/manifests.md) for both manifest shapes with field-by-field explanation.

## Security and abuse controls

- Providers must choose which models they serve and what request classes they allow.
- Provider gateways must enforce request size, context length, concurrency, and spend caps.
- Users should see provider logging and retention policy before routing sensitive requests.
- Private transport modes should be opt-in with clear latency and reliability warnings.
- Provider nodes should not allow arbitrary remote model loading, custom code execution, or shell execution through the inference endpoint.
- The network does not promise absolute anonymity or guaranteed access against every censor. It promises layered resilience and transparent tradeoffs.

## MVP scope for SIP-AI

This MVP is the first milestone of a real, production-bound protocol, not a throwaway demo. Each "mock" or "simulated" element below names the first implementable step with a defined path to the full cryptographic and networked version.

| Capability | MVP decision |
| --- | --- |
| Protocol interface | OpenAI-compatible chat completions wrapper plus SIP-specific quote, receipt, and provider endpoints. |
| Registry | Local registry JSON plus optional Arweave-published manifest anchor. |
| Providers | At least two providers: one local SIN node and one remote adapter such as Nosana, Akash, Chutes, or a simple cloud GPU. |
| Payment | First-step x402 flow plus voucher-based PIC redemption, with a defined upgrade path to full x402 settlement and Chaumian-ecash/Privacy-Pass credits. |
| Transport | Direct HTTPS plus relay mode. Tor/I2P/Nym adapters documented but not required for this milestone. |
| Verification | Signed receipt, model manifest hash, runtime version, response hash, and simple verifier CLI. |
| Demo | Route a request, show payment, show receipt, kill provider, demonstrate failover. |

## SIP-AI success metrics

| Metric | Target for hackathon demo |
| --- | --- |
| Time to first routed inference | Under 10 minutes from clean install on developer machine. |
| Provider failover | Client succeeds after one provider is stopped or unhealthy. |
| Receipt verification | 100 percent of successful demo requests return verifiable signed receipts. |
| Payment demo | At least one direct x402-like flow and one PIC redemption flow. |
| Provider neutrality | At least two runtime/provider adapters demonstrated. |
| Evidence quality | Metrics dashboard shows latency, TTFT, tokens/sec, cost, receipt status, and provider health. |

---

See also: [sin.md](sin.md) for the Sovereign Inference Node product requirements.

_Derived from the v0.1.2 Product Requirements Package._
