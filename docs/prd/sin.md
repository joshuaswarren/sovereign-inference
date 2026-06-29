# PRD 2: Sovereign Inference Node (SIN)

SIN is the installable local-first node that turns an ordinary machine into a private AI workstation, a team AI server, or an optional network provider. This document is the product requirements for SIN; it describes the full system we are building, with the MVP framed as the first milestone on the path to the production version.

> **Terminology:** SIP-AI = Sovereign Inference Protocol; SIN = Sovereign Inference Node; PIC = Private Inference Credits.

## Product summary

Sovereign Inference Node is the installable local node that turns an ordinary machine into a private AI workstation, a team AI server, or an optional network provider. SIN handles hardware detection, model recommendation, model fetching, runtime installation, local serving, benchmarking, hardening, and network publication.

## Goals

1. Answer the user question: what is the best open model for my need that will actually run well on this hardware?
2. Install the selected model and runtime with minimal manual setup.
3. Run a local OpenAI-compatible endpoint for private use.
4. Benchmark the node and produce a signed capability manifest.
5. Let the user safely publish spare capacity to the SIP-AI network.
6. Make sharing reversible, capped, policy-controlled, and observable.

## Non-goals

- No attempt to replace Ollama, llama.cpp, vLLM, SGLang, LocalAI, or LM Studio.
- No public model sharding across many strangers in v1.
- No requirement that every user use crypto to run local models.
- No assumption that all providers are always online or professionally operated.
- No exposing local models to the internet without explicit user action.

## Core user flows

### Flow A: What can my machine run?

1. User installs SIN.
2. SIN scans CPU, RAM, GPU, VRAM, OS, drivers, disk, battery/power state, network, and existing runtimes.
3. SIN asks the user what they want to do: chat, code, RAG, embeddings, vision, long context, low latency, private local use, or sharing.
4. SIN recommends model/runtime/quantization combinations with expected speed, memory, and tradeoffs.
5. User chooses one and clicks install or runs one CLI command.

### Flow B: Run privately

1. SIN downloads the model, verifies checksum or manifest hash, shows license summary, and installs or selects the runtime.
2. SIN starts a local server bound to localhost by default.
3. User sends a test prompt through the local dashboard or OpenAI-compatible endpoint.
4. SIN records local benchmark metrics and recommends configuration adjustments.

### Flow C: Share spare capacity

1. User opts into network sharing.
2. SIN runs a provider qualification benchmark.
3. User sets max requests/hour, max bandwidth, spend/earning limits, uptime window, allowed models, logging policy, and safety policy.
4. SIN starts a hardened provider gateway in front of the runtime.
5. SIN publishes a signed provider manifest.
6. Remote SIP-AI client routes a request to this node.
7. Provider earns test credits or settled payment and sees usage metrics.

## Functional requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| SIN-FR-001 | Detect OS, CPU architecture, RAM, disk space, GPU vendor, GPU memory, drivers, and existing model runtimes. | P0 |
| SIN-FR-002 | Recommend at least three model/runtime/quantization combinations for a chosen task. | P0 |
| SIN-FR-003 | Estimate memory fit including model weights and context/KV-cache headroom. | P0 |
| SIN-FR-004 | Fetch and verify a model artifact or call an existing runtime pull command. | P0 |
| SIN-FR-005 | Start a local-only OpenAI-compatible endpoint. | P0 |
| SIN-FR-006 | Run a benchmark for tokens/sec, time to first token, memory usage, and max stable context. | P0 |
| SIN-FR-007 | Create and sign a provider capability manifest. | P0 |
| SIN-FR-008 | Expose network sharing controls with safe defaults and explicit opt-in. | P0 |
| SIN-FR-009 | Run a hardened provider gateway in front of the runtime. | P0 |
| SIN-FR-010 | Enforce quotas, rate limits, request size limits, model allowlists, and logging policy. | P0 |
| SIN-FR-011 | Support payment validation and signed receipt generation. | P1 |
| SIN-FR-012 | Publish provider manifest to local registry and optionally Arweave. | P1 |
| SIN-FR-013 | Provide a simple dashboard for health, earnings, requests, latency, and pause/resume. | P1 |
| SIN-FR-014 | Support adapter plugins for Ollama, llama.cpp, vLLM, SGLang, LocalAI, and LM Studio over time. | P1/P2 |

## Hardware profiler

The profiler produces a user-readable diagnosis and a machine-readable hardware profile. It should not overwhelm users with GPU jargon unless they ask for details.

| Input | How used |
| --- | --- |
| RAM and VRAM | Filter models and quantizations that fit. |
| CPU and instruction set | Choose CPU fallback or optimized runtime. |
| GPU vendor and driver | Choose CUDA, ROCm, Metal/MLX, Vulkan, or CPU path. |
| Disk space | Filter large model downloads and warn about storage. |
| Power/battery/thermal state | Warn laptop users before sharing capacity. |
| Network bandwidth and NAT | Recommend local-only, LAN-only, relay, or public provider mode. |
| Existing runtimes | Reuse Ollama, LM Studio, LocalAI, llama.cpp, or vLLM if already installed. |

## Model recommendation engine

The recommendation engine combines static catalog data, memory estimates, licensing constraints, runtime compatibility, task benchmarks, and local benchmark feedback. A simple first version is enough if it is transparent.

### Fit algorithm

```text
candidate_models = filter_by_task(task)
candidate_models = filter_by_license(candidate_models, commercial_required)
candidate_models = filter_by_runtime_support(candidate_models, hardware_profile)
for model in candidate_models:
    weight_memory = params * quant_bits / 8 * overhead_factor
    kv_headroom = estimate_kv_cache(model, target_context, concurrency)
    total_memory = weight_memory + kv_headroom + runtime_overhead
    fit_score = memory_available / total_memory
    quality_score = benchmark_score_for_task(model, task)
    speed_score = predicted_tokens_per_second(model, hardware_profile, runtime)
    recommendation_score = weighted_sum(fit_score, quality_score, speed_score, license_score, privacy_score)
return ranked_recommendations
```

For rough estimation, the advisor can use published inference memory rules of thumb and improve them with local benchmark data. Modal gives a simple FP16 rule of thumb of about 2GB of GPU memory per 1B parameters, and Hugging Face Accelerate provides a model memory estimator [S32, S33]. Long context must be treated separately because KV cache can become a significant memory consumer [S34].

## Runtime adapter strategy

| Adapter | Best use | Priority |
| --- | --- | --- |
| Ollama | Beginner-friendly local use and existing local installs. | P0 |
| llama.cpp | Reproducible GGUF local serving, CPU/GPU fallback, simple benchmarking. | P0 |
| vLLM | Provider-grade NVIDIA/AMD/GPU serving and higher concurrency. | P1 |
| SGLang | Production serving for advanced providers. | P2 |
| LocalAI | Multi-modal local/on-prem engine and OpenAI-compatible local deployments. | P2 |
| LM Studio | Desktop users who already use LM Studio as a local server. | P2 |
| RamaLama | Linux/container-first local serving path. | P2 |

## Serving and sharing controls

- Local-only is the default.
- LAN/team mode is second.
- Public network sharing is explicit opt-in.
- Prompt logging is off by default for public sharing, but providers can choose stricter or looser policy within legal and network policy bounds.
- Users can cap requests per hour, tokens per request, total tokens per day, bandwidth, CPU/GPU utilization, and operating hours.
- Users can pause sharing instantly.
- The dashboard should show what model is running, who can access it, current request load, expected temperature or utilization concerns, and earned credits.

## Provider benchmark

| Metric | Definition |
| --- | --- |
| Time to first token | Milliseconds from accepted request to first generated token. |
| Tokens per second | Output throughput under standard prompt and generation length. |
| Max stable context | Largest context length that runs without out-of-memory or severe degradation. |
| Concurrency | Number of simultaneous requests that maintain acceptable latency. |
| Memory use | Peak RAM/VRAM for benchmark run. |
| Uptime probe | Whether node responds consistently over a window. |
| Receipt validity | Whether signed receipts verify against provider public key. |

## SIN MVP scope

This MVP is the first milestone of a real, production-bound node, not a throwaway demo. Each step below is implementable now and has a defined path to the full version.

| Capability | MVP decision |
| --- | --- |
| Interface | CLI plus lightweight local web dashboard. |
| Hardware scan | Mac/Linux first, Windows later unless easy. Detect CPU/RAM/disk/GPU where possible. |
| Runtimes | Ollama and llama.cpp first. |
| Model format | GGUF first because Hugging Face supports GGUF metadata and common local tools use it [S21]. |
| Model catalog | 5 curated models across chat, coding, embeddings, and small/fast use. |
| Local serving | localhost OpenAI-compatible endpoint. |
| Sharing | Expose provider gateway and publish signed manifest to local registry. Optional Arweave anchor. |
| Payment | Accept test PIC vouchers and produce signed receipt, with a defined path to full settlement. |
| Dashboard | Health, local model, benchmark, sharing status, requests, receipts, pause/resume. |

## SIN CLI sketch

```text
sin scan
sin recommend --task coding --privacy local --latency balanced
sin install qwen-coder-7b --quant q4_k_m
sin serve --local
sin benchmark
sin share --model qwen-coder-7b --max-requests 50/hour --price auto
sin status
sin pause-sharing
sin verify-receipt receipt.json
```

## SIN success metrics

| Metric | Target |
| --- | --- |
| Time to first local model | Under 15 minutes for a supported machine and selected model. |
| Recommendation explainability | Every recommendation includes why it fits and what tradeoffs it makes. |
| Benchmark reliability | Benchmark produces repeatable tokens/sec and TTFT measurements. |
| Safe default | No public port is opened without explicit opt-in. |
| Network contribution | A clean installed node can publish a manifest and serve one remote request in the demo. |

---

See also: [sip-ai.md](sip-ai.md) for the Sovereign Inference Protocol product requirements, and [../spec/manifests.md](../spec/manifests.md) for the provider manifest format SIN publishes.

_Derived from the v0.1.2 Product Requirements Package._
