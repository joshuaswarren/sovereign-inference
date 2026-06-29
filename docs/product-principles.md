# Product Principles

The nine principles that govern every design and engineering decision in Sovereign Inference. They keep the system local-first, provider-neutral, honest about privacy, and grounded in verifiable evidence.

## The nine principles

1. **Local-first.** The best request is the one the user can run privately on their own machine. SIN exists to make local inference the default path, and the protocol only reaches for remote providers when local is not possible or not preferred.

2. **Provider-neutral.** Plug into existing runtimes and networks instead of trying to replace all of them. SIP-AI is adapter-first: it wraps Ollama, llama.cpp, vLLM, SGLang, LocalAI, LM Studio, and decentralized networks rather than forcing one engine, chain, or marketplace.

3. **One provider per request in v1.** No public multi-node model sharding for the first product generation. Each request is served in full by a single provider, and failover happens between providers, not within one model execution. This keeps latency, security, accountability, and verification tractable [S20].

4. **Privacy without magical claims.** Reduce metadata leakage and improve resilience, but do not claim traffic is impossible to detect or block. The system promises layered resilience, reduced linkability, and transparent tradeoffs — never invisibility or guaranteed censorship bypass.

5. **OpenAI-compatible where practical.** Reduce migration friction for users and apps by exposing an OpenAI-compatible interface, so existing SDKs and clients can adopt Sovereign Inference with minimal changes.

6. **Public provenance, private prompts.** Store model manifests and public receipts on durable storage (Arweave), not user prompts. Provenance and trust data are public and permanent; prompts, completions, and user identity stay private and local.

7. **Safe by default.** Never expose raw model runtimes directly to the open internet without a hardened gateway. The provider gateway enforces auth, quotas, policy, request limits, and receipt generation, and local-only serving is the default until a user explicitly opts into sharing.

8. **Composable economics.** Support x402 direct payment first, then Private Inference Credits (PIC) for unlinkability. Direct payment is the first implementable step for monetization; PIC is the privacy-preserving credit primitive on a defined path to its full cryptographic implementation.

9. **Evidence over ideology.** Every claim should be backed by code, measurements, traces, manifests, and reproducible demos. This matters especially for the hackathon, where DecentralizeAI values real implementation, technical depth, impact, and verifiable evidence [S2, S3].

See also: [Vision](vision.md), [Opportunity](opportunity.md), [Naming and Brand](naming-and-brand.md).

_Derived from the v0.1.2 Product Requirements Package._
