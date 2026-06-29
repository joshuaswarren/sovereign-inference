# ADR 0001 — Split Apache-2.0 / AGPL-3.0 licensing

- **Status:** Accepted
- **Date:** 2026-06-29

## Context

We want the protocol and clients to be adopted as widely as possible, but we
also want to prevent a company from taking the server/infrastructure code
closed-source and running it as a proprietary hosted fork
("embrace-extend-extinguish"). A single license can't optimize both goals: a
permissive license maximizes adoption but allows closed forks; a strong copyleft
license deters adoption (especially for an SDK linked into closed apps).

## Decision

Use a split:

- **Apache-2.0** for the protocol spec, JSON schemas, the `sip-protocol`
  library, the receipt verifier, runtime/provider adapters, and the TS SDK.
- **AGPL-3.0** for the server/infrastructure apps: router, provider gateway, PIC
  issuer, SIN node/CLI, and the dashboard.

Contributions are taken under the DCO. Apache→AGPL is one-way compatible, so the
AGPL servers may depend on the Apache library and SDK.

## Consequences

- App developers integrate the SDK/spec with no copyleft obligations.
- Anyone running a modified router/gateway/node as a service must publish source.
- A future optional commercial/dual license remains possible (DCO keeps the AGPL
  components copyright-clean) without ever closing the open version.
- Slightly more contributor overhead: per-directory licenses and SPDX headers.

See [LICENSING.md](../../LICENSING.md).
