# Releasing Sovereign Inference

This is the supply-chain and release process for the Python packages in this
monorepo. The goal: every published artifact is **reproducible, audited, and
signed**, so users can verify what they install.

## What CI already guarantees on every PR

- **Tests + types** — `pytest` across Linux and macOS, `mypy --strict` on the
  typed packages (`.github/workflows/python.yml`).
- **Lint/format** — `ruff check` + `ruff format --check`.
- **Dependency audit** — `pip-audit` over the locked dependency set (advisory; see
  the `security` job). The lockfile (`uv.lock`) pins every transitive dependency
  with hashes, so the audited set equals the installed set.
- **SBOM** — a CycloneDX Software Bill of Materials (`sbom.json`) is generated and
  uploaded as a build artifact.

## Cutting a release

1. **Bump versions** in the affected `pyproject.toml` files and update
   [`CHANGELOG.md`](CHANGELOG.md). Keep versions in lockstep within a release.
2. **Green main** — ensure `main` is green (tests, types, lint, audit) at the
   release commit.
3. **Refresh + audit the lockfile**:
   ```console
   uv lock
   uv sync
   uv run --with pip-audit pip-audit            # must report no known vulnerabilities
   uv run --with cyclonedx-bom cyclonedx-py environment -o sbom.json
   ```
4. **Build** the distributions (sdist + wheels) reproducibly:
   ```console
   uv build --all-packages           # writes dist/*.tar.gz and dist/*.whl
   ```
5. **Sign** every artifact and publish checksums + signatures:
   ```console
   # keyless signing via Sigstore (recommended; verifiable against the GitHub OIDC identity)
   python -m sigstore sign dist/*
   # ...or detached signatures with minisign / GPG if you maintain a key:
   #   minisign -Sm dist/<file>
   sha256sum dist/* > dist/SHA256SUMS
   ```
6. **Tag + publish**: create an annotated, signed git tag (`git tag -s vX.Y.Z`),
   push it, and attach `dist/*`, `dist/SHA256SUMS`, the `*.sigstore`/`*.sig`
   signatures, and `sbom.json` to the GitHub Release. Publish to PyPI with
   `uv publish` (using a scoped PyPI Trusted Publisher / OIDC, not a long-lived
   token, where possible).

## Verifying a release (for users)

```console
sha256sum -c SHA256SUMS                                   # integrity
python -m sigstore verify identity dist/<file> \         # provenance
  --cert-identity <release-workflow-identity> \
  --cert-oidc-issuer https://token.actions.githubusercontent.com
```

Inference results are independently verifiable too: every answer ships a signed
[receipt](docs/spec/), and provider manifests / attestations are signed — see
[`sip-receipt verify`](packages/receipt-verifier) and the [threat model](docs/threat-model.md).

## Reporting vulnerabilities

See [SECURITY.md](SECURITY.md). Do not open public issues for security reports.
