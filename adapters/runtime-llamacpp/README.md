# sip-runtime-llamacpp

Wraps a [llama.cpp](https://github.com/ggml-org/llama.cpp) `llama-server` (GGUF,
OpenAI-compatible) as a SIP-AI runtime adapter.

**Status:** Phase 1 implemented — detect / build-command / serve (with health
polling and subprocess lifecycle) / chat / health / stop.

**License:** Apache-2.0 — see [LICENSING.md](../../LICENSING.md).

`LlamaCppAdapter` subclasses the shared `OpenAICompatibleAdapter` from
[`sin-node`](../../packages/sin-node) and registers itself as `"llama.cpp"` on
import. It manages a `llama-server` subprocess (reaped and SIGKILL-escalated on
stop). Models are local GGUF paths. Design ref: [SIN PRD](../../docs/prd/sin.md).
