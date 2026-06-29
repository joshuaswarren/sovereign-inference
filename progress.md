# Progress

A running log of what's done and what's next. See [ROADMAP.md](ROADMAP.md) for
the phased plan and [CHANGELOG.md](CHANGELOG.md) for released changes.

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
