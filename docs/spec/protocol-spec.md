# SIP-AI Protocol Specification (v0.1)

The authoritative index for the Sovereign Inference Protocol: request lifecycle,
endpoints, document formats, and the rules clients and providers must follow.
This is a living spec; the version tag advances as formats stabilize.

- **Spec version:** `sip-ai/0.1`
- **Status:** draft, implementation in progress
- **Schemas:** [`docs/spec/schemas/`](schemas) (also bundled in
  [`sip-protocol`](../../packages/sip-protocol) and validated in CI)

## Companion documents

| Topic | Document |
| --- | --- |
| Signed inference receipts | [receipts.md](receipts.md) |
| Model & provider manifests | [manifests.md](manifests.md) |
| Provider selection & scoring | [provider-selection.md](provider-selection.md) |
| Transport modes | [transport-modes.md](transport-modes.md) |
| Private Inference Credits (PIC) | [private-inference-credits.md](private-inference-credits.md) |

## Request lifecycle

1. **Client declares intent**: model, task, privacy mode, budget, latency
   preference, max tokens, and verification level.
2. **Resolver** fetches the model manifest and candidate provider manifests.
3. **Router** scores available providers and requests a quote from top candidates.
4. **Client authorizes payment** via direct x402 flow or redeems a PIC voucher.
5. **Client sends** the inference request to the selected provider gateway over
   the chosen transport.
6. **Provider gateway validates** payment, policy, quotas, request size, and
   model availability.
7. **Provider runtime executes** the full model locally on that provider node.
8. **Provider returns** the response plus a signed inference receipt.
9. **Client verifies** the receipt signature, manifest references, token counts,
   and payment settlement metadata.
10. **Router updates** local reputation and optionally publishes non-sensitive
    receipt or benchmark metadata.

## Interfaces

### OpenAI-compatible path

A drop-in endpoint so existing OpenAI SDKs work with minimal change. SIP-AI
behavior is controlled with `X-SIP-*` headers.

```http
POST /v1/chat/completions
Authorization: Bearer <local-or-network-token>
X-SIP-Privacy-Mode: private-payment-relay
X-SIP-Budget: 0.01
X-SIP-Verification: signed-receipt

{
  "model": "qwen-coder-7b-instruct-gguf-q4_k_m",
  "messages": [{"role": "user", "content": "Write a small parser."}],
  "max_tokens": 256
}
```

| Header | Meaning | Values |
| --- | --- | --- |
| `X-SIP-Privacy-Mode` | Requested privacy/transport mode | `local-only`, `direct`, `relay`, `private-payment`, `private-payment-relay`, `confidential`, `batch` |
| `X-SIP-Budget` | Max spend for this request | decimal string, in the negotiated unit |
| `X-SIP-Verification` | Verification level requested | `none`, `signed-receipt`, `confidential` |

The successful response carries the model output plus a `X-SIP-Receipt` header
(or `sip_receipt` body field) containing the [signed receipt](receipts.md).

### SIP-specific endpoints

```http
GET  /sip/v1/models
GET  /sip/v1/providers?model=<model_id>
POST /sip/v1/quote
POST /sip/v1/redeem-credit
POST /sip/v1/verify-receipt
GET  /sip/v1/provider-health/<provider_id>
POST /sip/v1/publish-provider-manifest
POST /sip/v1/publish-model-manifest
```

## Cryptographic conventions

- **Signatures:** Ed25519. Keys and signatures are encoded as
  `ed25519:<base64url>` (no padding). Public keys are 32 bytes; signatures 64.
- **Hashes:** SHA-256, encoded as `sha256:<hex>`.
- **Canonicalization:** signed documents are serialized with an RFC 8785–compatible
  canonical JSON (sorted keys, compact separators, UTF-8, no NaN/Infinity). The
  detached `signature` field is excluded from the bytes being signed. Monetary
  amounts are encoded as **decimal strings** to keep the signed payload
  byte-deterministic. The reference implementation lives in
  [`sip_protocol.canonical`](../../packages/sip-protocol/src/sip_protocol/canonical.py).

## Conformance

An implementation conforms to `sip-ai/0.1` if it:

1. Produces/accepts model and provider manifests valid against the published
   JSON Schemas.
2. Generates receipts that validate against the receipt schema **and** whose
   signatures verify with the stated canonicalization rule.
3. Routes one request to exactly one provider and fails over on provider error
   without splitting a single model execution.
4. Honors the provider's advertised logging/retention policy and never logs
   prompts when `no_prompt_logging` is advertised.

_Derived from the v0.1.2 Product Requirements Package; formats are normative as
the reference implementation matures._
