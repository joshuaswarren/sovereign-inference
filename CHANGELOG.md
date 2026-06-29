# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project aims to
follow [Semantic Versioning](https://semver.org/) once it reaches 1.0.

## [Unreleased]

### Added
- Repository bootstrap as a public, open-source monorepo.
- Full product documentation set under `docs/` (vision, opportunity,
  architecture, PRDs for SIP-AI and SIN, protocol spec, manifests, transport
  modes, Private Inference Credits, provider selection, risk register, threat
  model, roadmap, go-to-market, glossary, references), derived from the v0.1.2
  Product Requirements Package.
- Authoritative JSON Schemas for inference receipts and model/provider manifests
  (`docs/spec/schemas/`), validated in CI.
- **`sip-protocol`** library (Apache-2.0): canonical JSON (RFC 8785-compatible),
  Ed25519 signing/verification, signed inference receipts, provider/model
  manifest signing & content-addressing, and JSON Schema validation — with a
  full pytest suite.
- **`sip-receipt`** CLI (Apache-2.0): `keygen`, `demo`, `sign`, and `verify`
  for signed inference receipts.
- Scaffolded packages for the router, provider gateway, PIC vouchers, SIN node,
  SIN CLI, runtime adapters (Ollama/llama.cpp/vLLM), TS SDK, and dashboard.
- Project tooling: uv workspace, ruff, mypy (strict), pytest, pre-commit, and
  GitHub Actions CI.
- DecentralizeAI hackathon plan, evidence map, and article series.
- Governance, contributing (DCO), security policy, code of conduct, and a split
  Apache-2.0 / AGPL-3.0 licensing model.
- **Phase 1 — Sovereign Inference Node (local node):**
  - `sin_node` core: `HardwareProfile`/catalog/recommendation models, a memory
    estimator, an OpenAI-compatible HTTP client with streaming TTFT/tokens-per-sec
    timing, and the `RuntimeAdapter` protocol + registry.
  - `sin scan` cross-platform hardware profiler (CPU/RAM/disk/GPU/VRAM + runtime
    detection) with human and JSON output.
  - Model recommendation engine over a curated 5-model catalog (memory-fit +
    quality + speed scoring with explanations; quant capped at a near-lossless Q8).
  - Ollama and llama.cpp runtime adapters (detect/serve/health/chat; lifecycle
    management with subprocess reaping).
  - `sin benchmark` — tokens/sec, TTFT, and a signed provider capability manifest.
  - The `sin` CLI: `scan`, `recommend`, `catalog`, `serve`, `install`,
    `benchmark`, `status`, `version`.
  - A FastAPI status API and a React/Vite dashboard.
  - Adversarial review pass: 7 confirmed findings fixed with regression tests
    (182 tests total; ruff + mypy --strict clean across the typed packages).
- **Phase 2 — SIP-AI network routing:**
  - Signed inference **quotes** (`sip-ai.quote.v1`) — a provider's verifiable,
    expiring price commitment (build/sign/verify + JSON schema).
  - **Provider gateway** (`sip-provider-gateway`): a hardened FastAPI front door
    over a runtime adapter — bearer auth (constant-time), model allowlist,
    context/output-token caps, in-memory rate limit, and logging policy;
    `/sip/v1` health/quote/provider-manifest plus an OpenAI-compatible
    `/v1/chat/completions` that returns a provider-signed receipt.
  - **Router** (`sip-router`): a provider registry + resolver, weighted provider
    scoring (spec §6.8), and `SovereignClient`, which resolves → scores →
    (optionally quotes) → routes one request to one provider → verifies the
    signed receipt (signature, provider-key binding, and response-body hash) →
    **fails over** to the next provider on any failure.
  - **End-to-end demo** (`sip-router-demo`): the real client routes across two
    real in-process gateways, verifies receipts, and fails over when a provider
    goes down.
  - Adversarial review pass: 8 confirmed findings fixed with regression tests
    (including failover on non-JSON bodies, receipt/response-hash binding, and
    signed-quote price enforcement).

[Unreleased]: https://github.com/joshuaswarren/sovereign-inference/commits/main
