# sip-runtime-ollama

Wraps a local [Ollama](https://ollama.com) server (OpenAI-compatible) as a SIP-AI
runtime adapter.

**Status:** Phase 1 implemented — detect / list / pull / serve / chat / health.

**License:** Apache-2.0 — see [LICENSING.md](../../LICENSING.md).

`OllamaAdapter` subclasses the shared `OpenAICompatibleAdapter` from
[`sin-node`](../../packages/sin-node) and registers itself as `"ollama"` on
import. Design ref: [SIN PRD](../../docs/prd/sin.md).
