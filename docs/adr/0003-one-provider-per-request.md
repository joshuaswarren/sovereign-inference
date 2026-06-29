# ADR 0003 — One provider per request in v1

- **Status:** Accepted
- **Date:** 2026-06-29

## Context

Collaborative sharded inference (e.g. Petals) lets several machines jointly serve
one prompt by hosting different model layers. It's important prior art, but it
makes latency, security, provider accountability, and verification much harder.

## Decision

In v1, each inference request is served **in full by exactly one** selected
provider node. Failover happens **between** providers (retry on another provider),
never **within** a single model execution. No public multi-node model sharding.

## Consequences

- Receipts can cleanly attribute a request to one provider key.
- Routing, quoting, and security stay tractable.
- We forgo serving models too large for any single available node in v1; this can
  be revisited later (e.g. trusted LAN clusters via an Exo-style adapter) without
  changing the public sharded-inference stance.

See [architecture](../architecture.md) and the [decision log](../decision-log.md).
