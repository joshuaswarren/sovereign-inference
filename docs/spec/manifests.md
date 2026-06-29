# Manifests: Model and Provider

Manifests are the portable, signed metadata that make trust travel across the Sovereign Inference network. This document explains the two manifest shapes — model and provider — field by field, and how they are published.

> **Terminology:** SIP-AI = Sovereign Inference Protocol; SIN = Sovereign Inference Node; PIC = Private Inference Credits.

## Why manifests

Public manifests create portable trust. A client can resolve a model by alias, hash, or registry ID and discover which providers serve it, at what price, under what policy, and with what benchmarked performance — without trusting a single central API. Arweave is a strong initial permanent anchor because the DecentralizeAI competition emphasizes permanent storage and Arweave positions itself as a permanent, permissionless storage network [S3, S9].

Two manifest types work together:

- **Model manifest** — public metadata about a model artifact: hash, format, quantization, license, runtime support, and recommended settings. (See glossary entry below.)
- **Provider manifest** — signed metadata about a node: supported models, price, runtime, benchmark, policy, privacy modes, and public key. (See glossary entry below.)

## Publication and anchoring

Manifests are published to a **local registry first** (a local registry JSON in the first milestone) and **optionally anchored on Arweave** for permanent, portable provenance. This keeps the first implementable step lightweight while preserving a defined path to durable public provenance. Private prompts and completions are never stored in public registries — only public model and provider metadata.

The **authoritative JSON Schemas** for both manifest shapes live in `docs/spec/schemas/`:

- `model_manifest.schema.json`
- `provider_manifest.schema.json`

The examples below are illustrative; the schema files are the source of truth for validation.

## Model manifest

A model manifest describes a single model artifact so that any client or node can verify what it is downloading and which runtimes can serve it.

```text
{
  "schema": "sip-ai.model_manifest.v1",
  "model_id": "qwen-coder-7b-instruct-gguf-q4_k_m",
  "display_name": "Qwen Coder 7B Instruct GGUF Q4_K_M",
  "source_repo": "huggingface:example/repo",
  "weights_hash": "sha256:...",
  "format": "GGUF",
  "quantization": "Q4_K_M",
  "license": "model-license-id",
  "recommended_runtimes": ["llama.cpp", "ollama"],
  "min_memory_gb": 8,
  "recommended_memory_gb": 16,
  "context_tested": [4096, 8192],
  "tasks": ["coding", "general-chat"],
  "manifest_uri": "arweave://...",
  "maintainer_signature": "..."
}
```

| Field | Meaning |
| --- | --- |
| `schema` | Schema identifier and version (e.g. `sip-ai.model_manifest.v1`). Validators key off this. |
| `model_id` | Stable, unique alias for the model artifact. Clients resolve providers by this ID. |
| `display_name` | Human-readable name shown in dashboards and recommendations. |
| `source_repo` | Where the weights originate (e.g. a Hugging Face repo reference). |
| `weights_hash` | SHA-256 of the model weights, so downloads can be verified against the manifest. |
| `format` | Artifact format, e.g. GGUF. GGUF is the first-milestone format because Hugging Face supports GGUF metadata and common local tools use it [S21]. |
| `quantization` | Quantization scheme (e.g. `Q4_K_M`), which determines memory footprint and quality tradeoff. |
| `license` | Model license identifier. Used to filter for commercial use and to require license acceptance before paid serving. |
| `recommended_runtimes` | Runtimes known to serve this artifact well (e.g. `llama.cpp`, `ollama`). |
| `min_memory_gb` / `recommended_memory_gb` | Memory floor and comfortable target, used by the SIN fit algorithm. |
| `context_tested` | Context lengths that have been verified to run, informing KV-cache headroom estimates. |
| `tasks` | Task tags (e.g. `coding`, `general-chat`) the recommendation engine filters on. |
| `manifest_uri` | Durable location of the manifest, e.g. an `arweave://` URI when anchored. |
| `maintainer_signature` | Signature from the model maintainer, supporting provenance and durable trust. |

## Provider manifest

A provider manifest is the signed advertisement a Sovereign Inference Node publishes when it offers capacity. It tells routers what the node serves, at what price and policy, and how it has benchmarked.

```text
{
  "schema": "sip-ai.provider_manifest.v1",
  "provider_pubkey": "ed25519:...",
  "node_type": "sovereign-node",
  "models": ["qwen-coder-7b-instruct-gguf-q4_k_m"],
  "runtime_adapters": ["llama.cpp"],
  "pricing": {"unit": "pic", "input_per_1m": 0.20, "output_per_1m": 0.80},
  "max_context": 8192,
  "max_concurrency": 2,
  "logging_policy": "no_prompt_logging",
  "retention_policy": "metrics_only_30d",
  "privacy_modes": ["direct", "relay", "private-payment"],
  "benchmark": {"tokens_per_second": 39.4, "ttft_ms": 520},
  "published_at": "2026-06-29T18:00:00Z",
  "signature": "..."
}
```

| Field | Meaning |
| --- | --- |
| `schema` | Schema identifier and version (e.g. `sip-ai.provider_manifest.v1`). |
| `provider_pubkey` | The provider's Ed25519 public key. Receipts are verified against this key, tying served requests to this node. |
| `node_type` | Kind of node, e.g. `sovereign-node`. |
| `models` | Model IDs this provider can serve, matching `model_id` values from model manifests. |
| `runtime_adapters` | Runtimes the node uses to serve (e.g. `llama.cpp`). |
| `pricing` | Price structure: `unit` (e.g. `pic`) plus per-1M-token input and output rates. |
| `max_context` | Largest context length the node will accept. |
| `max_concurrency` | Maximum simultaneous requests the node advertises. |
| `logging_policy` | Logging stance, e.g. `no_prompt_logging`. Surfaced to users before they route sensitive requests. |
| `retention_policy` | Data retention stance, e.g. `metrics_only_30d`. |
| `privacy_modes` | Transport/payment privacy modes the node supports (e.g. `direct`, `relay`, `private-payment`). See [transport-modes.md](transport-modes.md). |
| `benchmark` | Self-reported, benchmark-backed performance such as `tokens_per_second` and `ttft_ms`. |
| `published_at` | Timestamp the manifest was published. |
| `signature` | Provider signature over the canonical manifest, making it tamper-evident. |

## Glossary

| Term | Definition |
| --- | --- |
| Model manifest | Public metadata about a model artifact, hash, format, quantization, license, runtime support, and recommended settings. |
| Provider manifest | Signed metadata about a node, supported models, price, runtime, benchmark, policy, privacy modes, and public key. |

---

See also: [../prd/sip-ai.md](../prd/sip-ai.md) and [../prd/sin.md](../prd/sin.md) for how manifests are resolved and published, and [transport-modes.md](transport-modes.md) for the privacy modes a provider manifest can advertise.

_Derived from the v0.1.2 Product Requirements Package._
