# MVP and Hackathon Demo Plan

Milestone 1 of Sovereign Inference: a real, end-to-end build that routes a paid, signed-receipt inference request to a self-hosted Sovereign Inference Node (SIN) and fails over when that node is paused. This page describes the first shippable milestone, the demo that proves it, the stack we are building it on, the repository layout, and the public APIs.

## Framing: Milestone 1 of a production-bound system

The scope below is the **first milestone** of the full Sovereign Inference Protocol (SIP-AI) and Sovereign Inference Node (SIN), not a throwaway prototype. Every component named here is being built for real and is on the path to the complete system described across the rest of these docs. Where a capability ships in a deliberately simple form for Milestone 1 (for example a local-first credit voucher path or a relay transport before mixnet adapters), the simpler form is the working first version with a documented upgrade path, not a stub. Nothing here is claimed as finished before it is.

## MVP story

> A user installs Sovereign Node, learns what their computer can run, launches a local open model, benchmarks it, opts into sharing, and then a second client routes a paid request to that node through SIP-AI and receives a signed receipt. When the node is paused, the client fails over to another provider.

## Demo script (10 steps)

1. Show the DecentralizeAI thesis: open AI needs infrastructure without one API chokepoint [S1, S2, S3].
2. Run `sin scan` on a laptop or GPU box.
3. Run `sin recommend` for coding or general chat.
4. Install and serve a GGUF model locally.
5. Run `sin benchmark` and publish a provider manifest.
6. Show the manifest anchored locally and optionally on Arweave [S9].
7. From a second terminal, send an OpenAI-compatible chat completion through the SIP-AI router.
8. Show the quote, payment mode, response, and signed receipt.
9. Pause the first provider. Send the same request again. Show provider failover.
10. Show the dashboard: requests, latency, token counts, receipt verification, and provider health.

## Recommended hackathon stack

| Layer | Recommended MVP choice | Reason |
| --- | --- | --- |
| CLI | Python or TypeScript | Fast to build, easy SDK integrations. |
| Dashboard | React/Vite or simple local web UI | Enough to demo flows and metrics. |
| Runtime | llama.cpp and/or Ollama | Fastest local path and broad GGUF support [S10, S11, S21]. |
| Provider runtime for remote GPU | vLLM or llama.cpp on Nosana/Akash | Hackathon-aligned compute story [S7, S8, S23]. |
| Registry | Local JSON registry plus Arweave anchor | Simple and competition-aligned [S3, S9]. |
| Payment | x402 flow plus Private Inference Credit voucher path | Shows both immediate monetization and the privacy thesis [S5, S30, S31]. |
| Receipt signing | Ed25519 signatures over canonical JSON | Simple, auditable, enough for Milestone 1. |
| Transport | Direct HTTPS plus relay mode | Demonstrable without building a full anonymity network. |

## Repository structure

The repository is a monorepo with Python packages for the protocol core and a JavaScript SDK and web apps for the client-facing surfaces. The layout below reflects the real `sovereign-inference` repository.

```text
/sovereign-inference
  /docs                      # This documentation set (specs, PRD, threat model, demo, references)
  /packages                  # Python packages: the protocol core
    /sip-protocol            # SIP-AI types, manifests, quote/receipt schemas, request lifecycle
    /receipt-verifier        # Ed25519 signed-receipt verification library + verifier CLI
    /pic-vouchers            # Private Inference Credit issuance, redemption, settlement
    /provider-gateway        # Hardened front door: auth, quotas, policy, receipt generation
    /router                  # Provider scoring, quotes, selection, failover
    /sin-node                # Sovereign Inference Node: scan, recommend, serve, benchmark, share
    /sin-cli                 # `sin` command-line interface
  /adapters                  # Runtime and external-provider adapters
    /runtime-ollama
    /runtime-llamacpp
    /runtime-vllm
    /provider-nosana
    /provider-akash
  /sdk-js                    # JavaScript/TypeScript client SDK
  /apps
    /dashboard               # Local web dashboard (health, earnings, receipts, pause/resume)
    /router-demo             # Demo client that routes an OpenAI-compatible request
  /registry                  # Model and provider manifests + durable anchoring
    /model-manifests
    /provider-manifests
    /arweave-anchor
  /examples                  # Runnable examples for SDKs and CLI flows
  /scripts                   # Build, benchmark, and demo automation
  /.github                   # CI workflows and issue/PR templates
```

## APIs

Milestone 1 exposes two API surfaces: an OpenAI-compatible path for drop-in adoption, and SIP-specific endpoints for discovery, quotes, payment, receipts, health, and manifest publication.

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

The `X-SIP-*` headers carry SIP-AI routing intent (privacy mode, budget, verification level) alongside an otherwise standard OpenAI chat completion request, so existing OpenAI SDKs work without modification.

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

## Success criteria for Milestone 1

The demo is considered successful when a clean developer machine reaches a routed inference in under ten minutes, the client fails over after one provider is stopped, every successful request returns a verifiable signed receipt, at least one direct x402-style and one Private Inference Credit redemption flow run, at least two runtime/provider adapters are demonstrated, and the dashboard surfaces latency, TTFT, tokens/sec, cost, receipt status, and provider health.

## Related docs

- [user-stories.md](user-stories.md) — epics, stories, and acceptance criteria behind this milestone.
- [roadmap.md](roadmap.md) — the phases that build up to and beyond Milestone 1.
- [threat-model.md](threat-model.md) — security and abuse controls referenced in the demo.
- [glossary.md](glossary.md) — definitions for SIP-AI, SIN, PIC, and related terms.
- [references.md](references.md) — sources behind the [S#] citations above.

_Derived from the v0.1.2 Product Requirements Package._
