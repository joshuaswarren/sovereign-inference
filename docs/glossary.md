# Glossary

Definitions for the core terms used across the Sovereign Inference documentation.

| Term | Definition |
| --- | --- |
| SIP-AI | Sovereign Inference Protocol, the routing, payment, manifest, transport, and receipt protocol. |
| SIN | Sovereign Inference Node, the local-first installable node for running and optionally sharing models. |
| PIC | Private Inference Credit, a voucher or token used to pay for inference without directly linking the provider request to the original wallet purchase. |
| Model manifest | Public metadata about a model artifact, hash, format, quantization, license, runtime support, and recommended settings. |
| Provider manifest | Signed metadata about a node, supported models, price, runtime, benchmark, policy, privacy modes, and public key. |
| Signed inference receipt | Provider-signed accountability record for an inference request. |
| Provider gateway | Hardened service that sits in front of the actual model runtime and handles auth, policy, payment, limits, and receipts. |
| Runtime adapter | Connector to a local or remote model engine such as llama.cpp, Ollama, vLLM, SGLang, LocalAI, or LM Studio. |

## Related docs

- [mvp-and-demo.md](mvp-and-demo.md) — how these pieces fit together in the first milestone.
- [threat-model.md](threat-model.md) — the security role of gateways, manifests, receipts, and PIC.
- [references.md](references.md) — sources for the runtimes and standards referenced here.

_Derived from the v0.1.2 Product Requirements Package._
