# sip-provider-gateway

The hardened front door a Sovereign Inference Node exposes to the network. It
enforces policy before the runtime is ever called and never exposes the raw
runtime.

**Status:** Phase 2 implemented.

**License:** AGPL-3.0-or-later — see [LICENSING.md](../../LICENSING.md).

`create_app(adapter=..., keypair=..., allowed_models=[...], token=..., ...)`
builds a FastAPI app speaking the SIP-AI wire contract:

- `GET /sip/v1/health` — liveness + advertised models.
- `GET /sip/v1/provider-manifest` — the signed provider manifest.
- `POST /sip/v1/quote` — a signed, expiring price commitment (`sip-ai.quote.v1`).
- `POST /v1/chat/completions` — OpenAI-compatible inference returning a
  provider-signed receipt (`sip-ai.receipt.v1`).

Enforced before serving: bearer auth (constant-time), model allowlist,
output-token + input-size caps, an in-memory rate limit, and logging policy. A
`MockAdapter` is provided for tests and the demo. Wraps the runtime via the
[`sin_node`](../sin-node) adapter protocol. See the
[protocol spec](../../docs/spec/protocol-spec.md).
