# Registry

Public, portable metadata that creates transferable trust. Manifests are stored
here as JSON first and can later be anchored on Arweave for permanence.

- `model-manifests/` — open-model metadata (hash, format, quantization, license,
  runtime support, memory needs). Validates against
  [`model_manifest.schema.json`](../docs/spec/schemas/model_manifest.schema.json).
- `provider-manifests/` — signed node advertisements (models, pricing, policy,
  privacy modes, benchmark, public key). Validates against
  [`provider_manifest.schema.json`](../docs/spec/schemas/provider_manifest.schema.json)
  and the signature verifies with `verify_provider_manifest`.

The committed `provider-manifests/example-sovereign-node.json` is a **real signed
manifest** — its Ed25519 signature verifies against its embedded `provider_pubkey`.

See [docs/spec/manifests.md](../docs/spec/manifests.md).
