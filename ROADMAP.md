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

## Phase 5 — Privacy modes  (post-MVP)
- ⬜ Relay hardening; Tor/Snowflake, I2P, and Nym-compatible transport experiments
- ⬜ TEE-capable provider metadata & attestation
- ⬜ PIC cryptographic upgrade (Chaumian ecash / Privacy Pass)

## Phase 6 — Production hardening  (post-hackathon)
- ⬜ Security review & signed releases
- ⬜ Plugin SDK, policy framework, provider reputation
- ⬜ **Cross-platform desktop app (Tauri)** bundling the Python node as a sidecar
  + the React dashboard, for one-click install on macOS/Linux/Windows by
  non-technical users

## How to help
Pick an unchecked item, open an issue if one doesn't exist, and see
[CONTRIBUTING.md](CONTRIBUTING.md). Runtime adapters and model-catalog entries
are great self-contained starting points.
