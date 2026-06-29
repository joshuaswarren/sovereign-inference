# Progress

A running log of what's done and what's next. See [ROADMAP.md](ROADMAP.md) for
the phased plan and [CHANGELOG.md](CHANGELOG.md) for released changes.

## 2026-06-29 — Phase 2: SIP-AI network routing

**Done** (branch `feat/phase-2-network-routing`, PR pending)
- Signed inference **quotes** (`sip-ai.quote.v1`) in `sip-protocol` (TDD).
- **Provider gateway** (FastAPI): auth, model allowlist, context/token caps,
  rate limit, logging policy; `/sip/v1` health/quote/manifest + OpenAI-compatible
  `/v1/chat/completions` returning a provider-signed receipt.
- **Router**: registry + resolver + weighted scoring (§6.8) + `SovereignClient`
  (resolve → score → quote → route → verify receipt → **failover**).
- **End-to-end demo** routes across two real in-process gateways and fails over
  on provider failure — `uv run sip-router-demo` passes.
- Built via an implementation workflow + adversarial-review workflow; 8 confirmed
  findings fixed (non-JSON-body failover, receipt↔response-hash binding, signed-
  quote price/identity/expiry enforcement, constant-time auth, true-upper-bound
  quote pricing) with regression tests. Full suite + ruff + mypy --strict clean.

**Next (Phase 3 — payment)**
- x402 direct-pay path; Private Inference Credits issue → redeem → settle with
  double-spend prevention; provider accounting (issues #9).

## 2026-06-29 — Phase 1: Sovereign Inference Node (local node)

**Done** (branch `feat/phase-1-local-node`, PR pending)
- `sin_node` core (TDD): models, memory estimator, OpenAI-compatible HTTP client
  with streaming TTFT/tps timing, runtime-adapter protocol + registry.
- `sin scan` cross-platform hardware profiler; model recommendation engine over a
  curated 5-model catalog; Ollama + llama.cpp adapters; `sin benchmark` (signed
  capability manifest); the `sin` CLI; a FastAPI status API; a React/Vite dashboard.
- Built via a parallel implementation workflow against frozen core contracts, then
  an adversarial review workflow; 7 confirmed findings fixed with regression tests.
- **182 tests pass; ruff + mypy --strict clean.** Live-verified `sin scan` /
  `sin recommend` on real hardware; dashboard builds.

**Next (Phase 2 — network routing)**
- Provider registry + resolver; router (scoring, quotes, one-provider-per-request,
  failover); hardened provider gateway with signed receipts end-to-end.

## 2026-06-29 — Repository bootstrap

**Done**
- Split the v0.1.2 PRD (`docs/prd/archive/prdpak-v0.1.2.md`) into a full docs set
  under `docs/` (vision, opportunity, architecture, PRDs, protocol spec,
  manifests, transport, PIC, provider selection, risk register, threat model,
  roadmap, GTM, glossary, references, hackathon plan + evidence + articles).
- Authoritative JSON Schemas for receipts and model/provider manifests.
- **`sip-protocol`** (Apache-2.0): canonical JSON, Ed25519 signing/verify,
  receipts, manifests, schema validation — 42 tests passing, ruff + mypy clean.
- **`sip-receipt`** CLI: `keygen` / `demo` / `sign` / `verify` (real Ed25519).
- Scaffolded packages: router, provider-gateway, pic-vouchers, sin-node,
  sin-cli, runtime adapters (ollama/llamacpp/vllm), TS SDK (builds), dashboard.
- Real signed registry artifacts (provider manifest) + `examples/sample-receipt.json`.
- Repo meta: README, split Apache/AGPL licensing, CONTRIBUTING (DCO), CoC,
  SECURITY, GOVERNANCE, ROADMAP, CHANGELOG, ADRs.
- Tooling: uv workspace, ruff, mypy --strict, pytest, pre-commit, Makefile.
- CI: Python (lint/type/test + receipt CLI smoke) and JS (SDK typecheck/build).

**Next (Phase 1 — local node)**
- `sin scan` hardware profiler (CPU/RAM/GPU/VRAM/disk/runtimes).
- Model recommendation engine + memory-fit estimation.
- Local serving via llama.cpp / Ollama adapters; `sin benchmark`.
- React/Vite dashboard.
