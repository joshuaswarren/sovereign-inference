# sip-reputation

Health and reputation signals for SIP-AI provider selection. Given providers
discovered via [`sip-discovery`](../discovery), this library:

- **probes health** — `HealthProbe` hits a provider's `/sip/v1/health`, checks the
  advertised public key and model match, and measures latency;
- **tracks reputation** — `ReputationStore` records routing outcomes (success,
  latency, receipt validity) per provider and computes a composite score, persisted
  atomically;
- **ranks** — `rank_providers` orders discovered providers by a blend of reputation,
  liveness, and advertised benchmark, so a router routes to the best live provider.

Every network boundary (the health HTTP client, the clock) is injected, so the
whole module is unit-testable offline.

**Status:** implemented.

**License:** Apache-2.0 — see [LICENSING.md](../../LICENSING.md).

Design refs: [Provider selection](../../docs/provider-selection.md),
[Architecture](../../docs/architecture.md).
