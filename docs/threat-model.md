# Threat Model

A structured threat model for Sovereign Inference, covering the assets we protect, the trust boundaries between components, the threats we expect, and the controls we are building to address them. It draws on the protocol's security and abuse controls, the node's serving and sharing controls, and the project risk register, and organizes them in STRIDE-style categories. It stays faithful to the controls stated in the requirements; it does not invent new guarantees.

## Scope and stance

Sovereign Inference routes one user request to one provider node that holds the full selected model. The system aims for **layered resilience and transparent tradeoffs**, not absolute anonymity. We explicitly do not promise that traffic is undetectable or unblockable, nor that a signed receipt is a mathematical proof that a particular model produced a particular answer. Receipts are accountability artifacts, not zero-knowledge proofs of execution.

## Assets

| Asset | Why it matters |
| --- | --- |
| User prompts and completions | Sensitive content; must never be written to public registries. |
| User identity and payment linkage | Linking a wallet or purchase to each prompt erodes the core privacy promise. |
| Provider private keys | Used to sign receipts and provider manifests; compromise enables impersonation. |
| Provider host machine and runtime | A provider's CPU/GPU, OS, and model runtime; compromise can harm the operator. |
| Model weights and license compliance | Serving an unlicensed or disallowed model creates legal exposure. |
| Private Inference Credits (PIC vouchers) | Bearer value; double-spend or forgery is direct financial fraud. |
| Signed inference receipts | The accountability record clients rely on; forgery breaks trust. |
| Model and provider manifests | Public trust data; tampering misleads routing and reputation. |

## Trust boundaries

```text
Client (app / CLI / SDK)
  | boundary: client <-> router (intent, budget, privacy mode)
Router and provider selector
  | boundary: router <-> provider gateway (quote, request, payment)
Provider gateway (hardened front door)
  | boundary: gateway <-> runtime (isolated local execution)
Runtime (llama.cpp / Ollama / vLLM / ...)
  | boundary: client/provider <-> issuer & settlement (credit purchase / redemption)
PIC issuer and settlement layer
  | boundary: anyone <-> registry/storage (public manifests, receipts)
Registry / durable storage (Arweave anchor)
```

Each boundary is a place where data changes hands and where a control must enforce authentication, policy, isolation, or verification. Private transport modes (relay, and later Tor/I2P/Nym-compatible adapters) add boundaries between the client and provider but are opt-in with explicit latency and reliability warnings.

## Threats and controls (STRIDE-style)

### Spoofing (identity)

- **Threat:** A malicious node impersonates a trusted provider, or a forged receipt claims a provider that did not serve the request.
- **Controls:** Provider gateways authenticate requests. Receipts are signed with the provider's Ed25519 key and reference the provider public key, model manifest hash, runtime/version, token counts, cost, and a response hash; clients verify the signature with the receipt verifier. Provider manifests are signed.

### Tampering (integrity)

- **Threat:** Altered manifests, prices, or receipts; tampering with model artifacts.
- **Controls:** Model manifests carry a weights hash and maintainer signature; provider manifests are signed. Receipts are signed over canonical JSON and include a response hash. Public manifests and receipts are anchored to durable storage (Arweave) for portable, tamper-evident trust.

### Repudiation (accountability)

- **Threat:** A provider denies what it served, or disputes pricing and usage.
- **Controls:** Signed inference receipts bind provider key, model manifest hash, runtime version, price, token counts, timestamps, and response hash into a verifiable record. Receipts are framed as accountability artifacts and feed provider reputation (uptime, receipt validity, benchmark drift, latency, dispute history).

### Information disclosure (privacy)

- **Threat:** Prompts or user identity leak; payment metadata links a wallet to each prompt; network metadata fingerprints sensitive users.
- **Controls:** Default system never stores prompts in public registries; logging and retention policy are explicit and surfaced to the user before routing sensitive requests. Prompt logging is off by default for public sharing. Private Inference Credits separate credit purchase from redemption so the provider can verify a valid, unspent voucher without learning which wallet bought it; the privacy claim is made explicit and measurable in docs. Layered transport modes (direct, relay, and later mixnet-compatible) reduce metadata leakage. Routing never makes jurisdiction mandatory unless the user opts in, to avoid creating privacy fingerprints.

### Denial of service / abuse (availability)

- **Threat:** Provider abuse or illegal use; request floods; oversized contexts exhausting memory; cold-start with no available providers.
- **Controls:** Providers choose which models they serve and which request classes they allow (model allowlists, blocked request classes). Gateways enforce request size, context length, concurrency, and spend caps, plus rate limits and abuse throttles. Public network sharing is explicit opt-in and off by default. Operators can cap requests/hour, tokens/request, tokens/day, bandwidth, CPU/GPU utilization, and operating hours, and can pause sharing instantly. Routing detects failed providers and fails over to another provider when budget and privacy settings permit. Easy provider onboarding plus integration of existing compute networks mitigates cold start.

### Elevation of privilege (host and runtime compromise)

- **Threat:** A request triggers arbitrary code, shell execution, or remote model loading and compromises the provider's machine.
- **Controls:** Provider nodes must not allow arbitrary remote model loading, custom code execution, or shell execution through the inference endpoint. The gateway isolates runtime access, runs with least privilege, uses container sandboxing, and has an auto-update path. Local-only is the default; LAN/team mode is second; public sharing requires explicit opt-in and never opens a public port without it.

## Payment fraud and double-spend

- **Threat:** Forged or replayed PIC vouchers; double-spending the same credit; provider over-redeeming.
- **Controls:** Double spend is prevented in the MVP environment. Vouchers support expiry and denomination to reduce abuse and simplify accounting. Providers settle and audit aggregate balances with the issuer/settlement layer. The cryptographic upgrade path (drawing on Chaumian ecash and privacy-token patterns) is documented so the simple first form can harden without re-architecting the privacy boundary [S30, S31].

## Model-license violations

- **Threat:** Serving a model in violation of its license, creating commercial or legal risk.
- **Controls:** The model catalog stores license flags and warnings; providers must accept license terms before serving. License metadata is part of the model manifest and is factored into recommendations and listing eligibility.

## Privacy overclaim

- **Threat:** Users assume stronger anonymity or verification than the system provides.
- **Controls:** Use precise language — reduced linkability, layered transport, no guarantee of undetectability or unblockability. Private transport modes carry explicit warnings. Receipts are described as accountability artifacts, not proof of model execution.

## Related docs

- [risk-register.md](risk-register.md) — the project-level risks that feed this model.
- [mvp-and-demo.md](mvp-and-demo.md) — where these controls appear in the demo.
- [glossary.md](glossary.md) — definitions for gateway, manifests, receipts, and PIC.
- [references.md](references.md) — sources behind the [S#] citations above.

_Derived from the v0.1.2 Product Requirements Package._
