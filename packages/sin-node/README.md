# sin-node

The Sovereign Inference Node core: turns an ordinary machine into a private AI
workstation and optional network provider.

**Status:** Phase 1 implemented — hardware profiler, model recommendation engine,
runtime-adapter contract, benchmark runner, and a local status API.

**License:** AGPL-3.0-or-later — see [LICENSING.md](../../LICENSING.md).

## What's here
- `hardware.scan()` — cross-platform CPU/RAM/disk/GPU/VRAM + runtime detection.
- `recommend.recommend()` — rank model/runtime/quant choices for a task and machine.
- `catalog.load_catalog()` — the curated model catalog.
- `memory.estimate_memory()` — weights + KV-cache + overhead estimate.
- `benchmark` — tokens/sec, TTFT, and a signed provider capability manifest.
- `adapter` — the `RuntimeAdapter` protocol + registry and an OpenAI-compatible base.
- `http` — OpenAI-compatible client with streaming TTFT/tokens-per-sec timing.
- `api.create_app()` — a FastAPI status API for the dashboard.

Driven by the [`sin` CLI](../sin-cli). Design refs:
[Architecture](../../docs/architecture.md), [SIN PRD](../../docs/prd/sin.md).
