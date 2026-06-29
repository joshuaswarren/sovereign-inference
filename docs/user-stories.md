# User Stories and Acceptance Criteria

The user stories and acceptance criteria that define Milestone 1 of Sovereign Inference, grouped by epic. Each story carries a priority (P0 must ship for the first milestone; P1 follows closely).

## Local node (hardware, advisor, serving, benchmark)

| Epic | User story | Acceptance criteria | Priority |
| --- | --- | --- | --- |
| Hardware scan | As a local user, I want the app to tell me what my machine can run. | Scan completes and returns clear fit categories for small, medium, and large models. | P0 |
| Model advisor | As a user, I want recommendations for my task, not a giant model list. | At least three ranked recommendations with memory, speed, license, and tradeoff explanation. | P0 |
| Local serving | As a developer, I want a local OpenAI-compatible endpoint. | Existing OpenAI SDK can call localhost endpoint after model starts. | P0 |
| Benchmark | As a provider, I want proof of what my node can serve. | Benchmark produces signed capability manifest with tokens/sec, TTFT, and max context. | P0 |

## Sharing and routing

| Epic | User story | Acceptance criteria | Priority |
| --- | --- | --- | --- |
| Share mode | As a GPU owner, I want to share capacity safely. | Sharing is opt-in, capped, pauseable, and protected by gateway limits. | P0 |
| Routing | As a client, I want one call to find a provider and get a response. | Router resolves provider, gets quote, sends request, and returns response. | P0 |
| Receipts | As a client, I want evidence of what provider served me. | Response includes signed receipt that verifies with CLI. | P0 |

## Payment and privacy

| Epic | User story | Acceptance criteria | Priority |
| --- | --- | --- | --- |
| Payment | As a provider, I want to be paid. | Provider validates x402-like payment or PIC voucher before inference. | P1 |
| Private credits | As a privacy-sensitive user, I do not want my wallet linked to each prompt. | PIC demo separates credit issuance identity from provider redemption metadata. | P1 |

## Provider integrations

| Epic | User story | Acceptance criteria | Priority |
| --- | --- | --- | --- |
| Provider adapters | As a network operator, I want to plug in Nosana or Akash. | At least one external compute/provider adapter can serve a routed request. | P1 |

## Related docs

- [mvp-and-demo.md](mvp-and-demo.md) — how these stories come together in the demo.
- [roadmap.md](roadmap.md) — the build phases that deliver these stories.
- [glossary.md](glossary.md) — term definitions (SIP-AI, SIN, PIC, manifests, receipts).

_Derived from the v0.1.2 Product Requirements Package._
