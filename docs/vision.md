# Vision

Sovereign Inference is the access and supply layer for open AI: a neutral protocol (SIP-AI) plus a local-first node (SIN) that let anyone run the best open model their hardware can handle and, optionally, share that capacity through a privacy-preserving, censorship-resistant network.

## One-line pitch

> Sovereign Inference lets anyone run the best open model their hardware can handle, and optionally share that capacity through a privacy-preserving, censorship-resistant open inference network.

## The problem

Open-source AI access is fragile. Model weights may be open, but most people still depend on centralized APIs, centralized clouds, app-store-controlled clients, blocked websites, or hardware they cannot afford. Running locally is powerful, but it is still too hard for ordinary users. Serving to others is even harder: providers need to pick models, install runtimes, secure endpoints, price requests, measure capacity, handle payment, and earn trust.

Sovereign Inference solves both sides of this open AI access problem with two tightly linked products.

## The two-product bundle

The system pairs a demand-side protocol with a supply-side node so that access and capacity grow together.

- **SIP-AI** (Sovereign Inference Protocol) is the neutral protocol layer for model discovery, provider selection, privacy-preserving payments, transport modes, inference receipts, and routing across decentralized or self-hosted providers.
- **SIN** (Sovereign Inference Node) is the local-first node that helps people inspect their hardware, choose the right open model, download it, run it locally, benchmark it, and optionally offer spare capacity to the network.

| Product | Audience | Primary job | Milestone proof |
| --- | --- | --- | --- |
| SIP-AI | Developers, apps, routers, marketplaces | Route paid inference to open models without one API chokepoint | OpenAI-compatible request routed to a provider with signed receipt and test payment |
| SIN | Individuals, homelab owners, GPU providers, small teams | Choose, install, run, benchmark, and share open models | Scan hardware, recommend model, run local server, publish provider manifest |

## The non-negotiable v1 constraint

Each inference request is handled by **one selected provider node or server**. There is no public model sharding across multiple unrelated nodes in v1. Failover happens between providers, not within one model execution.

This is deliberately *not* Petals-style distributed model execution, where several unrelated users combine GPUs to serve one prompt. Petals is important prior art for collaborative inference, but SIP-AI v1 routes one user request to one provider node that has the full selected model available [S20]. This constraint keeps latency, security, provider accountability, and verification tractable.

## The core novelty: the orchestration layer

The novelty is not a new GPU marketplace, a new local model runner, or a new anonymity network. The novelty is the **orchestration layer** that makes existing pieces composable, safe, usable, and provider-neutral.

Most projects start from one layer: a compute market, a model runner, a decentralized gateway, or a privacy network. Sovereign Inference starts from the user workflow and the provider onboarding workflow. It asks: what model should I run, will it fit, can I serve it safely, who can find it, how do I get paid, and how does a user know what happened?

> Sovereign Inference is the access and supply layer for open AI: local-first when possible, decentralized when needed, provider-neutral by design.

## What we are building (for real)

This is a real, production-bound system. The first milestone is a working, demonstrable implementation, and every part of it is designed to evolve into its production version rather than remaining a throwaway demo. The real system goals are:

- A provider-neutral protocol and SDK that route open-model inference across local, decentralized, and self-hosted providers through an OpenAI-compatible interface, with real provider selection, quotes, and failover.
- A local-first node that genuinely inspects hardware, recommends and installs models, serves them locally, benchmarks them, and lets owners safely contribute spare capacity.
- Real payment rails: x402-style direct payment as the first implementable step, with Private Inference Credits (PIC) as the privacy-preserving credit primitive on a defined path to a full cryptographic implementation.
- Signed inference receipts as verifiable accountability artifacts, with a clear upgrade path toward stronger verification and confidential-compute (TEE) trust modes.
- Durable public provenance via permanent storage (Arweave) for model and provider manifests, while user prompts stay private and local.

Where the first milestone uses a mock or simulated component (for example, mock x402 or simulated PIC vouchers), that is the first implementable step toward the real cryptographic/production version, with the privacy boundary and upgrade path defined up front. Nothing here is claimed as finished that is not.

## Why it fits the hackathon

The hackathon wedge is strong because DecentralizeAI explicitly highlights distributed compute, edge/local inference, open inference protocols, permanent storage, verifiable AI, and data sovereignty tooling as part of the desired decentralized AI stack [S1, S2, S3]. The competition rewards real infrastructure contributions with verifiable evidence, not conceptual essays. Sovereign Inference is built around exactly that: working code, measurements, traces, manifests, and reproducible demos.

The product thesis: anyone should be able to run open AI privately, and anyone with spare hardware should be able to become a safe, benchmarked, compensated inference provider without learning CUDA deployment, model quantization, runtime tuning, crypto settlement, or server hardening.

See also: [Opportunity](opportunity.md), [Product Principles](product-principles.md), [Naming and Brand](naming-and-brand.md).

_Derived from the v0.1.2 Product Requirements Package._
