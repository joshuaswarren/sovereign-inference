# Security Policy

Sovereign Inference lets people run model runtimes and optionally expose spare
capacity to a network. Security is a first-class concern — a provider node sits
in front of a user's own machine, so node and gateway safety matter as much as
protocol correctness. See the [threat model](docs/threat-model.md).

## Reporting a vulnerability

**Please do not open public issues for security vulnerabilities.**

Report privately via either:

1. **GitHub Security Advisories** — "Report a vulnerability" on the repository's
   Security tab (preferred), or
2. **Email** — joshua.s.warren@gmail.com with subject `SECURITY: sovereign-inference`.

Please include: affected component/version, reproduction steps or PoC, impact,
and any suggested mitigation. We aim to acknowledge within **3 business days**
and to provide a remediation timeline after triage.

We support coordinated disclosure and will credit reporters who wish to be
credited once a fix is available.

## Scope

In scope:
- The protocol library, receipt/manifest signing & verification.
- The provider gateway, router, PIC issuance/redeem/settle, and node.
- Privilege/isolation issues in runtime adapters and the dashboard.

Especially interesting:
- Receipt or manifest signature forgery / canonicalization ambiguities.
- Provider-gateway sandbox escapes, arbitrary code/model loading, or SSRF.
- PIC double-spend, voucher forgery, or linkability leaks.
- Anything that exposes a local runtime to the internet without explicit opt-in.

Out of scope (for now): the placeholder/scaffolded packages with no
implementation yet, and third-party runtimes/networks we adapt (report those
upstream).

## Supported versions

The project is pre-1.0; security fixes land on `main` and the latest tagged
release. Pin to a tag and watch releases for advisories.
