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
- 🚧 CLI skeletons for `sin` and the router

## Phase 1 — Local node  (Weeks 2–3)
- ⬜ `sin scan` — hardware profiler (CPU/RAM/GPU/VRAM/disk/runtimes)
- ⬜ Model recommendation engine (fit + quality + speed scoring)
- ⬜ Local serving via llama.cpp and Ollama adapters (OpenAI-compatible)
- ⬜ `sin benchmark` — tokens/sec, TTFT, max stable context
- ⬜ Local web dashboard (React/Vite)

## Phase 2 — Network routing  (Weeks 3–4)
- ⬜ Provider registry (local JSON) + resolver
- ⬜ Router: scoring, quotes, one-provider-per-request, **failover**
- ⬜ Provider gateway: auth, quotas, policy, request limits, receipt generation
- ⬜ Signed receipts end-to-end through a real request

## Phase 3 — Payment  (Weeks 4–5)
- ⬜ x402 direct-payment path (first real form, with upgrade path)
- ⬜ PIC: issue → redeem → settle, with double-spend prevention
- ⬜ Provider accounting & balances

## Phase 4 — Decentralized integration  (Weeks 5–6)
- ⬜ Arweave manifest anchoring (model + provider manifests, public receipts)
- ⬜ One external compute/provider adapter (Nosana first — aligns with the $35k credits)
- ⬜ Published, reproducible demo metrics

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
