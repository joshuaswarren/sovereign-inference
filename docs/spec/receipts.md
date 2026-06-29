# Signed Inference Receipts

The authoritative format for SIP-AI receipts. A receipt is a verifiable
**accountability artifact** — not a cryptographic proof that a specific model
computed a specific answer. It lets any client confirm *who* served a request,
*what* was claimed, *what* it cost, and that the response was not altered after
signing. This format is implemented and tested in
[`sip-protocol`](../../packages/sip-protocol) and verified by the
[`sip-receipt`](../../packages/receipt-verifier) CLI.

- **Schema:** [`schemas/inference_receipt.schema.json`](schemas/inference_receipt.schema.json)
- **Version tag:** `sip-ai.receipt.v1`

## What a receipt proves (and doesn't)

| It proves | It does **not** prove |
| --- | --- |
| Which provider key signed the receipt | That the named model actually produced the output |
| The claimed model manifest hash, runtime, and version | That the runtime/quantization claim is truthful |
| Token counts and price charged | Anything about the *content* of the prompt |
| That the response body matches `response_hash` | Confidentiality of the computation (see TEE modes) |

Stronger guarantees (e.g. TEE attestation, and eventually verifiable execution)
are layered on top in later milestones — see the [roadmap](../roadmap.md). We
call receipts "accountability artifacts" precisely so users don't over-trust them.

## Fields

| Field | Type | Notes |
| --- | --- | --- |
| `receipt_version` | string | Always `sip-ai.receipt.v1`. |
| `request_id` | string | Opaque, client-generated. MUST NOT encode user identity. |
| `provider_pubkey` | string | `ed25519:<base64url>` provider public key. |
| `model_manifest_hash` | string | `sha256:<hex>` of the claimed model manifest. |
| `model_alias` | string | Human-readable model id. |
| `runtime` | enum | `llama.cpp`, `ollama`, `vllm`, `sglang`, `localai`, `lmstudio`, `ramalama`. |
| `runtime_version` | string | Optional but recommended. |
| `input_tokens` / `output_tokens` | integer | Billed token counts. |
| `price_units` | enum | `pic`, `usdc`, `x402`, `test`. |
| `price_amount` | string | Decimal **string** (avoids float non-determinism in signing). |
| `privacy_mode` | enum | The transport/privacy mode used. |
| `started_at` / `completed_at` | string | RFC 3339 timestamps. |
| `response_hash` | string | `sha256:<hex>` of the canonical response body. |
| `signature` | string | `ed25519:<base64url>` over the canonical receipt minus `signature`. |

## Example

```json
{
  "receipt_version": "sip-ai.receipt.v1",
  "request_id": "opaque-client-generated-id",
  "provider_pubkey": "ed25519:SlAH5zFV_kkKxiz8_5O9hbUlp8rU3AmxokAIVcS-xa8",
  "model_manifest_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "model_alias": "qwen-coder-7b-instruct-gguf-q4_k_m",
  "runtime": "llama.cpp",
  "runtime_version": "b3000",
  "input_tokens": 817,
  "output_tokens": 242,
  "price_units": "pic",
  "price_amount": "0.0042",
  "privacy_mode": "private-payment-relay",
  "started_at": "2026-06-29T18:15:02Z",
  "completed_at": "2026-06-29T18:15:09Z",
  "response_hash": "sha256:...",
  "signature": "ed25519:..."
}
```

## Signing & verification rule

1. Remove the `signature` field.
2. Serialize the remaining object with canonical JSON (sorted keys, compact
   separators, UTF-8, no NaN/Infinity).
3. Sign those bytes with the provider's Ed25519 private key; encode the 64-byte
   signature as `ed25519:<base64url>` and place it back in `signature`.
4. To verify: re-derive the signing bytes the same way and check the signature
   against `provider_pubkey`. Verification also runs full JSON Schema validation.

A change to **any** signed field (a single token count, the response hash, the
price) invalidates the signature — this is covered by the test suite and
demonstrable with the CLI.

## Verify it yourself

```console
$ sip-receipt demo > receipt.json     # emit a freshly signed sample
$ sip-receipt verify receipt.json
OK   receipt verified — provider ed25519:...

$ # tamper with any field and it fails, exit code 1:
$ jq '.output_tokens = 1' receipt.json > bad.json && sip-receipt verify bad.json
FAIL receipt did not verify:
  - signature: invalid or missing provider signature
```

Reference implementation:
[`sip_protocol/receipts.py`](../../packages/sip-protocol/src/sip_protocol/receipts.py).

_Derived from the v0.1.2 Product Requirements Package; this document is normative._
