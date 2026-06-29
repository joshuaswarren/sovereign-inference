# Dashboard

The local web dashboard for a Sovereign Inference Node: hardware overview,
model recommendations, status, and (stubbed for Phase 2/3) capacity sharing and
receipts.

**Status:** Phase 1 implemented — React + Vite (TypeScript). Fetches from the
[`sin-node` status API](../../packages/sin-node) (`/api/scan`, `/api/recommend`,
`/api/status`). A Tauri desktop shell that bundles the Python node as a sidecar
is planned for Phase 6.

**License:** AGPL-3.0-or-later — see [LICENSING.md](../../LICENSING.md).

```console
pnpm --filter @sovereign-inference/dashboard dev        # dev server (proxies /api -> :8009)
pnpm --filter @sovereign-inference/dashboard build      # production build
```

Run the API it talks to with `python -c "from sin_node.api import serve; serve()"`
(or the forthcoming `sin dashboard` command).
