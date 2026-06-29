# Evidence Plan

This is the verifiable-evidence plan for the Sovereign Inference entry in the [DecentralizeAI hackathon](https://decentralizeai.tech/). The hackathon disqualifies mockups, undemonstrated prototypes, and unreleased projects, and requires working code, a deployment URL, or reproducible metrics. So every public claim we make is bound to a concrete artifact, with a repo location and a reproduction path a judge can follow. Where a Milestone 1 component is simulated (for example, mock x402 or simulated PIC vouchers), we say so and label it as a first implementable step, not a finished feature.

## Claim-to-artifact map

| Claim we make | Artifact that proves it | Where it lives in the repo | How a judge reproduces it |
| --- | --- | --- | --- |
| Runs on real hardware (not slides) | `sin scan` output + machine-readable hardware profile | [`../../packages/sin-cli`](../../packages/sin-cli), [`../../packages/sin-node`](../../packages/sin-node) | Install the node, run `sin scan`; confirm it reports CPU/RAM/GPU/VRAM/disk and existing runtimes for the host. |
| Gives transparent model recommendations | Ranked recommendations with memory, speed, license, and tradeoff explanation | [`../../packages/sin-node`](../../packages/sin-node) | Run `sin recommend --task coding --privacy local --latency balanced`; confirm at least three ranked options each with a "why it fits" line. |
| Serves a local OpenAI-compatible endpoint | A localhost endpoint callable by a standard OpenAI SDK | [`../../packages/sin-node`](../../packages/sin-node), [`../../adapters/runtime-llamacpp`](../../adapters/runtime-llamacpp), [`../../adapters/runtime-ollama`](../../adapters/runtime-ollama) | Run `sin serve --local`; send a chat completion from an OpenAI-compatible client to the localhost endpoint and get a response. |
| Produces reproducible benchmark metrics | Committed benchmark JSON (tokens/sec, TTFT, max stable context, memory) | [`../../packages/sin-node`](../../packages/sin-node), benchmark output in repo | Run `sin benchmark`; compare emitted JSON against the committed reference; numbers should be repeatable within tolerance. |
| Signs a capability/provider manifest | Signed provider manifest published to the local registry | [`../../packages/provider-gateway`](../../packages/provider-gateway), [`../../registry/provider-manifests`](../../registry/provider-manifests) | Run `sin share ...`; inspect the published provider manifest and verify its Ed25519 signature against the provider public key. |
| Receipts verify | `sin verify-receipt` / `sip-receipt verify` CLI output + passing test suite | [`../../packages/receipt-verifier`](../../packages/receipt-verifier) | Run `sin verify-receipt receipt.json` on demo receipts (expect a pass) and on a tampered receipt (expect a fail); run the receipt-verifier test suite. |
| Router selects a provider and returns a response | Router resolves provider, gets a quote, sends request, returns response | [`../../packages/router`](../../packages/router), [`../../apps/router-demo`](../../apps/router-demo) | Run the router demo; one OpenAI-compatible call resolves a provider, shows a quote, and returns a response with a receipt. |
| Provider failover works | Recorded terminal session + router logs showing the switch | [`../../packages/router`](../../packages/router), [`../../logs`](../../logs), recorded demo | Start two providers, send a request (succeeds), stop the first provider, send the same request; the client succeeds via the second provider, and router logs show the failover. |
| Decentralized compute serves a routed request | Nosana provider deployment URL + recorded run | [`../../adapters/provider-nosana`](../../adapters/provider-nosana) | Deploy the provider on Nosana GPU using the adapter; route a request from SIP-AI to the Nosana-hosted provider; confirm a response and signed receipt; the deployment URL is the evidence. |
| Public provenance is durable | Arweave manifest anchor (transaction ID) for a model and a provider manifest | [`../../registry/arweave-anchor`](../../registry/arweave-anchor), [`../../registry/model-manifests`](../../registry/model-manifests), [`../../registry/provider-manifests`](../../registry/provider-manifests) | Anchor at least one model manifest and one provider manifest; resolve them by their recorded Arweave transaction IDs. |
| Direct payment path works | Mock x402 flow on a routed request | [`../../packages/router`](../../packages/router), [`../../apps/router-demo`](../../apps/router-demo) | Run a routed request in direct-pay mode; confirm the gateway validates the (mock) x402 payment before inference. Labeled as mock / first implementable step. |
| Wallet is not linked to each prompt | Recorded PIC flow separating issuance from redemption | [`../../packages/pic-vouchers`](../../packages/pic-vouchers) | Issue test credits, redeem one with a provider, settle; confirm the provider does not learn the original purchase ID. Labeled as simulated voucher system with a defined cryptographic upgrade path. |
| Safe by default | Evidence that no public port opens without explicit opt-in | [`../../packages/sin-node`](../../packages/sin-node), [`../../packages/provider-gateway`](../../packages/provider-gateway) | Run `sin serve --local` and confirm the endpoint binds to localhost only; sharing requires an explicit `sin share` opt-in. |
| Metrics are observable | Dashboard showing latency, TTFT, tokens/sec, cost, receipt status, provider health | [`../../apps/dashboard`](../../apps/dashboard) | Open the dashboard during a routed run; confirm it displays live request metrics and provider health. |

## Reproduction notes for judges

- **Single happy-path run.** The fastest end-to-end check follows the demo script in [`../mvp-and-demo.md`](../mvp-and-demo.md): `sin scan` → `sin recommend` → install/serve a GGUF model → `sin benchmark` → publish manifest → route a request from a second terminal → show quote, payment, response, and signed receipt → pause the provider → repeat the request to see failover.
- **Receipt fields and verification rules** are defined in [`../spec/protocol-spec.md`](../spec/protocol-spec.md); the verifier in [`../../packages/receipt-verifier`](../../packages/receipt-verifier) checks the signature, manifest references, token counts, and response hash.
- **Recorded artifacts** (terminal sessions, benchmark JSON, router logs, deployment URL, Arweave transaction IDs) are linked from the follow-up article, [Article 4 in the series plan](article-series.md).

## Honesty guardrails

- We describe signed receipts as **accountability artifacts**, not as cryptographic proof that a specific model produced a specific answer.
- We never claim traffic is undetectable or unblockable; privacy claims are stated as reduced linkability and layered resilience with explicit tradeoffs.
- Simulated or mocked components (mock x402, simulated PIC vouchers) are labeled as such everywhere they appear, with their real upgrade path noted.
- A claim only appears in an article or the submission once its artifact in this table exists and reproduces.

See also: [DecentralizeAI submission plan](decentralizeai-submission.md), [Article series plan](article-series.md).

_Derived from the v0.1.2 Product Requirements Package._
