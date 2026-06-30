# sip-directory-service

A hosted SIP-AI **provider directory** — the relay form of
[`sip-discovery`](../../packages/discovery). Nodes `POST` their signed provider
manifests; routers `GET` verified providers to route to.

```console
sip-directory-service --store ~/.sip/directory.json --host 0.0.0.0 --port 8088
```

The service is a thin FastAPI over any `sip_discovery.Directory` store (a
`FileDirectory` by default), so it inherits **signature verification on announce**
and **freshest-per-provider** discovery. Clients use
`sip_discovery.HttpDirectory(base_url)`, which **re-verifies every manifest** and
derives the routed endpoint from the signed `manifest_uri` — the relay is never
trusted to redirect traffic.

**Status:** implemented.

**License:** AGPL-3.0-or-later — see [LICENSING.md](../../LICENSING.md).

Design refs: [Architecture](../../docs/architecture.md),
[Provider selection](../../docs/provider-selection.md).
