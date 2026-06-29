# ADR 0002 — Python core, TypeScript dashboard & SDK

- **Status:** Accepted
- **Date:** 2026-06-29

## Context

The system must run on macOS, Linux, and Windows and eventually be usable by
non-technical users. The hard parts of the node — GPU/VRAM detection, model
memory estimation, and adapters to llama.cpp/vLLM/SGLang — live in a
Python-native ecosystem. The dashboard and a developer-facing client SDK are
inherently web/JS work.

## Decision

- **Python 3.12+** (managed with `uv`) for the core: `sip-protocol`, receipt
  verifier, router, provider gateway, PIC, SIN node, and CLI. Tooling: `ruff`,
  `mypy --strict`, `pytest`.
- **TypeScript** for the React/Vite dashboard and the `@sovereign-inference/sdk`
  client.
- Cross-platform distribution for non-technical users is treated as a
  **packaging** concern, not a language choice: a planned **Tauri** desktop shell
  bundles the Python node as a sidecar with the React dashboard for one-click
  install (Phase 6).

## Consequences

- We get the mature Python inference ecosystem for the node's hard problems.
- Web developers get an idiomatic TypeScript SDK.
- A polyglot monorepo (uv workspace + pnpm workspace) with two CI lanes.
- Desktop packaging work is deferred but explicitly planned.
