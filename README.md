<div align="center">

# Sovereign Inference

**Run the best open model your hardware can handle — and optionally share that
capacity through a privacy-preserving, censorship-resistant, provider-neutral
inference network.**

Two linked products: **SIP-AI** (the protocol) and **SIN** (the node).

[Vision](docs/vision.md) · [Architecture](docs/architecture.md) · [Protocol spec](docs/spec/protocol-spec.md) · [Roadmap](ROADMAP.md) · [Hackathon plan](docs/hackathon/decentralizeai-submission.md) · [Contributing](CONTRIBUTING.md)

</div>

---

## The problem

Open-weight models are good enough for real work, but *access* to them is
fragile. Most people still depend on centralized APIs, clouds, app-store
gatekeepers, blockable websites, or hardware they can't afford. Running locally
is powerful but still too hard. Serving to others is harder still — providers
must pick models, install runtimes, secure endpoints, price requests, measure
capacity, handle payment, and earn trust.

**Sovereign Inference is the access and supply layer for open AI: local-first
when possible, decentralized when needed, provider-neutral by design.** The
novelty isn't a new GPU marketplace, model runner, or anonymity network — it's
the **orchestration layer** that makes those existing pieces composable, safe,
and usable.

## Two products

| Product | What it does | For whom |
| --- | --- | --- |
| **SIP-AI** — Sovereign Inference Protocol | Routes paid inference to open models across local, self-hosted, and decentralized providers — without one API chokepoint. Signed receipts, pluggable payments, pluggable transports. | Developers, apps, routers |
| **SIN** — Sovereign Inference Node | Scans your hardware, recommends + installs the right open model, runs it locally, benchmarks it, and (opt-in) shares spare capacity safely. | Individuals, homelabs, GPU owners, teams |

> **One provider per request (v1).** Each request is served in full by one
> provider node; failover happens between providers, never inside one model
> execution. This is deliberately *not* sharded inference — it keeps latency,
> security, accountability, and verification tractable.

## Status — building it for real

This is a real, in-progress build, not a slideware concept. Honest snapshot:

| Component | Status |
| --- | --- |
| `sip-protocol` — canonical JSON, Ed25519, manifests, receipts, JSON-Schema validation | ✅ **implemented + tested** |
| `sip-receipt` — sign/verify CLI | ✅ **implemented + tested** |
| JSON Schemas for receipts & manifests | ✅ **authoritative, CI-validated** |
| **SIN node** — `sin scan`, recommendation engine, benchmark · `sin` CLI · Ollama & llama.cpp adapters · status API · React dashboard | ✅ **implemented + tested** (Phase 1) |
| **SIP-AI routing** — provider gateway (auth, limits, signed receipts) · router (resolve, score, quote, route, **failover**) · signed quotes | ✅ **implemented + tested** (Phase 2) |
| PIC vouchers · external compute adapters (Nosana/Akash) · Arweave anchoring | 🚧 scaffolded — see [ROADMAP](ROADMAP.md) (Phase 3–4) |

## Try the working slice (60 seconds)

A signed inference receipt is a verifiable accountability artifact. You can
generate and verify one today, with real Ed25519 signatures, no network needed:

```console
# Requires: uv (https://docs.astral.sh/uv) and Python 3.12+
git clone https://github.com/joshuaswarren/sovereign-inference
cd sovereign-inference
uv sync

uv run sip-receipt demo > receipt.json     # emit a freshly signed sample receipt
uv run sip-receipt verify receipt.json      # -> OK   receipt verified — provider ed25519:...

# tamper with any field and verification fails (exit code 1):
python -c "import json;d=json.load(open('receipt.json'));d['output_tokens']=1;json.dump(d,open('receipt.json','w'))"
uv run sip-receipt verify receipt.json      # -> FAIL receipt did not verify
```

See [docs/spec/receipts.md](docs/spec/receipts.md) for the format and signing rule.

### Inspect your hardware and pick a model (the SIN node)

```console
uv run sin scan                          # detect CPU/RAM/GPU/VRAM + installed runtimes
uv run sin recommend --task coding       # ranked model/quant picks that fit your machine
uv run sin catalog                       # the curated model catalog
uv run sin status                        # registered runtime adapters
```

`sin scan` is cross-platform (macOS/Linux/Windows) and the recommendation engine
explains *why* each model fits and what tradeoffs it carries. See the
[SIN PRD](docs/prd/sin.md) and [ROADMAP](ROADMAP.md).

## Repository layout

```text
docs/            # Vision, architecture, protocol spec, PRDs, hackathon plan (start at docs/README.md)
packages/        # Python core
  sip-protocol/      # canonical JSON, Ed25519, receipts, manifests, schemas   [Apache-2.0]
  receipt-verifier/  # the `sip-receipt` CLI                                    [Apache-2.0]
  router/            # client SDK + provider router (resolve/score/quote/route) [AGPL-3.0]
  provider-gateway/  # hardened gateway in front of a runtime                   [AGPL-3.0]
  pic-vouchers/      # Private Inference Credits issuance/redeem/settle          [AGPL-3.0]
  sin-node/          # hardware scan, model advisor, serving, benchmarking       [AGPL-3.0]
  sin-cli/           # the `sin` CLI                                             [AGPL-3.0]
adapters/        # runtime + provider adapters (Ollama, llama.cpp, vLLM, ...)   [Apache-2.0]
sdk-js/          # TypeScript client SDK                                         [Apache-2.0]
apps/dashboard/  # local web dashboard (React/Vite)                             [AGPL-3.0]
registry/        # model + provider manifests
```

## Tech stack

- **Python 3.12+** core (managed with [uv](https://docs.astral.sh/uv)) — node,
  CLI, router, gateway, receipts, PIC. Tooling: `ruff`, `mypy --strict`, `pytest`.
- **TypeScript** for the React/Vite dashboard and the developer-facing JS SDK.
- A cross-platform **Tauri** desktop shell (bundling the Python node as a
  sidecar) is planned so non-technical users on macOS/Linux/Windows get a
  one-click install — see [ROADMAP](ROADMAP.md).

## Licensing — open, and built to stay open

We use a deliberate split so the protocol spreads widely **and** can't be
quietly closed-sourced as a hosted fork:

- **Apache-2.0** — the protocol spec, JSON schemas, client SDKs, and runtime
  adapters. Maximum adoption, with a patent grant.
- **AGPL-3.0** — the server/infrastructure apps (router, gateway, node, PIC
  issuer, dashboard). Network copyleft keeps hosted versions open.

Full details and the per-directory map: [LICENSING.md](LICENSING.md).

## Hackathon

Sovereign Inference is being entered into the
[DecentralizeAI](https://decentralizeai.tech/) hackathon, which rewards genuine
implementation, originality, impact, and **verifiable evidence** (mockups are
ineligible). Our plan, evidence map, and article series live in
[docs/hackathon/](docs/hackathon/decentralizeai-submission.md).

## Contributing

We welcome contributors. Please read [CONTRIBUTING.md](CONTRIBUTING.md) (we use
DCO sign-offs) and our [Code of Conduct](CODE_OF_CONDUCT.md). Security issues:
see [SECURITY.md](SECURITY.md). Project governance: [GOVERNANCE.md](GOVERNANCE.md).

## Acknowledgements

Sovereign Inference is an orchestration layer that builds on excellent existing
work — Ollama, llama.cpp, vLLM, SGLang, LocalAI, LM Studio, Nosana, Akash,
Arweave, x402, Cashu, Privacy Pass, and others. See [references](docs/references.md).
