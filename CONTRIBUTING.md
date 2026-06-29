# Contributing to Sovereign Inference

Thanks for helping build an open, provider-neutral access layer for open AI.
This project is built **for real** — contributions ship working code with tests,
not mockups.

## Ground rules

- Be excellent to each other — see the [Code of Conduct](CODE_OF_CONDUCT.md).
- Read the relevant [docs](docs/README.md) before large changes; align with the
  [product principles](docs/product-principles.md) and [architecture](docs/architecture.md).
- **Test-first.** Write a failing test that describes the behavior, make it pass,
  then refactor. We target ≥ 90% coverage across the repo.
- Keep PRs focused and ideally ≤ 400 lines of diff (or explain why not).

## Prerequisites

- **Python 3.12+** and [**uv**](https://docs.astral.sh/uv) for the Python workspace.
- **Node 20+** and [**pnpm**](https://pnpm.io) for the TypeScript packages.
- `git`, and (optional) `pre-commit`.

## Setup

```console
git clone https://github.com/joshuaswarren/sovereign-inference
cd sovereign-inference

# Python workspace (installs every package editable + dev tools)
uv sync

# JavaScript/TypeScript workspace
pnpm install

# Optional: install the git hooks
uv run pre-commit install
```

## Quality gates (run before every PR)

```console
make check          # runs everything below, or individually:

uv run ruff format --check packages adapters
uv run ruff check packages adapters
uv run mypy packages/sip-protocol/src packages/receipt-verifier/src
uv run pytest
pnpm -r test        # once TS packages have tests
```

All gates must pass before a PR is opened. CI ([.github/workflows](.github/workflows))
runs the same checks.

## Developer Certificate of Origin (DCO)

We use the [DCO](https://developercertificate.org/) instead of a CLA. Every
commit must be signed off, certifying you have the right to contribute it:

```console
git commit -s -m "feat(router): add provider failover"
```

This appends a `Signed-off-by: Your Name <you@example.com>` line. Use a real
name and a reachable email.

## Commits & branches

- Branch from `main`: `feat/...`, `fix/...`, `docs/...`, `chore/...`.
- Prefer [Conventional Commits](https://www.conventionalcommits.org/) messages.
- Reference issues (`Closes #123`) where relevant.

## Where things live

- Code: `packages/` (Python), `adapters/`, `sdk-js/` (TS), `apps/` (TS).
- Specs & design: `docs/` (start at [docs/README.md](docs/README.md)).
- Architecture decisions: `docs/adr/` (add an ADR for significant choices).

## Licensing of contributions

By contributing, you agree your contribution is licensed under the license of
the directory you're changing — Apache-2.0 or AGPL-3.0 per
[LICENSING.md](LICENSING.md). Keep the `SPDX-License-Identifier` header on new
source files.

## Good first contributions

Check issues labeled `good-first-issue` and the [ROADMAP](ROADMAP.md). Runtime
adapters (`adapters/`) and model-catalog entries (`registry/`) are
self-contained, Apache-licensed, and a great place to start.
