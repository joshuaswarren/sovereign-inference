# Opportunity

Why open AI access still needs an orchestration layer, why now is the moment, and how Sovereign Inference builds on the existing decentralized AI stack rather than competing with every piece of it.

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

## Current landscape and build-on strategy

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

That workflow-first framing is the differentiator. Rather than treating Nosana, Akash, Ollama, llama.cpp, Arweave, x402, or Cashu as rivals, Sovereign Inference treats them as composable backends behind a single provider-neutral interface, and adds the missing usability, onboarding, payment, and trust glue on top.

See also: [Vision](vision.md), [Naming and Brand](naming-and-brand.md), [Product Principles](product-principles.md).

_Derived from the v0.1.2 Product Requirements Package._
