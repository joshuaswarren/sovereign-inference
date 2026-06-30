# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project aims to
follow [Semantic Versioning](https://semver.org/) once it reaches 1.0.

## [Unreleased]

### Added
- **Phase 6 — production usability: a local OpenAI-compatible endpoint + policy:**
  - **`sip-openai-proxy`** (AGPL): run one server (`sip-openai-proxy --registry … --port 11435`)
    and point any OpenAI client (the `openai` SDK, LangChain, LM Studio, `curl`) at
    `http://localhost:11435/v1` — requests route across SIP-AI providers with failover,
    and every answer carries a verified signed receipt (under a `sip` extension field).
    Exposes `GET /v1/models`, `POST /v1/chat/completions` (streaming + non-streaming),
    `GET /healthz`; optional API-key auth.
  - **`sip-policy`**: a declarative `Policy` governing which providers may serve —
    require TEE attestation (and which types), price caps + accepted units, required
    privacy modes, provider allow/deny lists, and a minimum reputation. The proxy
    applies it to filter providers (and the advertised model list).
- **Phase 5 — privacy modes (relay, TEE attestation, issuer-unlinkable credits):**
  - **`sip-relay`** (AGPL): a privacy relay that forwards a completion to a provider
    so the provider sees the relay, not the client. The relay routes **only to the
    signed `manifest_uri`** and is untrusted for integrity — the client (`relay_chat`)
    verifies the provider's signed receipt and detects any tampering.
  - **TEE attestation** (`sip_protocol.attestation`): a signed `sip-ai.attestation.v1`
    statement binding a TEE type + code measurement to a provider key, embedded in the
    provider manifest, with an `is_attested` selection policy (binds the attestation to
    the manifest key; hardware-quote verification is a pluggable boundary).
  - **Issuer-unlinkable credits** (`sip_pic.blind`): RSA blind-signature credits — the
    issuer blind-signs a serial it never sees, so it can't link issuance to redemption
    (payer↔issuer unlinkability), with double-spend prevention via the spent-set. (v0:
    MGF1-FDH, documented as pending formal review.)
  - **Privacy demo** (`sip-privacy-demo`): require an attested provider, mint + spend an
    unlinkable credit, route through a relay, and detect a tampering relay — in-process.
- **Supply onboarding follow-ons — hosted directory, reputation, auto re-announce:**
  - **Hosted directory service** — `sip_discovery.HttpDirectory` (a `Directory`
    client over HTTP) and **`sip-directory-service`** (an AGPL FastAPI relay,
    `create_directory_app`, over any `Directory` store). The relay is never
    trusted: the client re-verifies every manifest and routes only to the signed
    `manifest_uri`, and the server rejects forged manifests on announce.
  - **`sip-reputation`** — `HealthProbe` (liveness + identity + model check at
    `/sip/v1/health`), a persisted `ReputationStore` (records routing outcomes,
    computes a bounded score, neutral cold-start), and `rank_providers` (drops
    unreachable nodes, orders by reputation → latency → advertised throughput).
  - **Auto re-announce** — `ShareConfig.benchmark` + `build_share_manifest` /
    `reannounce` re-sign a fresh manifest (new `published_at` + benchmark), and
    `sin benchmark --announce DIRECTORY` re-announces with the just-measured
    metrics; directories keep the freshest entry per provider.
  - **Supply demo** (`sip-supply-demo`): announce to a hosted directory → discover
    → health/reputation rank → route → record outcome → re-benchmark + re-announce.
- **Supply onboarding — `sin share` + provider discovery:**
  - **`sin share`**: one command turns a running node into a discoverable SIP
    provider — it fronts the local runtime adapter with the real provider gateway
    (auth, model allowlist, context/token caps, rate limit, signed receipts, opt-in
    PIC payment), advertises a signed `sovereign-node` manifest carrying the node's
    public URL, and (optionally) announces it to a directory. `--no-serve` publishes
    and announces without starting the server.
  - **`sip-discovery`**: announce signed provider manifests to a `Directory` and
    discover verified providers to route to — `FileDirectory` (offline shared JSON)
    and `ArweaveDirectory` (anchor + injected GraphQL query). Discovery verifies
    every manifest signature and keeps the freshest entry per provider key, so a
    forged or stale entry is never routed to.
  - **`sip_protocol.build_provider_manifest`**: a reusable unsigned provider-manifest
    builder (sovereign-node / external-adapter / relay) with `manifest_uri` support.
  - **Discovery demo** (`sip-discovery-demo`): a node announces itself, a router
    discovers it, builds its registry, routes a real request, and verifies the
    receipt — fully in-process and deterministic.
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
- **Phase 3 — payments (Private Inference Credits + x402):**
  - Signed **Voucher** artifact (`sip-ai.voucher.v1`) — an issuer-signed bearer
    credit (build/sign/verify + expiry + JSON schema).
  - **`sip-pic`**: a PIC issuer, a wallet, a persistent **double-spend `SpentSet`**
    (atomic redemption with rollback), `redeem_payment` (all-or-nothing PIC batch
    + x402), a provider `Ledger`, and the HTTP 402 challenge — all `Decimal` money math.
  - **x402** direct-pay: payer-signed, single-use (nonce), and bound to one
    provider + request, with a documented path to real on-chain settlement.
  - **Gateway** payment enforcement: an HTTP 402 challenge carrying the exact
    price, **charge-on-success** (the credit is consumed only after a successful
    response), and a receipt that attests the price actually charged.
  - **Router** reactive payment: on 402 it pays from a wallet (or x402), retries
    the provider once, returns unspent vouchers to the wallet on failure, and fails over.
  - **Paid end-to-end demo**: mint → 402 → pay → verified receipt → wallet
    debited / provider ledger credited → double-spend replay rejected.
  - Adversarial review pass: 4 confirmed money bugs fixed with regression tests
    (x402 replay, charge-on-success, receipt==charged, paid-retry voucher safety).
- **Phase 4 — decentralized integration (external compute + permanent provenance):**
  - **`sip-compute`**: a provider-agnostic external-compute contract — the
    `InferenceSpec`/`Deployment`/`DeploymentStatus` types, the `ComputeProvider`
    protocol + a factory registry, and `provider_manifest_for`, which turns a
    provisioned endpoint into a signed `external-adapter` SIP provider manifest.
  - **`sip-arweave`**: anchor SIP-AI provenance to durable storage and resolve it
    back — `LocalAnchor` (offline, content-addressed `local://`) and `ArweaveAnchor`
    (permanent `ar://`, HTTP resolve + injected transaction submitter), with
    canonical-JSON round-tripping and **verify-before-anchor** for receipts/manifests.
  - **`sip-provider-nosana`**: a Nosana adapter that builds a container job
    definition, posts it, polls to `RUNNING`, exposes the served endpoint, and
    registers as a SIP `nosana` compute provider.
  - **`sip-provider-akash`**: an Akash adapter that builds an SDL v2.0 manifest and
    drives the real marketplace lifecycle (create → cheapest-bid → lease →
    send-manifest → poll lease ingress) as the SIP `akash` compute provider.
  - Both adapters reach their networks only through **injected boundaries** (a CLI
    runner + an injected `sleep`), so the entire provision/poll/teardown lifecycle
    is unit-tested offline; a live deploy needs the real CLIs and a funded wallet.
  - **Decentralized demo** (`sip-decentralized-demo`): provision a node via the
    Nosana adapter → advertise it as a signed provider → anchor the manifest →
    route a real request → verify and anchor the signed receipt — fully in-process,
    deterministic, with reproducible metrics.

[Unreleased]: https://github.com/joshuaswarren/sovereign-inference/commits/main
