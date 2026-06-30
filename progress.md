# Progress

A running log of what's done and what's next. See [ROADMAP.md](ROADMAP.md) for
the phased plan and [CHANGELOG.md](CHANGELOG.md) for released changes.

## 2026-06-30 — Phase 6 (part 2): plugin SDK + supply-chain hardening + desktop scaffold

**Done** (branch `feat/phase-6-plugins-security`, PR pending)
- **`sip-plugins`** (Apache, TDD): entry-point discovery + registration for runtime
  adapters / compute providers / directories; `discover`/`load_all` skip a plugin
  that fails to import (one bad plugin can't break the host). Injectable entry-point
  source + registrar → unit-tested without installing packages.
- **Supply-chain hardening**: CI `security` job runs `pip-audit` (advisory; locked
  set is currently clean) + publishes a CycloneDX `sbom.json` artifact;
  `RELEASING.md` documents reproducible builds + Sigstore/minisign signing + verify.
- **Desktop scaffold** (`apps/desktop`, Tauri v2): `tauri.conf.json` (dashboard as
  frontend + proxy as `externalBin` sidecar), Rust shell that spawns the sidecar,
  README with the local build steps. Plus `python -m sip_openai_proxy` for freezing
  the sidecar. (Binary build needs the local Rust/Tauri toolchain — honest scaffold.)
- 517 tests; ruff + mypy --strict clean. Focused adversarial review run.

**Next:** built/notarized installers in a release workflow; deeper privacy + directory
federation per the roadmap.

## 2026-06-30 — Phase 6 (part 1): local OpenAI-compatible endpoint + policy

**Done** (branch `feat/phase-6-openai-proxy`, PR pending)
- **`sip-openai-proxy`** (AGPL, TDD): one local server exposing `/v1/models` +
  `/v1/chat/completions` (streaming SSE + non-streaming) + `/healthz` over the real
  `SovereignClient` — point any OpenAI client at `http://localhost:11435/v1`. Every
  answer carries a verified signed receipt under a `sip` extension; optional API key.
  Verified on a real socket (boots, serves OpenAI-shaped `/v1/models`).
- **`sip-policy`** (Apache, TDD): `Policy` (require attestation/tee-types, price caps +
  units, required privacy modes, allow/deny, min reputation via injected score);
  `build_backend` filters the registry + model list by policy.
- 510 tests; ruff + mypy --strict clean (80 files). CI extended (policy + proxy in
  the mypy list). Adversarial review running.

**Next (Phase 6 part 2):** plugin SDK (entry-point extension points), security
hardening (pip-audit CI, SBOM, signed-releases doc), Tauri desktop scaffold.

## 2026-06-30 — Phase 5: privacy modes + 3-machine validation

**Live validation** — all of `main` (Phases 0–4 + share/discovery + supply) re-run
on **laptop / macstudio / proxmox2** (fresh clone of commit 59858ca): full pytest
exit 0 + all 5 demos green on macOS arm64 ×2 and Linux x86_64.

**Phase 5 done** (branch `feat/phase-5-privacy`, PR pending)
- **`sip-relay`** (AGPL, TDD): privacy relay — forward to a provider so it never
  sees the client; routes only to the signed `manifest_uri`; untrusted for integrity
  (client `relay_chat` verifies the receipt; tampering relay detected).
- **TEE attestation** (`sip_protocol.attestation`, TDD): `sip-ai.attestation.v1`
  build/sign/verify + `is_attested` policy (binds attestation to the manifest key);
  hardware-quote verification is an injected boundary. New schema + manifest field.
- **Issuer-unlinkable credits** (`sip_pic.blind`, TDD): RSA blind-signature credits
  (blind → blind-sign → unblind → redeem; double-spend via spent-set). v0 = MGF1-FDH,
  documented as pending formal review.
- **`sip-privacy-demo`**: attested provider + unlinkable credit + relay (with a
  threaded ASGI transport so relay→provider composes in-process).
- 498 tests; ruff + mypy --strict clean. CI extended (pic-vouchers + relay in the
  mypy list; privacy-demo smoke step). Adversarial review run (crypto-focused).

**Next:** open PR; Phase 6 (production hardening) or deeper privacy (onion routing,
formal crypto review, DCAP/SEV verifiers).

## 2026-06-30 — Supply follow-ons: hosted directory, reputation, auto re-announce

**Done** (branch `feat/directory-service-reputation-reannounce`, PR pending)
- **Hosted directory** — `sip_discovery.HttpDirectory` client + **`sip-directory-service`**
  (AGPL FastAPI `create_directory_app` over any `Directory` store). Relay is untrusted:
  client re-verifies manifests + routes only to the signed `manifest_uri`; server 400s
  forged manifests on announce.
- **`sip-reputation`** — `HealthProbe` (liveness + pubkey/model identity at `/sip/v1/health`),
  persisted `ReputationStore` (outcome counters → bounded score, neutral cold-start),
  `rank_providers` (drops unreachable, orders by reputation → latency → tps).
- **Auto re-announce** — `ShareConfig.benchmark` + `build_share_manifest`/`reannounce`;
  `sin benchmark --announce DIR` re-announces with the just-measured metrics; freshest
  per pubkey wins.
- **`sip-supply-demo`** — announce (hosted) → discover → rank → route → record → re-announce.
- 475 tests; ruff + mypy --strict clean. CI extended (reputation + directory-service in
  the mypy list; supply-demo smoke step). Adversarial review run.

**Next:** open PR; further follow-ons (directory federation/gossip, signed reputation
attestations, staking) and Phase 5 privacy modes.

## 2026-06-29 — Supply onboarding: `sin share` + provider discovery

**Done** (branch `feat/sin-share-and-discovery`, PR pending)
- **`sip-discovery`** (lead, TDD): `Directory` protocol + `FileDirectory` (atomic,
  verify-on-announce/discover, dedupe-by-freshness, model filter) + `ArweaveDirectory`
  (anchor + injected GraphQL query). Signature-verified discovery, freshest-per-key.
- **`sip_protocol.build_provider_manifest`** (TDD): reusable unsigned provider-manifest
  builder with `manifest_uri`.
- **`sin share`** (TDD): `ShareConfig` + `build_share` compose the existing gateway
  (caps + payment) over a SIN runtime adapter, advertise a signed `sovereign-node`
  manifest with `manifest_uri`, and announce to a `Directory`. `cmd_share` + a
  `--no-serve` publish/announce mode (also the CI smoke test).
- **Discovery demo** (`sip-discovery-demo`): announce → discover → route → verify,
  in-process and deterministic.
- 452 tests pass; ruff + mypy --strict clean. CI extended (discovery in the mypy
  list; discovery-demo + `sin share` publish smoke steps). Adversarial review run.

**Why:** answers "can users' SIN nodes also join this system?" — yes: a SIN node is a
first-class provider, and discovery removes the manual-registry cold-start.

**Next:** open PR; then the bigger discovery follow-ons (a hosted directory service,
reputation/health signals) and Phase 5 privacy modes.

## 2026-06-29 — Phase 4: decentralized integration (external compute + anchoring)

**Done** (branch `feat/phase-4-decentralized`, PR pending)
- **`sip-compute`** (lead, TDD): external-compute contract — `InferenceSpec` /
  `Deployment` / `DeploymentStatus`, `ComputeProvider` protocol + registry, and
  `provider_manifest_for` (signed `external-adapter` provider manifest).
- **`sip-arweave`** (lead, TDD): `LocalAnchor` (offline `local://`) + `ArweaveAnchor`
  (`ar://`, HTTP resolve + injected tx submitter); canonical round-trip and
  **verify-before-anchor** for receipts/manifests.
- **`sip-provider-nosana`** and **`sip-provider-akash`** adapters: real job/SDL
  builders + full provision→poll→teardown lifecycle, reached through injected CLI
  boundaries so they unit-test offline (live deploy needs the real CLIs + wallet).
- **Decentralized demo** (`sip-decentralized-demo`): provision → advertise → anchor
  → route → verify → anchor receipt, fully in-process & deterministic, with
  reproducible metrics. Wired into CI (lint/type/test now cover `apps` + the four
  new packages; a demo smoke-test step added).
- Full suite + ruff + mypy --strict clean. Adversarial-review workflow run; fixes
  applied per confirmed findings.

**Next**
- 3-machine live validation (laptop / macstudio / proxmox2); open PR for issue #10.
- Phase 5 (privacy modes) per the roadmap.

## 2026-06-29 — Phase 3: payments (PIC + x402)

**Done** (branch `feat/phase-3-payment`, PR pending)
- Signed **Voucher** artifact (`sip-ai.voucher.v1`) in `sip-protocol` (TDD).
- **`sip-pic`**: Issuer, Wallet, persistent atomic double-spend `SpentSet`,
  `redeem_payment` (all-or-nothing PIC + single-use/bound x402), provider `Ledger`,
  402 challenge — all `Decimal` math.
- **Gateway**: HTTP 402 challenge + **charge-on-success** (verify → serve → commit);
  receipt attests the charged price. **Router**: reactive 402 pay-and-retry with
  voucher refund on failure → failover.
- **Paid demo** green: mint → 402 → pay → verified receipt → debited/credited →
  double-spend replay rejected.
- Built via an implementation workflow + adversarial-review workflow; 4 confirmed
  money bugs fixed (x402 replay, charge-on-success, receipt==charged, paid-retry
  voucher safety) with regression tests. Full suite + ruff + mypy --strict clean.

**Next (Phase 4 — decentralized integration)**
- Arweave manifest/receipt anchoring; a Nosana (or Akash) external compute/provider
  adapter; published reproducible demo metrics (issue #10).

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
