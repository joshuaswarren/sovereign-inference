# sip-protocol

Shared Sovereign Inference Protocol (SIP-AI) primitives, used by every other
package in this repo.

- **Canonical JSON** (RFC 8785-compatible subset) for deterministic signing.
- **Ed25519** key handling, signing, and verification (`ed25519:<base64url>`).
- **Signed inference receipts** — build, sign, and verify accountability artifacts.
- **Model & provider manifests** — content-addressing, signing, and validation.
- **JSON Schema validation** against the authoritative schemas in
  [`docs/spec/schemas/`](../../docs/spec/schemas).

**License:** Apache-2.0 (a foundational library meant for the widest possible
adoption — see [LICENSING.md](../../LICENSING.md)).

```python
from datetime import datetime, timezone
from sip_protocol import KeyPair, build_receipt, sign_receipt, verify_receipt, hash_response_body

kp = KeyPair.generate()
receipt = build_receipt(
    request_id="req-1",
    provider_pubkey=kp.public_key_str,
    model_manifest_hash="sha256:" + "0" * 64,
    model_alias="qwen-coder-7b-instruct-gguf-q4_k_m",
    runtime="llama.cpp",
    input_tokens=817,
    output_tokens=242,
    price_units="pic",
    price_amount="0.0042",
    privacy_mode="direct",
    started_at=datetime.now(timezone.utc),
    completed_at=datetime.now(timezone.utc),
    response_hash=hash_response_body("hello world"),
)
signed = sign_receipt(receipt, kp)
assert verify_receipt(signed).valid
```
