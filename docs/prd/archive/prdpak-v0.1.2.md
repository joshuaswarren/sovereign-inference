# Sovereign Inference Protocol and Sovereign Inference Node

**Product Requirements Package v0.1.2**
Prepared for Joshua Warren
Personal project under Joshua Warren
Date: June 29, 2026
Draft status: strategy, product requirements, architecture, MVP plan, and PM artifact set

---


# 0. Executive Summary

This package defines two tightly linked products: Sovereign Inference Protocol, abbreviated here as SIP-AI to avoid confusion with VoIP SIP, and Sovereign Inference Node, abbreviated SIN. Together they solve both sides of the open AI access problem.

- SIP-AI is the neutral protocol layer for model discovery, provider selection, privacy-preserving payments, transport modes, inference receipts, and routing across decentralized or self-hosted providers.
- SIN is the local-first node that helps people inspect their hardware, choose the right open model, download it, run it locally, benchmark it, and optionally offer spare capacity to the network.
- The system explicitly avoids model sharding across multiple public nodes in v1. Each inference request is handled by one selected provider node or server. Failover happens between providers, not within one model execution.
- The core novelty is not a new GPU marketplace, a new local model runner, or a new anonymity network. The novelty is the orchestration layer that makes existing pieces composable, safe, usable, and provider-neutral.
- The hackathon wedge is strong because DecentralizeAI explicitly highlights distributed compute, edge/local inference, open inference protocols, permanent storage, verifiable AI, and data sovereignty tooling as part of the desired decentralized AI stack [S1, S2, S3].

The product thesis: anyone should be able to run open AI privately, and anyone with spare hardware should be able to become a safe, benchmarked, compensated inference provider without learning CUDA deployment, model quantization, runtime tuning, crypto settlement, or server hardening.

## Recommended one-line pitch

> Sovereign Inference lets anyone run the best open model their hardware can handle, and optionally share that capacity through a privacy-preserving, censorship-resistant open inference network.

## The two-product bundle

| Product | Audience | Primary job | MVP proof |
| --- | --- | --- | --- |
| SIP-AI | Developers, apps, routers, marketplaces | Route paid inference to open models without one API chokepoint | OpenAI-compatible request routed to a provider with signed receipt and test payment |
| SIN | Individuals, homelab owners, GPU providers, small teams | Choose, install, run, benchmark, and share open models | Scan hardware, recommend model, run local server, publish provider manifest |

## Non-negotiable v1 constraint

This is not Petals-style distributed model execution where several unrelated users combine GPUs to serve one prompt. Petals is important prior art for collaborative inference, but SIP-AI v1 should route one user request to one provider node that has the full selected model available [S20]. This constraint keeps latency, security, provider accountability, and verification tractable.

---


# 1. Naming and Brand Strategy

The name Sovereign Inference Protocol is strong. It communicates user ownership, self-hosting, open access, and exit from centralized AI chokepoints. There is one practical issue: SIP is already widely used for the Session Initiation Protocol defined by IETF RFC 3261, especially in VoIP and multimedia session signaling [S4].

| Name | Use | Risk | Recommendation |
| --- | --- | --- | --- |
| Sovereign Inference Protocol | Public concept and protocol name | SIP acronym collision with Session Initiation Protocol | Use the full name in public copy and SIP-AI in technical docs |
| SIP-AI | Engineering and spec acronym | Still close to SIP, but differentiated | Use for repository names, package names, and protocol docs |
| Sovereign Inference Node | Installable local serving node | SIN acronym is memorable but polarizing | Use SIN in hackathon/dev community; use Sovereign Node for enterprise-facing copy |
| Private Inference Credits | Payment/voucher layer | PIC is generic but clear | Use PIC as the privacy-preserving credit primitive |
| Sovereign Receipts | Signed proof of execution | Could imply stronger verification than provided | Use Signed Inference Receipt until verification matures |

## Naming guardrails

- Do not use sip:// as a URL scheme. It creates unnecessary collision with existing telephony infrastructure.
- Use package names like sovinfer, sovereign-inference, sip-ai-sdk, and sovereign-node.
- Use SIN as an internal and hackathon-friendly acronym, but default to Sovereign Node in conservative contexts.
- Avoid promising invisibility, undetectability, or guaranteed censorship bypass. Use resilient, privacy-preserving, censorship-resistant, and hard to block instead.

# 2. Opportunity Assessment

## Problem

Open-source AI access is fragile. The model weights may be open, but most people still depend on centralized APIs, centralized clouds, app-store-controlled clients, blocked websites, or hardware they cannot afford. Running locally is powerful, but it is still too hard for ordinary users. Serving to others is even harder: providers need to pick models, install runtimes, secure endpoints, price requests, measure capacity, handle payment, and earn trust.

## Customer jobs

| Persona | Job to be done | Current pain |
| --- | --- | --- |
| Blocked user | Use open models when centralized AI services are unavailable or unreliable | APIs and model sites can be blocked, slow, or identity-gated |
| No-GPU user | Access open models without owning expensive hardware | Local inference is too slow or impossible |
| GPU owner | Turn spare compute into useful service or income | Serving safely requires ML ops, networking, security, and payment knowledge |
| Developer | Swap between local and decentralized providers without rewriting code | Each provider has different APIs, auth, pricing, and reliability |
| Researcher/journalist/NGO | Use models privately for sensitive work | Centralized providers create policy, logging, availability, and jurisdiction concerns |
| Open model maintainer | Make model access durable after release | Distribution, provenance, and deployment instructions are fragmented |

## Why now

- Open-weight models are good enough for many everyday and professional workloads.
- Local model runtimes have matured and many expose OpenAI-compatible endpoints, including Ollama, llama.cpp, LocalAI, LM Studio, vLLM, and SGLang [S10, S11, S12, S13, S14, S15].
- Decentralized compute markets and inference networks already exist, including Nosana, Akash, Chutes, LibertAI, Morpheus, and NodeGhost [S7, S22, S23, S24, S25, S26].
- HTTP-native crypto payments are becoming easier through x402, while private token systems such as Cashu and Privacy Pass provide patterns for unlinkable credit redemption [S5, S6, S30, S31].
- The DecentralizeAI competition is actively rewarding real infrastructure contributions, not just conceptual essays [S2, S3].

## Positioning

> Sovereign Inference is the access and supply layer for open AI: local-first when possible, decentralized when needed, provider-neutral by design.

# 3. Product Principles

1. Local-first: the best request is the one the user can run privately on their own machine.
2. Provider-neutral: plug into existing runtimes and networks instead of trying to replace all of them.
3. One provider per request in v1: no public multi-node model sharding for the first product generation.
4. Privacy without magical claims: reduce metadata leakage and improve resilience, but do not claim traffic is impossible to detect or block.
5. OpenAI-compatible where practical: reduce migration friction for users and apps.
6. Public provenance, private prompts: store model manifests and public receipts on durable storage, not user prompts.
7. Safe by default: never expose raw model runtimes directly to the open internet without a hardened gateway.
8. Composable economics: support x402 direct payment first, then private inference credits for unlinkability.
9. Evidence over ideology: every hackathon claim should be backed by code, measurements, traces, manifests, and reproducible demos.

# 4. Current Landscape and Build-On Strategy

The market already contains strong pieces. The opportunity is to avoid competing with every piece and instead become the adapter, router, usability, payment, and trust layer that makes the pieces work together.

| Layer | Existing projects | What they provide | How SIP-AI and SIN build on them |
| --- | --- | --- | --- |
| Local model runners | Ollama, llama.cpp, LocalAI, LM Studio, Jan | Local model execution and OpenAI-compatible APIs | Wrap as runtime adapters; add hardware-aware recommendation, benchmark, sharing, and network publication [S10, S11, S14, S15, S16] |
| Production inference runtimes | vLLM, SGLang | High-throughput serving and OpenAI-compatible APIs | Use for serious provider nodes and GPU backends [S12, S13] |
| Containerized local serving | RamaLama | Container-based model serving with hardware inspection and CPU fallback | Study or integrate as a Linux provider runtime path [S17, S18] |
| Local clusters | Exo | Multi-device local AI clusters | Later adapter for LAN/local clusters, not public sharded inference [S19] |
| Collaborative sharded inference | Petals | Layer/block-sharded collaborative inference | Prior art only for v1; explicitly out of scope for routing architecture [S20] |
| Decentralized compute/inference | Nosana, Akash, Chutes, LibertAI, Morpheus, NodeGhost | Compute markets, decentralized inference, provider networks, OpenAI-compatible gateways | Use as optional backend adapters, not direct competitors [S7, S22, S23, S24, S25, S26] |
| Permanent storage | Arweave | Permanent public data storage | Store model manifests, provider manifests, signed public receipts, benchmark attestations, and spec versions [S9] |
| Transport privacy and resilience | Tor/Snowflake, I2P, Nym | Censorship circumvention, anonymous overlay routing, or metadata protection | Implement transport adapters while keeping normal HTTPS as the default fast path [S27, S28, S29] |
| Payment | x402, Cashu-like ecash, Privacy Pass-like tokens | HTTP-native payments and privacy-preserving token patterns | Use x402 for direct pay; use PIC vouchers for unlinkable request redemption [S5, S6, S30, S31] |
| Confidential/verifiable compute | Targon, Atoma, TEE-based systems | Confidential compute and attestation approaches | Optional trust mode for providers with TEE support [S35, S36] |

## Differentiation

Most projects start from one layer: a compute market, a model runner, a decentralized gateway, or a privacy network. Sovereign Inference starts from the user workflow and the provider onboarding workflow. It asks: what model should I run, will it fit, can I serve it safely, who can find it, how do I get paid, and how does a user know what happened?

# 5. Product Architecture Overview

## Logical system

```text
User app or CLI
  -> SIP-AI Client SDK
     -> Resolver and model registry
     -> Router and provider selector
     -> Payment mode: x402 or Private Inference Credits
     -> Transport adapter: HTTPS, relay, Tor/I2P/Nym-compatible, or batch
        -> Provider gateway on a Sovereign Inference Node
           -> Runtime adapter: llama.cpp, Ollama, vLLM, SGLang, LocalAI, LM Studio
           -> Full model execution on one provider node
        <- Response plus signed inference receipt
     <- Optional public receipt anchor and reputation update
```

## Core roles

| Role | Description |
| --- | --- |
| Client | The app, CLI, SDK, or browser extension requesting inference. |
| Resolver | Finds model manifests, provider manifests, pricing, and trust data. |
| Router | Selects one provider for each request based on model fit, price, latency, trust, privacy mode, and availability. |
| Provider gateway | A hardened front door in front of the local or remote runtime. It enforces auth, quotas, policy, logging settings, and receipt generation. |
| Runtime adapter | Connector to Ollama, llama.cpp, LocalAI, vLLM, SGLang, LM Studio, or other execution engines. |
| Private Inference Credit issuer | Issues blinded or otherwise unlinkable inference credits that can be redeemed by providers. |
| Settlement layer | Lets providers redeem used credits or direct x402 payments. |
| Registry/storage | Stores public model manifests, provider manifests, spec versions, and public attestations. Arweave is the natural first choice. |

## Key design decision

The protocol should be adapter-first. SIP-AI should not require every provider to run the same model engine, use the same chain, or join the same compute market. The protocol defines manifests, quotes, payments, receipts, and transport expectations. SIN and adapters do the runtime-specific work.

---


# 6. PRD 1: Sovereign Inference Protocol

## 6.1 Product summary

SIP-AI is a provider-neutral protocol and SDK for discovering open models, selecting an inference provider, paying for inference, sending the request over a chosen transport, and receiving a response with a signed receipt. It is designed to make open-weight AI access resilient, portable, and privacy-preserving without depending on one API vendor or one compute network.

## 6.2 Goals

1. Let applications call open models through an OpenAI-compatible interface while retaining the ability to route across local, decentralized, and self-hosted providers.
2. Let providers publish capacity, model support, price, privacy policy, trust data, and uptime without hand-building a marketplace.
3. Support both direct x402 payment and privacy-preserving inference credits.
4. Provide signed inference receipts tied to model manifests, provider keys, runtime versions, pricing, and token usage.
5. Support multiple transport modes so the network can adapt to normal, privacy-sensitive, and censorship-heavy environments.
6. Make it easy to plug in existing networks such as Nosana, Akash, Chutes, LibertAI, Morpheus, and NodeGhost as provider backends rather than treating them as competitors.

## 6.3 Non-goals

- No public multi-node model sharding in v1.
- No claim that traffic is undetectable or unblockable.
- No custom LLM runtime as part of the protocol MVP.
- No storage of private prompts, completions, or user identity on Arweave.
- No full zero-knowledge proof of LLM execution in v1.
- No attempt to force one token, chain, marketplace, or model license.

## 6.4 Primary users

- Developers who want a drop-in open inference endpoint with routing and failover.
- Apps that want local-first inference with decentralized fallback.
- Users who cannot reliably access centralized AI services.
- Providers who want to monetize spare GPUs or servers.
- Model maintainers who want durable model provenance and easy deployment paths.

## 6.5 Request lifecycle

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

## 6.6 Functional requirements

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

## 6.7 Non-functional requirements

| Category | Requirement |
| --- | --- |
| Interoperability | Protocol must work with normal HTTP clients and OpenAI-compatible SDKs. |
| Reliability | Router must detect failed providers and retry with another provider when budget and privacy settings permit. |
| Privacy | Default system must avoid storing prompts in public registries and must make logging policy explicit. |
| Security | Provider gateway must authenticate requests, enforce limits, and isolate runtime access. |
| Extensibility | New runtimes, transports, payment methods, and registries must be plugins. |
| Measurability | Every successful request should generate metrics for latency, token count, cost, and receipt verification status. |

## 6.8 Provider selection model

The router should score providers with a transparent weighted formula. The MVP can be simple and deterministic, then become user-tunable later.

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

The router should never make provider location or jurisdiction mandatory unless the user explicitly opts into that criterion. Overly strict routing reduces availability and can accidentally create privacy fingerprints.

## 6.9 Private Inference Credits

Private Inference Credits, or PICs, are the privacy-preserving payment primitive. Direct x402 is excellent for simple API monetization because it uses the existing HTTP 402 payment pattern [S5, S6]. But direct on-chain payments can link wallet, provider, request timing, and usage. PICs reduce that linkage by separating credit purchase from credit redemption.

### PIC v1 concept

1. User buys a bundle of inference credits from an issuer or mint.
2. The issuer returns blinded or otherwise unlinkable bearer vouchers.
3. The client stores vouchers locally.
4. When making an inference request, the client redeems one or more vouchers with the provider gateway.
5. The provider verifies that the voucher is valid and unspent without learning which wallet bought it.
6. The provider later settles redeemed vouchers with the issuer or settlement layer.

PIC can draw inspiration from Chaumian ecash systems such as Cashu and privacy token systems such as Privacy Pass, but the MVP should avoid cryptographic overreach. A simulated voucher system is acceptable for a hackathon demo if the architecture shows the privacy boundary and future cryptographic upgrade path [S30, S31].

### PIC v1 requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| PIC-FR-001 | Issue test credits to a client wallet. | P0 |
| PIC-FR-002 | Redeem credits with a provider without exposing the original purchase ID to the provider. | P1 |
| PIC-FR-003 | Prevent double spend in the MVP environment. | P0 |
| PIC-FR-004 | Allow provider settlement and audit of aggregate balances. | P1 |
| PIC-FR-005 | Support expiry and denomination to reduce abuse and simplify accounting. | P1 |
| PIC-FR-006 | Make the credit privacy claim explicit and measurable in docs. | P0 |

## 6.10 Signed inference receipts

A signed inference receipt is not a mathematical proof that a specific model computed a specific answer. It is a verifiable accountability artifact. It lets the client and network verify who served the request, what model manifest was claimed, what runtime and quantization were claimed, what price was charged, and whether the receipt signature is valid.

### Receipt fields

```text
{
  "receipt_version": "sip-ai.receipt.v1",
  "request_id": "opaque-client-generated-id",
  "provider_pubkey": "ed25519:...",
  "model_manifest_hash": "sha256:...",
  "model_alias": "qwen-coder-7b-instruct-gguf-q4_k_m",
  "runtime": "llama.cpp",
  "runtime_version": "...",
  "input_tokens": 817,
  "output_tokens": 242,
  "price_units": "pic",
  "price_amount": "0.0042",
  "privacy_mode": "private-payment-relay",
  "started_at": "2026-06-29T18:15:02Z",
  "completed_at": "2026-06-29T18:15:09Z",
  "response_hash": "sha256:hash-of-response-body",
  "signature": "provider-signature-over-canonical-receipt"
}
```

## 6.11 Transport modes

| Mode | Description | MVP status | Tradeoff |
| --- | --- | --- | --- |
| Direct HTTPS | Client talks to provider or gateway over ordinary HTTPS. | P0 | Fast and simple, but weaker metadata privacy. |
| Relay HTTPS | Client routes through one or more SIP-AI relays. | P0/P1 | Better IP separation, extra latency and trust assumptions. |
| Tor/Snowflake-compatible | Use Tor ecosystem or Snowflake-style circumvention path where appropriate. | P2 | Improves reach in censored networks, but can be slow or blocked [S27]. |
| I2P-compatible | Use I2P hidden service or tunnel path. | P2 | Good for anonymous overlay use, but adoption and UX are harder [S28]. |
| Nym-compatible | Use mixnet-style metadata protection. | P2 | Stronger metadata privacy patterns, higher latency [S29]. |
| Batch/offline | Send delayed request and retrieve later. | P2 | Resilient under censorship, no streaming UX. |

## 6.12 Model and provider manifests

Public manifests create portable trust. Arweave is a strong initial storage layer because the competition emphasizes permanent storage and Arweave positions itself as a permanent, permissionless storage network [S3, S9].

### Model manifest example

```text
{
  "schema": "sip-ai.model_manifest.v1",
  "model_id": "qwen-coder-7b-instruct-gguf-q4_k_m",
  "display_name": "Qwen Coder 7B Instruct GGUF Q4_K_M",
  "source_repo": "huggingface:example/repo",
  "weights_hash": "sha256:...",
  "format": "GGUF",
  "quantization": "Q4_K_M",
  "license": "model-license-id",
  "recommended_runtimes": ["llama.cpp", "ollama"],
  "min_memory_gb": 8,
  "recommended_memory_gb": 16,
  "context_tested": [4096, 8192],
  "tasks": ["coding", "general-chat"],
  "manifest_uri": "arweave://...",
  "maintainer_signature": "..."
}
```

### Provider manifest example

```text
{
  "schema": "sip-ai.provider_manifest.v1",
  "provider_pubkey": "ed25519:...",
  "node_type": "sovereign-node",
  "models": ["qwen-coder-7b-instruct-gguf-q4_k_m"],
  "runtime_adapters": ["llama.cpp"],
  "pricing": {"unit": "pic", "input_per_1m": 0.20, "output_per_1m": 0.80},
  "max_context": 8192,
  "max_concurrency": 2,
  "logging_policy": "no_prompt_logging",
  "retention_policy": "metrics_only_30d",
  "privacy_modes": ["direct", "relay", "private-payment"],
  "benchmark": {"tokens_per_second": 39.4, "ttft_ms": 520},
  "published_at": "2026-06-29T18:00:00Z",
  "signature": "..."
}
```

## 6.13 Security and abuse controls

- Providers must choose which models they serve and what request classes they allow.
- Provider gateways must enforce request size, context length, concurrency, and spend caps.
- Users should see provider logging and retention policy before routing sensitive requests.
- Private transport modes should be opt-in with clear latency and reliability warnings.
- Provider nodes should not allow arbitrary remote model loading, custom code execution, or shell execution through the inference endpoint.
- The network should not promise absolute anonymity or guaranteed access against every censor. It should promise layered resilience and transparent tradeoffs.

## 6.14 MVP scope for SIP-AI

| Capability | MVP decision |
| --- | --- |
| Protocol interface | OpenAI-compatible chat completions wrapper plus SIP-specific quote, receipt, and provider endpoints. |
| Registry | Local registry JSON plus optional Arweave-published manifest anchor. |
| Providers | At least two providers: one local SIN node and one remote adapter such as Nosana, Akash, Chutes, or a simple cloud GPU. |
| Payment | Mock x402 flow plus simulated PIC voucher redemption. |
| Transport | Direct HTTPS plus relay mode. Tor/I2P/Nym adapters documented but not required for MVP. |
| Verification | Signed receipt, model manifest hash, runtime version, response hash, and simple verifier CLI. |
| Demo | Route a request, show payment, show receipt, kill provider, demonstrate failover. |

## 6.15 SIP-AI success metrics

| Metric | Target for hackathon demo |
| --- | --- |
| Time to first routed inference | Under 10 minutes from clean install on developer machine. |
| Provider failover | Client succeeds after one provider is stopped or unhealthy. |
| Receipt verification | 100 percent of successful demo requests return verifiable signed receipts. |
| Payment demo | At least one direct x402-like or mocked x402 flow and one PIC redemption flow. |
| Provider neutrality | At least two runtime/provider adapters demonstrated. |
| Evidence quality | Metrics dashboard shows latency, TTFT, tokens/sec, cost, receipt status, and provider health. |

---


# 7. PRD 2: Sovereign Inference Node

## 7.1 Product summary

Sovereign Inference Node is the installable local node that turns an ordinary machine into a private AI workstation, a team AI server, or an optional network provider. SIN handles hardware detection, model recommendation, model fetching, runtime installation, local serving, benchmarking, hardening, and network publication.

## 7.2 Goals

1. Answer the user question: what is the best open model for my need that will actually run well on this hardware?
2. Install the selected model and runtime with minimal manual setup.
3. Run a local OpenAI-compatible endpoint for private use.
4. Benchmark the node and produce a signed capability manifest.
5. Let the user safely publish spare capacity to the SIP-AI network.
6. Make sharing reversible, capped, policy-controlled, and observable.

## 7.3 Non-goals

- No attempt to replace Ollama, llama.cpp, vLLM, SGLang, LocalAI, or LM Studio.
- No public model sharding across many strangers in v1.
- No requirement that every user use crypto to run local models.
- No assumption that all providers are always online or professionally operated.
- No exposing local models to the internet without explicit user action.

## 7.4 Core user flows

### Flow A: What can my machine run?

1. User installs SIN.
2. SIN scans CPU, RAM, GPU, VRAM, OS, drivers, disk, battery/power state, network, and existing runtimes.
3. SIN asks the user what they want to do: chat, code, RAG, embeddings, vision, long context, low latency, private local use, or sharing.
4. SIN recommends model/runtime/quantization combinations with expected speed, memory, and tradeoffs.
5. User chooses one and clicks install or runs one CLI command.

### Flow B: Run privately

1. SIN downloads the model, verifies checksum or manifest hash, shows license summary, and installs or selects the runtime.
2. SIN starts a local server bound to localhost by default.
3. User sends a test prompt through the local dashboard or OpenAI-compatible endpoint.
4. SIN records local benchmark metrics and recommends configuration adjustments.

### Flow C: Share spare capacity

1. User opts into network sharing.
2. SIN runs a provider qualification benchmark.
3. User sets max requests/hour, max bandwidth, spend/earning limits, uptime window, allowed models, logging policy, and safety policy.
4. SIN starts a hardened provider gateway in front of the runtime.
5. SIN publishes a signed provider manifest.
6. Remote SIP-AI client routes a request to this node.
7. Provider earns test credits or settled payment and sees usage metrics.

## 7.5 Functional requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| SIN-FR-001 | Detect OS, CPU architecture, RAM, disk space, GPU vendor, GPU memory, drivers, and existing model runtimes. | P0 |
| SIN-FR-002 | Recommend at least three model/runtime/quantization combinations for a chosen task. | P0 |
| SIN-FR-003 | Estimate memory fit including model weights and context/KV-cache headroom. | P0 |
| SIN-FR-004 | Fetch and verify a model artifact or call an existing runtime pull command. | P0 |
| SIN-FR-005 | Start a local-only OpenAI-compatible endpoint. | P0 |
| SIN-FR-006 | Run a benchmark for tokens/sec, time to first token, memory usage, and max stable context. | P0 |
| SIN-FR-007 | Create and sign a provider capability manifest. | P0 |
| SIN-FR-008 | Expose network sharing controls with safe defaults and explicit opt-in. | P0 |
| SIN-FR-009 | Run a hardened provider gateway in front of the runtime. | P0 |
| SIN-FR-010 | Enforce quotas, rate limits, request size limits, model allowlists, and logging policy. | P0 |
| SIN-FR-011 | Support payment validation and signed receipt generation. | P1 |
| SIN-FR-012 | Publish provider manifest to local registry and optionally Arweave. | P1 |
| SIN-FR-013 | Provide a simple dashboard for health, earnings, requests, latency, and pause/resume. | P1 |
| SIN-FR-014 | Support adapter plugins for Ollama, llama.cpp, vLLM, SGLang, LocalAI, and LM Studio over time. | P1/P2 |

## 7.6 Hardware profiler

The profiler should produce a user-readable diagnosis and a machine-readable hardware profile. It should not overwhelm users with GPU jargon unless they ask for details.

| Input | How used |
| --- | --- |
| RAM and VRAM | Filter models and quantizations that fit. |
| CPU and instruction set | Choose CPU fallback or optimized runtime. |
| GPU vendor and driver | Choose CUDA, ROCm, Metal/MLX, Vulkan, or CPU path. |
| Disk space | Filter large model downloads and warn about storage. |
| Power/battery/thermal state | Warn laptop users before sharing capacity. |
| Network bandwidth and NAT | Recommend local-only, LAN-only, relay, or public provider mode. |
| Existing runtimes | Reuse Ollama, LM Studio, LocalAI, llama.cpp, or vLLM if already installed. |

## 7.7 Model recommendation engine

The recommendation engine combines static catalog data, memory estimates, licensing constraints, runtime compatibility, task benchmarks, and local benchmark feedback. A simple first version is enough if it is transparent.

### Fit algorithm

```text
candidate_models = filter_by_task(task)
candidate_models = filter_by_license(candidate_models, commercial_required)
candidate_models = filter_by_runtime_support(candidate_models, hardware_profile)
for model in candidate_models:
    weight_memory = params * quant_bits / 8 * overhead_factor
    kv_headroom = estimate_kv_cache(model, target_context, concurrency)
    total_memory = weight_memory + kv_headroom + runtime_overhead
    fit_score = memory_available / total_memory
    quality_score = benchmark_score_for_task(model, task)
    speed_score = predicted_tokens_per_second(model, hardware_profile, runtime)
    recommendation_score = weighted_sum(fit_score, quality_score, speed_score, license_score, privacy_score)
return ranked_recommendations
```

For rough estimation, the advisor can use published inference memory rules of thumb and improve them with local benchmark data. Modal gives a simple FP16 rule of thumb of about 2GB of GPU memory per 1B parameters, and Hugging Face Accelerate provides a model memory estimator [S32, S33]. Long context must be treated separately because KV cache can become a significant memory consumer [S34].

## 7.8 Runtime adapter strategy

| Adapter | Best use | Priority |
| --- | --- | --- |
| Ollama | Beginner-friendly local use and existing local installs. | P0 |
| llama.cpp | Reproducible GGUF local serving, CPU/GPU fallback, simple benchmarking. | P0 |
| vLLM | Provider-grade NVIDIA/AMD/GPU serving and higher concurrency. | P1 |
| SGLang | Production serving for advanced providers. | P2 |
| LocalAI | Multi-modal local/on-prem engine and OpenAI-compatible local deployments. | P2 |
| LM Studio | Desktop users who already use LM Studio as a local server. | P2 |
| RamaLama | Linux/container-first local serving path. | P2 |

## 7.9 Serving and sharing controls

- Local-only is the default.
- LAN/team mode is second.
- Public network sharing is explicit opt-in.
- Prompt logging is off by default for public sharing, but providers can choose stricter or looser policy within legal and network policy bounds.
- Users can cap requests per hour, tokens per request, total tokens per day, bandwidth, CPU/GPU utilization, and operating hours.
- Users can pause sharing instantly.
- The dashboard should show what model is running, who can access it, current request load, expected temperature or utilization concerns, and earned credits.

## 7.10 Provider benchmark

| Metric | Definition |
| --- | --- |
| Time to first token | Milliseconds from accepted request to first generated token. |
| Tokens per second | Output throughput under standard prompt and generation length. |
| Max stable context | Largest context length that runs without out-of-memory or severe degradation. |
| Concurrency | Number of simultaneous requests that maintain acceptable latency. |
| Memory use | Peak RAM/VRAM for benchmark run. |
| Uptime probe | Whether node responds consistently over a window. |
| Receipt validity | Whether signed receipts verify against provider public key. |

## 7.11 SIN MVP scope

| Capability | MVP decision |
| --- | --- |
| Interface | CLI plus lightweight local web dashboard. |
| Hardware scan | Mac/Linux first, Windows later unless easy. Detect CPU/RAM/disk/GPU where possible. |
| Runtimes | Ollama and llama.cpp first. |
| Model format | GGUF first because Hugging Face supports GGUF metadata and common local tools use it [S21]. |
| Model catalog | 5 curated models across chat, coding, embeddings, and small/fast use. |
| Local serving | localhost OpenAI-compatible endpoint. |
| Sharing | Expose provider gateway and publish signed manifest to local registry. Optional Arweave anchor. |
| Payment | Accept test PIC vouchers and produce signed receipt. |
| Dashboard | Health, local model, benchmark, sharing status, requests, receipts, pause/resume. |

## 7.12 SIN CLI sketch

```text
sin scan
sin recommend --task coding --privacy local --latency balanced
sin install qwen-coder-7b --quant q4_k_m
sin serve --local
sin benchmark
sin share --model qwen-coder-7b --max-requests 50/hour --price auto
sin status
sin pause-sharing
sin verify-receipt receipt.json
```

## 7.13 SIN success metrics

| Metric | Target |
| --- | --- |
| Time to first local model | Under 15 minutes for a supported machine and selected model. |
| Recommendation explainability | Every recommendation includes why it fits and what tradeoffs it makes. |
| Benchmark reliability | Benchmark produces repeatable tokens/sec and TTFT measurements. |
| Safe default | No public port is opened without explicit opt-in. |
| Network contribution | A clean installed node can publish a manifest and serve one remote request in the demo. |

---


# 8. Combined MVP and Hackathon Demo Plan

## 8.1 MVP story

> A user installs Sovereign Node, learns what their computer can run, launches a local open model, benchmarks it, opts into sharing, and then a second client routes a paid request to that node through SIP-AI and receives a signed receipt. When the node is paused, the client fails over to another provider.

## 8.2 Demo script

1. Show DecentralizeAI thesis: open AI needs infrastructure without one API chokepoint.
2. Run sin scan on a laptop or GPU box.
3. Run sin recommend for coding or general chat.
4. Install and serve a GGUF model locally.
5. Run sin benchmark and publish a provider manifest.
6. Show manifest anchored locally and optionally on Arweave.
7. From a second terminal, send an OpenAI-compatible chat completion through SIP-AI router.
8. Show quote, payment mode, response, and signed receipt.
9. Pause the first provider. Send the same request again. Show provider failover.
10. Show dashboard: requests, latency, token counts, receipt verification, and provider health.

## 8.3 Recommended hackathon stack

| Layer | Recommended MVP choice | Reason |
| --- | --- | --- |
| CLI | Python or TypeScript | Fast to build, easy SDK integrations. |
| Dashboard | React/Vite or simple local web UI | Enough to demo flows and metrics. |
| Runtime | llama.cpp and/or Ollama | Fastest local path and broad GGUF support [S10, S11, S21]. |
| Provider runtime for remote GPU | vLLM or llama.cpp on Nosana/Akash | Hackathon-aligned compute story [S7, S8, S23]. |
| Registry | Local JSON registry plus Arweave anchor | Simple and competition-aligned [S3, S9]. |
| Payment | Mock x402 plus simulated PIC | Shows both immediate monetization and privacy thesis [S5, S30, S31]. |
| Receipt signing | Ed25519 signatures over canonical JSON | Simple, auditable, enough for MVP. |
| Transport | Direct HTTPS plus relay mode | Demonstrable without building a full anonymity network. |

## 8.4 Repository structure

```text
/sovereign-inference
  /apps
    /dashboard
    /router-demo
  /packages
    /sip-sdk-js
    /sip-sdk-py
    /sin-node
    /sin-cli
    /provider-gateway
    /pic-vouchers
    /receipt-verifier
  /adapters
    /runtime-ollama
    /runtime-llamacpp
    /runtime-vllm
    /provider-nosana
    /provider-akash
  /registry
    /model-manifests
    /provider-manifests
    /arweave-anchor
  /docs
    /protocol-spec
    /prd
    /demo-script
    /threat-model
```

## 8.5 APIs

### OpenAI-compatible path

```text
POST /v1/chat/completions
Authorization: Bearer <local-or-network-token>
X-SIP-Privacy-Mode: private-payment-relay
X-SIP-Budget: 0.01
X-SIP-Verification: signed-receipt

{
  "model": "qwen-coder-7b-instruct-gguf-q4_k_m",
  "messages": [{"role": "user", "content": "Write a small parser."}],
  "max_tokens": 256
}
```

### SIP-specific endpoints

```text
GET  /sip/v1/models
GET  /sip/v1/providers?model=<model_id>
POST /sip/v1/quote
POST /sip/v1/redeem-credit
POST /sip/v1/verify-receipt
GET  /sip/v1/provider-health/<provider_id>
POST /sip/v1/publish-provider-manifest
POST /sip/v1/publish-model-manifest
```

# 9. User Stories and Acceptance Criteria

| Epic | User story | Acceptance criteria | Priority |
| --- | --- | --- | --- |
| Hardware scan | As a local user, I want the app to tell me what my machine can run. | Scan completes and returns clear fit categories for small, medium, and large models. | P0 |
| Model advisor | As a user, I want recommendations for my task, not a giant model list. | At least three ranked recommendations with memory, speed, license, and tradeoff explanation. | P0 |
| Local serving | As a developer, I want a local OpenAI-compatible endpoint. | Existing OpenAI SDK can call localhost endpoint after model starts. | P0 |
| Benchmark | As a provider, I want proof of what my node can serve. | Benchmark produces signed capability manifest with tokens/sec, TTFT, and max context. | P0 |
| Share mode | As a GPU owner, I want to share capacity safely. | Sharing is opt-in, capped, pauseable, and protected by gateway limits. | P0 |
| Routing | As a client, I want one call to find a provider and get a response. | Router resolves provider, gets quote, sends request, and returns response. | P0 |
| Receipts | As a client, I want evidence of what provider served me. | Response includes signed receipt that verifies with CLI. | P0 |
| Payment | As a provider, I want to be paid. | Provider validates x402-like payment or PIC voucher before inference. | P1 |
| Private credits | As a privacy-sensitive user, I do not want my wallet linked to each prompt. | PIC demo separates credit issuance identity from provider redemption metadata. | P1 |
| Provider adapters | As a network operator, I want to plug in Nosana or Akash. | At least one external compute/provider adapter can serve a routed request. | P1 |

# 10. Risk Register

| Risk | Impact | Likelihood | Mitigation |
| --- | --- | --- | --- |
| SIP acronym conflict | Confusion with VoIP protocol | High | Use SIP-AI in technical contexts and avoid sip:// scheme [S4]. |
| Too much overlap with existing decentralized inference projects | Judges see it as derivative | Medium | Position as adapter-first access and provider onboarding layer; demo integrations. |
| Privacy overclaim | Credibility or legal risk | Medium | Use precise claims: reduced linkability, layered transport, no guarantee of undetectability. |
| Payment complexity slows MVP | Demo slips | Medium | Mock x402 and PIC first, document cryptographic upgrade path. |
| Provider abuse or illegal use | Network reputational and legal risk | Medium | Provider policy controls, model allowlists, rate limits, abuse throttles, no default public sharing. |
| Provider node security vulnerability | User machine compromise | Medium | Gateway isolation, no arbitrary remote code/model loads, container sandboxing, least privilege, auto-update path. |
| Latency through private transport | Poor UX | High | Default to direct or relay mode; private transport is opt-in with warning. |
| Model licensing mistakes | Commercial/legal risk | Medium | Model catalog stores license flags and warnings; provider must accept license terms before serving. |
| Cold start supply problem | No providers available | Medium | SIN makes provider onboarding easy; also integrate existing compute networks. |
| Verification weaker than users assume | Trust gap | Medium | Call receipts accountability artifacts, not full cryptographic proof of model execution. |

# 11. Hackathon and Go-to-Market Strategy

## Hackathon positioning

For DecentralizeAI, the best framing is not that Sovereign Inference invents decentralized inference from scratch. The stronger framing is that decentralized AI already has compute, model, payment, storage, and privacy primitives, but users still lack a simple way to run open models locally and safely contribute capacity to a provider-neutral inference network. DecentralizeAI explicitly values real implementation, originality, impact, and verifiable evidence [S2, S3].

## Suggested HackerNoon article sequence

1. Open Inference Without Chokepoints: Why Open Models Still Need an Access Protocol
2. From Laptop to Inference Provider: Building the Sovereign Inference Node
3. Private Inference Credits: Paying for AI Without Linking Wallets to Prompts
4. What We Measured: Benchmarks, Failover, Receipts, and Lessons from a Decentralized Inference Demo

## Business model options

| Model | Description | Pros | Cons |
| --- | --- | --- | --- |
| Protocol fee | Small fee on routed marketplace inference. | Aligned with usage. | Can conflict with neutrality if too extractive. |
| Hosted router | Managed router for apps that do not want to self-host. | Immediate SaaS path. | Creates a semi-centralized service unless self-hosting remains first-class. |
| Enterprise Sovereign Node | Paid desktop/server node with policy, audit, and team management. | Fits agencies, NGOs, regulated teams, and companies. | Longer sales cycle. |
| Provider tooling | Premium dashboards, alerts, benchmarking, and earnings optimization. | Monetizes supply side. | Needs provider scale. |
| Protocol token | Network-level token for settlement/governance. | Can bootstrap incentives. | Adds regulatory, distraction, and credibility risk. Defer. |

## Recommended first GTM

Start as an open-source developer tool and hackathon project, then evolve into a managed router and premium node management layer. Avoid leading with a token. Lead with working infrastructure, measurable performance, open manifests, and a clear path to private credits.

# 12. Roadmap

| Phase | Time horizon | Deliverables |
| --- | --- | --- |
| Phase 0: Spec and proof of concept | Week 1 | Protocol spec v0.1, model/provider manifest schemas, receipt format, CLI skeleton. |
| Phase 1: Local node | Weeks 2-3 | Hardware scan, model advisor, local llama.cpp/Ollama serving, benchmark, dashboard. |
| Phase 2: Network routing | Weeks 3-4 | Provider registry, routing, quote, direct request, signed receipts, failover. |
| Phase 3: Payment demo | Weeks 4-5 | Mock x402, PIC voucher issuance/redeem/settle flow, provider accounting. |
| Phase 4: Decentralized integration | Weeks 5-6 | Arweave manifest anchor, one compute/provider adapter such as Nosana or Akash, published demo metrics. |
| Phase 5: Privacy modes | Post-MVP | Relay hardening, Tor/I2P/Nym transport experiments, TEE-capable provider metadata. |
| Phase 6: Production hardening | Post-hackathon | Security review, signed releases, plugin SDK, policy framework, provider reputation. |

# 13. Decision Log

| Decision | Status | Rationale |
| --- | --- | --- |
| Build both SIP-AI and SIN. | Accepted | Demand side needs routing; supply side needs easy provider onboarding. |
| One provider handles one complete request in v1. | Accepted | Avoids latency, sharding, accountability, and verification complexity. |
| Use existing runtimes instead of building a new inference engine. | Accepted | Ollama, llama.cpp, vLLM, SGLang, LocalAI, and LM Studio already solve core serving [S10-S15]. |
| Use Arweave for public manifests, not private prompts. | Accepted | Permanent provenance fits Arweave; prompt privacy requires local/private storage [S9]. |
| Use x402 for direct payment and PIC for privacy-preserving payment. | Accepted | x402 is simple for APIs; PIC addresses wallet-request linkage [S5, S30, S31]. |
| Use SIP-AI externally instead of raw SIP acronym where ambiguity matters. | Proposed | Avoids conflict with Session Initiation Protocol [S4]. |

# 14. Open Questions

- Should the public brand use SIN, Sovereign Node, or both depending on audience?
- Which runtime gets first-class support first: Ollama for UX, llama.cpp for reproducibility, or both?
- Which external provider adapter should be first: Nosana for hackathon alignment, Akash for decentralized cloud breadth, or Chutes/LibertAI/NodeGhost for inference-specific alignment?
- Should PIC start as a Cashu-like ecash mint, a Privacy Pass-like token issuer, or a custom voucher service with a future cryptographic upgrade path?
- What are the default model safety and logging policies for public sharing?
- What minimum uptime and benchmark requirements should a node meet before being discoverable by default?
- Should provider reputation be public, pseudonymous, or local to each router at first?
- What model license metadata is required before a model can be listed for paid inference?

# 15. Glossary

| Term | Definition |
| --- | --- |
| SIP-AI | Sovereign Inference Protocol, the routing, payment, manifest, transport, and receipt protocol. |
| SIN | Sovereign Inference Node, the local-first installable node for running and optionally sharing models. |
| PIC | Private Inference Credit, a voucher or token used to pay for inference without directly linking the provider request to the original wallet purchase. |
| Model manifest | Public metadata about a model artifact, hash, format, quantization, license, runtime support, and recommended settings. |
| Provider manifest | Signed metadata about a node, supported models, price, runtime, benchmark, policy, privacy modes, and public key. |
| Signed inference receipt | Provider-signed accountability record for an inference request. |
| Provider gateway | Hardened service that sits in front of the actual model runtime and handles auth, policy, payment, limits, and receipts. |
| Runtime adapter | Connector to a local or remote model engine such as llama.cpp, Ollama, vLLM, SGLang, LocalAI, or LM Studio. |

# 16. Appendix: Source References

**[S1] DecentralizeAI Hackathon homepage.** DecentralizeAI describes the hackathon around open, transparent, user-owned AI infrastructure, including distributed compute, open inference systems, permanent storage, verifiable AI, and sovereignty-focused tooling. URL: https://decentralizeai.tech/

**[S2] DecentralizeAI Judges page.** The judging rubric emphasizes deep technical understanding, novel insights, real-world impact, research and evidence, and clear communication. URL: https://decentralizeai.tech/judges

**[S3] DecentralizeAI FAQ.** The FAQ names decentralized GPU orchestration, permanent model storage, verifiable systems, open inference infrastructure, and data sovereignty tooling as eligible project areas, and says mockups without demos do not qualify. URL: https://decentralizeai.tech/faq

**[S4] IETF RFC 3261.** RFC 3261 defines SIP as the Session Initiation Protocol for creating, modifying, and terminating multimedia sessions. URL: https://datatracker.ietf.org/doc/html/rfc3261

**[S5] x402 official documentation.** x402 is an open payment standard that uses HTTP 402 Payment Required to charge for APIs and content over HTTP. URL: https://docs.x402.org/introduction

**[S6] Coinbase x402 documentation.** Coinbase describes x402 as instant automatic stablecoin payments directly over HTTP without accounts, sessions, or complex authentication. URL: https://docs.cdp.coinbase.com/x402/welcome

**[S7] Nosana GPU Marketplace.** Nosana positions itself as an on-demand distributed GPU cloud where users can run workloads or earn by sharing GPUs. URL: https://nosana.com/

**[S8] Nosana host docs.** Nosana host documentation describes GPU hosts listing NVIDIA GPUs on the marketplace for AI inference and other compute workloads. URL: https://learn.nosana.com/hosts/grid.html

**[S9] Arweave official site.** Arweave describes itself as a global, permissionless hard drive for permanent data storage. URL: https://www.arweave.org/

**[S10] Ollama OpenAI compatibility docs.** Ollama documents OpenAI-compatible API support. URL: https://docs.ollama.com/api/openai-compatibility

**[S11] llama.cpp HTTP server docs.** llama.cpp server provides REST APIs, OpenAI-compatible chat, responses, and embeddings routes, and supports quantized inference on CPU and GPU. URL: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md

**[S12] vLLM OpenAI-compatible server docs.** vLLM provides an OpenAI-compatible HTTP server for serving models. URL: https://docs.vllm.ai/en/stable/serving/online_serving/

**[S13] SGLang documentation.** SGLang is a production-serving framework compatible with Hugging Face and OpenAI APIs. URL: https://docs.sglang.ai/

**[S14] LocalAI overview.** LocalAI is an OpenAI-compatible local and on-prem engine for multiple model families and backends. URL: https://localai.io/

**[S15] LM Studio developer docs.** LM Studio can serve local models over REST, SDKs, and OpenAI/Anthropic-compatible endpoints. URL: https://lmstudio.ai/docs/developer

**[S16] Jan official site.** Jan is an open-source local AI app that runs open-source models locally or connects to cloud providers. URL: https://jan.ai/

**[S17] RamaLama GitHub.** RamaLama simplifies local model serving through containers and can pull models from different sources. URL: https://github.com/containers/ramalama

**[S18] RamaLama PyPI docs.** RamaLama inspects the system for GPU support and falls back to CPU if needed. URL: https://pypi.org/project/ramalama/0.8.1/

**[S19] Exo GitHub.** Exo connects devices into a local AI cluster and targets running models across everyday hardware. URL: https://github.com/exo-explore/exo

**[S20] Petals paper.** Petals demonstrates collaborative inference and fine-tuning of large models by chaining servers that host model parts. URL: https://arxiv.org/abs/2209.01188

**[S21] Hugging Face GGUF docs.** Hugging Face supports GGUF metadata inspection and notes usage with llama.cpp, LM Studio, GPT4All, and Ollama. URL: https://huggingface.co/docs/hub/en/gguf

**[S22] Chutes official site.** Chutes describes decentralized serverless AI compute for open-source model inference and workloads. URL: https://chutes.ai/

**[S23] Akash Network.** Akash is an open decentralized compute marketplace where users buy and sell computing resources. URL: https://akash.network/

**[S24] LibertAI decentralized LLM page.** LibertAI describes decentralized LLM inference on Aleph Cloud with independent node operators and no single point of failure. URL: https://libertai.io/decentralized-llm

**[S25] Morpheus official site.** Morpheus describes a peer-to-peer open-source AI network where providers can run models on GPUs and earn MOR. URL: https://mor.org/

**[S26] NodeGhost official site.** NodeGhost describes an OpenAI-compatible decentralized AI inference gateway with requests routed through a decentralized network. URL: https://nodeghost.ai/

**[S27] Tor Snowflake.** Snowflake is a Tor-powered censorship circumvention system using volunteer routing. URL: https://snowflake.torproject.org/

**[S28] I2P official site.** I2P is a decentralized, privacy-focused network routing traffic through encrypted layers across volunteer nodes. URL: https://i2p.net/

**[S29] Nym official site.** Nym presents a decentralized VPN with mixnet technology for metadata protection. URL: https://nym.com/

**[S30] Cashu official site.** Cashu is an open-source Chaumian ecash protocol using digital bearer tokens stored on the user device. URL: https://cashu.space/

**[S31] Privacy Pass Architecture RFC 9576.** Privacy Pass defines a privacy-preserving token architecture involving clients, origins, issuers, and attesters. URL: https://datatracker.ietf.org/doc/rfc9576/

**[S32] Modal VRAM guide.** Modal provides a simple rule of thumb for inference memory, such as roughly 2GB VRAM per 1B parameters for FP16. URL: https://modal.com/blog/how-much-vram-need-inference

**[S33] Hugging Face Accelerate model memory estimator.** Accelerate includes a model memory estimator for calculating memory needs for inference and training. URL: https://huggingface.co/docs/accelerate/en/usage_guides/model_size_estimator

**[S34] Hugging Face Transformers KV cache docs.** Transformers documentation notes that KV cache can occupy significant memory, especially for long-context generation. URL: https://huggingface.co/docs/transformers/en/kv_cache

**[S35] Targon confidential compute.** Targon describes decentralized compute using trusted execution environments and Intel TDX. URL: https://targon.com/

**[S36] Atoma confidential AI.** Atoma positions itself around confidential computing for private AI inference and related workloads. URL: https://atoma.ai/
