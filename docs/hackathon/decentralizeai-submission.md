# DecentralizeAI Submission Plan

This is the master plan for entering Sovereign Inference into the [DecentralizeAI hackathon](https://decentralizeai.tech/). It maps our work to the hackathon's named project areas, shows how we satisfy each judging criterion with concrete repo artifacts, lists the verifiable evidence we will ship, and sets out a checklist and timeline for Round 1 (June–October 2026). Milestone 1 (the demonstrable implementation) is the hackathon entry; it is the first step of a real, production-bound project, not the finish line.

## a. Why Sovereign Inference fits DecentralizeAI

DecentralizeAI is about open, transparent, community-owned AI infrastructure. We do not claim to invent decentralized inference; we build the orchestration layer that makes existing decentralized primitives composable, safe, and usable. Each of the hackathon's named project areas maps directly onto work in this repo.

| DecentralizeAI project area | What we ship | Where it lives in the repo |
| --- | --- | --- |
| **Open inference infrastructure** | A provider-neutral protocol (SIP-AI) and SDK with an OpenAI-compatible chat-completions path, plus SIP-specific quote, receipt, and provider endpoints. No single API chokepoint. | [`../../README.md`](../../README.md), [`../spec/protocol-spec.md`](../spec/protocol-spec.md), [`../../packages/sip-protocol`](../../packages/sip-protocol), [`../../packages/router`](../../packages/router), [`../../sdk-js`](../../sdk-js) |
| **Decentralized GPU orchestration** | A router that selects one provider per request and fails over between providers, with adapters for decentralized compute markets (Nosana, Akash) as optional provider backends, not competitors. | [`../../packages/router`](../../packages/router), [`../../adapters/provider-nosana`](../../adapters/provider-nosana), [`../../adapters/provider-akash`](../../adapters/provider-akash) |
| **Permanent model storage (Arweave)** | Model and provider manifests anchored to permanent storage via an Arweave anchor, so provenance survives even when an origin disappears. Prompts stay private and local; only public provenance is anchored. | [`../../registry/model-manifests`](../../registry/model-manifests), [`../../registry/provider-manifests`](../../registry/provider-manifests), [`../../registry/arweave-anchor`](../../registry/arweave-anchor) |
| **Verifiable / reproducible AI** | Ed25519-signed inference receipts that bind provider key, model-manifest hash, runtime version, token counts, price, and response hash; a standalone verifier CLI; reproducible benchmark JSON. | [`../../packages/receipt-verifier`](../../packages/receipt-verifier), [`../../packages/provider-gateway`](../../packages/provider-gateway) |
| **Data sovereignty tooling** | A local-first node (SIN) that runs models on the user's own hardware, binds to localhost by default, opens no public port without explicit opt-in, and keeps prompts off any public registry. | [`../../packages/sin-node`](../../packages/sin-node), [`../../packages/sin-cli`](../../packages/sin-cli), [`../../packages/provider-gateway`](../../packages/provider-gateway) |

The connective thesis: decentralized AI already has compute, model, payment, storage, and privacy primitives, but users still lack a simple way to run open models locally and safely contribute capacity to a provider-neutral inference network. Sovereign Inference is that access-and-supply layer.

## b. How we satisfy each judging criterion

The hackathon qualifies entries on technical depth, originality, impact, and verifiable evidence. Each is answered with concrete pointers, not assertions.

### Technical depth — genuine implementation, not theory

- A working OpenAI-compatible router with provider scoring, quotes, and real failover between providers. See [`../mvp-and-demo.md`](../mvp-and-demo.md) and [`../architecture.md`](../architecture.md).
- Signed-receipt generation and an independent verifier that checks signatures, manifest references, token counts, and response hash. See [`../spec/protocol-spec.md`](../spec/protocol-spec.md) and [`../../packages/receipt-verifier`](../../packages/receipt-verifier).
- A local node that performs real hardware detection, memory-fit estimation (weights + KV-cache headroom), model fetch/verify, local serving, and benchmarking. See [`../architecture.md`](../architecture.md).
- Adapter-first design: runtimes (llama.cpp, Ollama) and providers (Nosana, Akash) are plugins, demonstrating at least two runtime/provider paths.

### Originality — addresses unsolved problems

- Most projects start from one layer (a compute market, a model runner, a gateway, or a privacy network). We start from the **user workflow and the provider-onboarding workflow** and stitch the layers together. See [`../../README.md`](../../README.md) and [`../architecture.md`](../architecture.md).
- Private Inference Credits (PIC): a payment primitive that separates credit purchase from credit redemption so a wallet is not linked to each prompt. See [`../spec/protocol-spec.md`](../spec/protocol-spec.md).
- Signed inference receipts framed honestly as **accountability artifacts**, with a defined upgrade path toward stronger verification and TEE-backed confidential compute — not overclaimed as cryptographic proof of model execution.

### Impact — meaningfully advances the decentralized AI stack

- Lowers the barrier so anyone with spare hardware can become a safe, benchmarked, compensated provider without learning CUDA deployment, quantization, settlement, or server hardening.
- Gives developers a drop-in open-inference endpoint with routing and failover across local, decentralized, and self-hosted providers — reducing dependence on any single API vendor.
- Strengthens existing networks (Nosana, Akash, and others) by making them reachable through one neutral protocol rather than competing with them.

### Verifiable evidence — working code, deployment URL, reproducible metrics

Mockups and undemonstrated prototypes are ineligible, so every claim is tied to a reproducible artifact. The full mapping lives in [`evidence-plan.md`](evidence-plan.md). Headline evidence:

- Working CLI flows (`sin scan`, `sin recommend`, `sin serve`, `sin benchmark`, `sin share`).
- `sip-receipt verify` CLI output plus a passing test suite for receipt verification.
- Reproducible benchmark JSON (tokens/sec, TTFT, max stable context, memory).
- A recorded failover demo with router logs.
- A deployment URL for a real remote provider node (Nosana) plus a recorded end-to-end demo.

## c. The evidence we will ship

| Evidence artifact | What it proves | Reproduced by |
| --- | --- | --- |
| Working CLI (SIN + SIP) | The system runs end to end on real hardware, not slides. | `sin scan`, `sin recommend`, `sin serve --local`, `sin benchmark` |
| Signed-receipt verifier | Receipts are real, verifiable accountability artifacts. | `sin verify-receipt receipt.json` / `sip-receipt verify` + test suite |
| Reproducible benchmark metrics | Performance numbers are measured, not asserted. | `sin benchmark` emitting committed benchmark JSON |
| Failover demo | The router survives a provider going down. | Recorded terminal session + router logs |
| Deployment URL / recorded demo | Decentralized compute actually serves a routed request. | Nosana provider deployment URL + recorded run |

Detailed claim-to-artifact mapping, repo locations, and judge reproduction steps are in [`evidence-plan.md`](evidence-plan.md).

## d. Submission checklist and timeline (Round 1: June–October 2026)

Submission mechanism: publish a blog post on HackerNoon tagged for the hackathon (e.g. "Decentralize AI", "AI Infrastructure", "GPU Marketplace"). A follow-up post is required to qualify for the additional follow-up-post prize pool. The full article plan is in [`article-series.md`](article-series.md).

### Checklist

- [ ] Public repo live at `github.com/joshuaswarren/sovereign-inference` with README, architecture, spec, MVP/demo doc, and threat model.
- [ ] Milestone 1 implementation working end to end (scan → recommend → serve → benchmark → publish manifest → route → receipt → failover).
- [ ] `sip-receipt verify` passing on all demo receipts; receipt test suite green in CI.
- [ ] Reproducible benchmark JSON committed and referenced from the article.
- [ ] Failover demo recorded (terminal session + router logs).
- [ ] One decentralized provider (Nosana) serving a routed request, with a deployment URL.
- [ ] Arweave manifest anchor demonstrated (or transaction ID recorded) for at least one model and one provider manifest.
- [ ] Primary HackerNoon post (Article 1) published with correct tags and links back to the repo.
- [ ] Follow-up HackerNoon post (Article 4) published with measured results.
- [ ] Evidence plan ([`evidence-plan.md`](evidence-plan.md)) cross-checked: every public claim has a linked artifact.

### Indicative timeline

| Window | Focus | Output |
| --- | --- | --- |
| June 2026 | Spec and proof of concept | Protocol spec v0.1, manifest/receipt schemas, CLI skeleton. |
| July 2026 | Local node | Hardware scan, model advisor, local serving, benchmark, dashboard. |
| August 2026 | Network routing | Provider registry, routing, quotes, signed receipts, failover. |
| September 2026 | Payment + decentralized integration | Mock x402, simulated PIC, Arweave anchor, Nosana provider adapter live. |
| October 2026 | Evidence + submission | Recorded demo, benchmark JSON, primary HackerNoon post, follow-up post. |

Multiple entries are allowed, and Round 2 (November 2026–February 2027) can carry a second, deeper submission (for example, the PIC privacy deep-dive or a hardened relay-transport mode).

## e. Nosana credits plan

The prize pool exceeds $51,750, including $35,000 in Nosana GPU credits, with the first 500 participants receiving $70 in credits and 15 winners sharing a $450 follow-up-post pool. We will use Nosana credits to make the "decentralized compute" claim real rather than simulated:

- Stand up a **real remote provider node** on Nosana GPU using the [`../../adapters/provider-nosana`](../../adapters/provider-nosana) adapter, running a supported runtime (llama.cpp or vLLM) behind the hardened provider gateway.
- Route a live OpenAI-compatible request from the SIP-AI client to that Nosana-hosted provider and return a signed receipt — producing the deployment URL used as verifiable evidence.
- Use the credits to run the benchmark and failover demos against a genuine remote GPU, so the published tokens/sec, TTFT, and failover behavior reflect decentralized compute, not just a local laptop.
- Reserve headroom for an uptime probe window so the provider manifest's benchmark and availability figures are measured over a real interval.

This keeps the entry honest: the credits fund a working remote provider node, and the resulting URL plus recorded run are the evidence that the orchestration layer reaches decentralized compute.

See also: [Article series plan](article-series.md), [Evidence plan](evidence-plan.md).

_Derived from the v0.1.2 Product Requirements Package._
