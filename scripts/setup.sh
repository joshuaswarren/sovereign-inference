#!/usr/bin/env bash
# Bootstrap a Sovereign Inference development environment.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Checking prerequisites"
command -v uv >/dev/null 2>&1 || { echo "ERROR: uv not found — install from https://docs.astral.sh/uv"; exit 1; }
command -v python3.12 >/dev/null 2>&1 || echo "WARN: python3.12 not on PATH; uv will fetch a managed 3.12 if needed"

echo "==> Syncing Python workspace (uv)"
uv sync

if command -v pnpm >/dev/null 2>&1; then
  echo "==> Installing JS workspace (pnpm)"
  pnpm install
else
  echo "WARN: pnpm not found — skipping JS workspace. Install from https://pnpm.io"
fi

echo "==> Verifying the working slice (sign + verify a receipt)"
uv run sip-receipt demo > /tmp/sip-setup-receipt.json
uv run sip-receipt verify /tmp/sip-setup-receipt.json

cat <<'EOF'

Setup complete.

Next steps:
  make check          # run lint + types + tests
  make demo           # sign & verify a sample receipt
  uv run sip-receipt --help

Docs: docs/README.md   Roadmap: ROADMAP.md
EOF
