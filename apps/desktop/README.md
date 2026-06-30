# Sovereign Inference — desktop app (Tauri)

A cross-platform desktop app (macOS / Linux / Windows) that bundles:

- the **React dashboard** ([`apps/dashboard`](../dashboard)) as its UI, and
- a unified **app server** as a **sidecar** binary — the OpenAI-compatible proxy,
  the node-status API, the dashboard, and the onboarding/admin API on one
  loopback origin (`sip-app-server`, from [`apps/openai-proxy`](../openai-proxy)).

Install one app, and on first run a **wizard** walks you through choosing where
inference comes from — a model already running on your computer (Ollama /
llama.cpp), and/or remote SIP providers — then any OpenAI-compatible client can
point at `http://localhost:11435/v1`. Even a locally-fronted model returns a
signed, verified receipt.

> **Built and verified on macOS (Apple Silicon).** `cargo tauri build` produces a
> `Sovereign Inference.app` + a `.dmg`; on launch the app starts the bundled app
> server, runs onboarding, and serves `/v1`, `/api/*`, and the dashboard on port
> 11435 — verified with real local inference. Linux (`.AppImage`/`.deb`) and
> Windows (`.msi`/`.exe`) build the same way **on those platforms** (Tauri does not
> cross-compile the OS webview). Built binaries and `target/` are git-ignored —
> build them locally per platform.

## Build it

```console
# prerequisites: Rust (https://rustup.rs), Node 20+, pnpm, and the Tauri CLI v2
cargo install tauri-cli --version "^2" --locked

# 1. build the dashboard (also done by beforeBuildCommand, but the freeze needs it)
pnpm --dir ../dashboard install && pnpm --dir ../dashboard build

# 2. freeze the app server into a self-contained sidecar via its spec, which bundles
#    the data the frozen app needs (catalog, schemas, the dashboard, adapter metadata)
uv run --with pyinstaller pyinstaller apps/desktop/sip-app-server.spec \
  --distpath apps/desktop/build/dist --workpath apps/desktop/build/work --noconfirm
cp apps/desktop/build/dist/sip-app-server \
  "apps/desktop/src-tauri/binaries/sip-app-server-$(rustc -vV | sed -n 's/host: //p')"

# 3. build the app
cd apps/desktop/src-tauri && cargo tauri build
# -> target/release/bundle/macos/Sovereign Inference.app  and  .../dmg/*.dmg
```

To regenerate the icon set from a 1024px source: `cargo tauri icon ../icon-source.png`.

## How it works

- `src/main.rs` (the shell) generates a per-install **admin token**, starts the
  `sip-app-server` sidecar with `--config-dir <OS app-data dir>`, `--admin-token`,
  and `--parent-pid`, **injects** `window.__SOVEREIGN__ = { apiBase, token }` into
  the webview, and reveals the window once the server is healthy. It kills the
  sidecar on exit — and the sidecar **also** self-exits via a parent-death
  watchdog, so it never orphans even if the app is force-killed.
- `tauri.conf.json` declares the sidecar as a `bundle.externalBin`; the SPA loads
  from `frontendDist` (the bundled dashboard) and talks to the app server on
  loopback (allowed by the CSP and the server's CORS).
- `capabilities/default.json` grants permission to run that sidecar — in Tauri v2
  sidecar permissions live in **capabilities**, not in `plugins.shell`.
- `sip-app-server.spec` is the PyInstaller spec; `sidecar_entry.py` is its
  absolute-import entry, so the frozen binary runs standalone.
- The dashboard's `App.tsx` asks the server for its config first and shows the
  **onboarding wizard** until setup is complete; mutating `/api` calls carry the
  injected admin token.

## Signing & distribution

For a distributable build, sign and notarize per platform (see [RELEASING.md](../../RELEASING.md)):
macOS Developer ID + notarization, Windows Authenticode, Linux detached signatures.
The local build is ad-hoc-signed (fine for development).

**License:** AGPL-3.0-or-later — see [LICENSING.md](../../LICENSING.md).

Design refs: [ROADMAP](../../ROADMAP.md) (Phase 6 desktop app), [Architecture](../../docs/architecture.md).
