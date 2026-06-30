# Roadmap

The actionable build plan and current status. Phase definitions come from the
[PRD roadmap](docs/roadmap.md); this file tracks **what's done** and **what's
next**, and maps the work to the [DecentralizeAI](docs/hackathon/decentralizeai-submission.md)
hackathon (Round 1: June–Oct 2026).

Legend: ✅ done · 🚧 in progress · ⬜ not started

## Phase 0 — Spec & proof of concept  (Week 1)
- ✅ Protocol spec v0.1, manifest schemas, receipt format
- ✅ `sip-protocol`: canonical JSON, Ed25519, receipts, manifests, schema validation (tested)
- ✅ `sip-receipt` verifier CLI (tested)
- ✅ `sin` CLI implemented (scan/recommend/catalog/serve/install/benchmark/status); router lands in Phase 2

## Phase 1 — Local node  (Weeks 2–3) — ✅ complete
- ✅ `sin scan` — hardware profiler (CPU/RAM/GPU/VRAM/disk/runtimes), cross-platform
- ✅ Model recommendation engine (memory-fit + quality + speed scoring, 5-model catalog)
- ✅ Local serving via llama.cpp and Ollama adapters (OpenAI-compatible)
- ✅ `sin benchmark` — tokens/sec, TTFT, max stable context; emits a signed provider manifest
- ✅ Local web dashboard (React/Vite) + FastAPI status API

## Phase 2 — Network routing  (Weeks 3–4) — ✅ complete
- ✅ Provider registry (local JSON) + resolver
- ✅ Router: weighted scoring (§6.8), signed quotes, one-provider-per-request, **failover**
- ✅ Provider gateway: auth, model allowlist, context/token caps, rate limit, signed receipt generation
- ✅ Signed receipts + quotes end-to-end through a real request (router ↔ two gateways, with failover)

## Phase 3 — Payment  (Weeks 4–5) — ✅ complete
- ✅ x402 direct-payment path (signed, single-use, provider/request-bound; documented on-chain upgrade)
- ✅ PIC: issue → redeem → settle, with atomic double-spend prevention (and signed voucher artifact)
- ✅ Provider accounting & balances (Ledger); HTTP 402 challenge wired into gateway + router (charge-on-success)

## Phase 4 — Decentralized integration  (Weeks 5–6) — ✅ complete
- ✅ Arweave manifest & receipt anchoring (`sip-arweave`: `LocalAnchor` offline +
  `ArweaveAnchor` `ar://`, verify-before-anchor, canonical round-trip)
- ✅ Shared external-compute contract (`sip-compute`: `InferenceSpec`/`Deployment`,
  `ComputeProvider` protocol + registry, signed `external-adapter` provider manifest)
- ✅ **Two** external compute/provider adapters — **Nosana** (GPU job network) and
  **Akash** (SDL marketplace: create → bid → lease → manifest → ingress) — with
  injected CLI boundaries so the full lifecycle is unit-tested offline
- ✅ Published, reproducible demo metrics (`sip-decentralized-demo`: provision →
  advertise → anchor → route → verify, all in-process and deterministic)

> **Hackathon Round 1 target = Phases 0–4** plus the HackerNoon
> [article series](docs/hackathon/article-series.md) and the
> [evidence plan](docs/hackathon/evidence-plan.md).

## Supply onboarding — `sin share` + discovery — ✅ landed
- ✅ `sin share`: one command exposes a node's model as a discoverable, signed SIP
  provider (gateway caps + opt-in payment + signed `sovereign-node` manifest);
  `--no-serve` publishes/announces only
- ✅ `sip-discovery`: announce signed manifests to a `Directory` and discover
  verified providers — `FileDirectory` (offline shared JSON) + `ArweaveDirectory`
  (anchor + GraphQL query); signature-verified, freshest-per-key
- ✅ `sip-discovery-demo`: announce → discover → route → verify, in-process
- ✅ Hosted/relayed directory service (`sip-directory-service` + `HttpDirectory`)
- ✅ Provider reputation + health signals (`sip-reputation`: probe, score, rank)
- ✅ Automatic re-announce on benchmark refresh (`sin benchmark --announce`)
- ✅ `sip-supply-demo`: hosted directory + reputation rank + re-announce, in-process
- ⬜ Further: directory federation/gossip, signed reputation attestations, staking

## Phase 5 — Privacy modes  (post-MVP) — ✅ first slices landed
- ✅ **Privacy relay** (`sip-relay`): forward to a provider so it never sees the
  client; relay routes only to the signed `manifest_uri` and is untrusted for
  integrity (client verifies the receipt). Single-hop today.
- ✅ **TEE attestation** (`sip-ai.attestation.v1` + `is_attested`): signed statement
  binding a TEE measurement to a provider key; hardware-quote check is pluggable.
- ✅ **Issuer-unlinkable credits** (`sip_pic.blind`): RSA blind-signature credits
  (v0, MGF1-FDH, pending formal review) — payer↔issuer unlinkability + double-spend.
- ✅ `sip-privacy-demo`: attested provider + unlinkable credit + relay, in-process.
- ⬜ Further: multi-hop onion routing + Tor/Snowflake/I2P/Nym transports, request
  encryption, formal review of the blind-credit scheme, DCAP/SEV quote verifiers.

## Phase 6 — Production hardening  (post-hackathon) — 🚧 in progress
- ✅ **Local OpenAI-compatible endpoint** (`sip-openai-proxy`): use the network like
  a local LLM — point any OpenAI client at `http://localhost:11435/v1`; routing +
  failover + verified receipts under the hood.
- ✅ **Policy framework** (`sip-policy`): attestation / price caps / privacy modes /
  allow-deny / min-reputation, applied by the proxy.
- ✅ Provider reputation (`sip-reputation`, shipped in supply onboarding).
- ✅ **Plugin SDK** (`sip-plugins`): entry-point extension points for runtime
  adapters / compute providers / directories.
- ✅ **Supply-chain hardening**: CI dependency audit (`pip-audit`) + CycloneDX SBOM
  artifact + [`RELEASING.md`](RELEASING.md) (reproducible + signed releases).
- ✅ **Cross-platform desktop app (Tauri)** (`apps/desktop`): bundles the dashboard +
  the Python OpenAI-proxy sidecar; **built + verified on macOS arm64** (`.app` + `.dmg`;
  launches and serves `http://localhost:11435/v1`). Linux/Windows build the same way
  on those platforms.
- ⬜ Remaining: notarized/signed installers in a release workflow; an in-app onboarding flow.

## How to help
Pick an unchecked item, open an issue if one doesn't exist, and see
[CONTRIBUTING.md](CONTRIBUTING.md). Runtime adapters and model-catalog entries
are great self-contained starting points.
