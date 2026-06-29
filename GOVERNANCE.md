# Governance

Sovereign Inference is a young open-source project. Governance is intentionally
lightweight now and will formalize as the contributor base grows.

## Current model

- **Maintainer-led.** Joshua Warren ([@joshuaswarren](https://github.com/joshuaswarren))
  is the founding maintainer and current project lead, with final say on scope,
  architecture, and releases.
- Decisions are made in the open via issues, pull requests, and discussions.
- Significant or hard-to-reverse technical decisions are recorded as
  **Architecture Decision Records** in [`docs/adr/`](docs/adr) and reflected in the
  [decision log](docs/decision-log.md).

## How changes are decided

1. Propose via an issue or discussion (or an ADR for architectural changes).
2. Rough consensus among active maintainers; the project lead resolves deadlocks.
3. Changes land via reviewed PRs that pass all CI gates.

The [product principles](docs/product-principles.md) are the tie-breaker: a change
that violates local-first, provider-neutral, one-provider-per-request,
safe-by-default, or honest-privacy-claims needs an explicit, recorded rationale.

## Becoming a maintainer

Contributors who land meaningful, sustained work and show good judgment in
review may be invited as maintainers (commit + triage rights). Maintainers are
expected to uphold the Code of Conduct and the quality gates.

## Roadmap & priorities

The [ROADMAP](ROADMAP.md) reflects current priorities, including the
[DecentralizeAI hackathon](docs/hackathon/decentralizeai-submission.md) Round 1
milestones. Priorities are revisited as the project evolves.

## Evolving this document

As the community grows we expect to adopt a more formal structure (e.g. a
maintainers' council and a written voting process). Proposals to change
governance are themselves made via PR to this file.
