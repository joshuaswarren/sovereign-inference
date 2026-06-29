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

[Unreleased]: https://github.com/joshuaswarren/sovereign-inference/commits/main
