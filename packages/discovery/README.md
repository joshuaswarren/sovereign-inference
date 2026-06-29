# sip-discovery

Provider discovery for SIP-AI. A node **announces** its signed provider manifest
to a **directory**; a router **discovers** verified providers from that directory
and routes to them — turning a manifest into something other people's routers can
find without manual registry editing.

Two directories ship:

- **`FileDirectory`** — a shared JSON file (offline, deterministic; for a LAN, a
  synced folder, or tests). Verifies every manifest signature on announce and on
  discover, keyed by provider public key.
- **`ArweaveDirectory`** — announce by anchoring the manifest to Arweave with
  discovery tags; discover by querying those tags (the GraphQL boundary is
  injected, so it is fully unit-testable offline).

Discovery always **verifies the manifest signature** before surfacing a provider,
and de-duplicates by public key keeping the freshest `published_at`.

**Status:** implemented.

**License:** Apache-2.0 — see [LICENSING.md](../../LICENSING.md).

Design refs: [Architecture](../../docs/architecture.md),
[Provider selection](../../docs/provider-selection.md),
[SIP-AI PRD](../../docs/prd/sip-ai.md).
