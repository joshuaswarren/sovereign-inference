# Decision Log

The key product and architecture decisions for Sovereign Inference, with their current status and the rationale behind each. This log records why the system is shaped the way it is.

| Decision | Status | Rationale |
| --- | --- | --- |
| Build both SIP-AI and SIN. | Accepted | Demand side needs routing; supply side needs easy provider onboarding. |
| One provider handles one complete request in v1. | Accepted | Avoids latency, sharding, accountability, and verification complexity. |
| Use existing runtimes instead of building a new inference engine. | Accepted | Ollama, llama.cpp, vLLM, SGLang, LocalAI, and LM Studio already solve core serving [S10, S11, S12, S13, S14, S15]. |
| Use Arweave for public manifests, not private prompts. | Accepted | Permanent provenance fits Arweave; prompt privacy requires local/private storage [S9]. |
| Use x402 for direct payment and PIC for privacy-preserving payment. | Accepted | x402 is simple for APIs; PIC addresses wallet-request linkage [S5, S30, S31]. |
| Use SIP-AI externally instead of the raw SIP acronym where ambiguity matters. | Proposed | Avoids conflict with Session Initiation Protocol [S4]. |

## Related docs

- [open-questions.md](open-questions.md) — decisions not yet made.
- [glossary.md](glossary.md) — definitions for the terms above.
- [references.md](references.md) — sources behind the [S#] citations.

_Derived from the v0.1.2 Product Requirements Package._
