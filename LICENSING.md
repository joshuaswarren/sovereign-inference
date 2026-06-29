# Licensing

Sovereign Inference uses a **deliberate split license model**. The goal is two
things at once: let the *protocol* and *client* pieces spread as widely as
possible, while ensuring the *server/infrastructure* pieces can't be taken
closed-source and run as a proprietary hosted fork ("embrace, extend,
extinguish").

## The split

| License | Applies to | Why |
| --- | --- | --- |
| **Apache-2.0** | The protocol spec & JSON schemas (`docs/spec/`), the protocol library (`packages/sip-protocol`), the receipt verifier (`packages/receipt-verifier`), all runtime/provider adapters (`adapters/`), and the TypeScript client SDK (`sdk-js/`). | A protocol only wins by being implemented everywhere. Apache-2.0 maximizes adoption and adds an explicit patent grant. |
| **AGPL-3.0** | The server & infrastructure apps: `packages/router`, `packages/provider-gateway`, `packages/pic-vouchers`, `packages/sin-node`, `packages/sin-cli`, and `apps/dashboard` (and `apps/router-demo`). | These are the parts someone could run as a hosted service. AGPL's network-copyleft means a modified hosted version must publish its source — keeping forks open. |

The repository's default/top-level [`LICENSE`](LICENSE) is Apache-2.0. The full
AGPL text is in [`LICENSE-AGPL`](LICENSE-AGPL). Each package states its license in
its `pyproject.toml`/`package.json` and via an `SPDX-License-Identifier` header
in its source files; that per-file identifier is authoritative.

## Why this is compatible

Apache-2.0 is one-way compatible with AGPL-3.0: AGPL-licensed server code may
depend on the Apache-licensed `sip-protocol` and SDKs. The Apache-licensed
pieces never depend on AGPL code, so integrators who only use the SDKs, spec, or
adapters take on **no** AGPL obligations.

## What this means for you

- **Building an app/client on SIP-AI?** You use the Apache-2.0 SDK and spec —
  integrate freely in open or closed software.
- **Writing a new runtime or provider adapter?** Apache-2.0 — contribute it or
  ship it however you like.
- **Running a modified router/gateway/node as a network service?** AGPL-3.0
  applies — you must offer your modified source to your users.

## Contributions & a future commercial option

Contributions are accepted under the **Developer Certificate of Origin (DCO)** —
sign off your commits with `git commit -s` (see [CONTRIBUTING.md](CONTRIBUTING.md)).
Keeping the AGPL components copyright-clean preserves the option of an optional
commercial/dual license for organizations that cannot accept AGPL terms, without
ever closing the open version. No CLA is required today.

If anything here is ambiguous for your use case, open a discussion — we'd rather
clarify than have you guess.
