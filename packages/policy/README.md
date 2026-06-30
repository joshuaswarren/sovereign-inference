# sip-policy

A declarative **provider-selection policy** for SIP-AI. A `Policy` decides which
providers a router (or the OpenAI proxy) may use, by:

- **required attestation** — only TEE-attested providers (and which TEE types);
- **price caps** — max input/output price per 1M tokens, and accepted units;
- **required privacy modes** — e.g. `relay`, `private-payment`;
- **allow / deny lists** — by provider public key;
- **minimum reputation** — against an injected reputation score.

`policy.permits(manifest)` returns a `PolicyDecision(ok, reason)`, and
`policy.filter_entries(entries)` keeps only the providers the policy allows — so an
operator can express "only attested, USDC ≤ $0.50/1M, reputation ≥ 0.7" in one place.

**Status:** implemented.

**License:** Apache-2.0 — see [LICENSING.md](../../LICENSING.md).

Design refs: [Provider selection](../../docs/provider-selection.md),
[Architecture](../../docs/architecture.md).
