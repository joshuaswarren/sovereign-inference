# Sovereign Inference — desktop app (Tauri) — scaffold

A cross-platform desktop app (macOS / Linux / Windows) that bundles:

- the **React dashboard** ([`apps/dashboard`](../dashboard)) as its UI, and
- the Python **node + OpenAI proxy** as a **sidecar** binary,

so a non-technical user can install one app, click *Start*, and have a local
`http://localhost:11435/v1` endpoint plus a dashboard — no terminal required.

> **Status: scaffold.** The configuration and Rust shell here are real and follow
> the standard Tauri v2 layout, but a signed installer must be **built on a machine
> with the toolchain** (Rust, the Tauri CLI, and Node) and a display — it cannot be
> produced in this headless repo. Treat `src-tauri/src/main.rs` as the starting
> point, not a finished binary.

## Build it locally

```console
# 1. prerequisites: Rust (https://rustup.rs), Node 20+, and the Tauri CLI
cargo install tauri-cli --version "^2"

# 2. build the dashboard UI the app embeds
cd apps/dashboard && pnpm install && pnpm build      # -> apps/dashboard/dist

# 3. freeze the Python proxy into a self-contained sidecar binary
#    (one option; pin to your platform triple, e.g. aarch64-apple-darwin)
uvx pyinstaller --onefile --name sip-openai-proxy \
  -p packages -p apps/openai-proxy/src \
  apps/openai-proxy/src/sip_openai_proxy/__main__.py
#    copy/rename to apps/desktop/src-tauri/binaries/sip-openai-proxy-<target-triple>

# 4. build the app
cd apps/desktop/src-tauri && cargo tauri build
```

## How it works

- `tauri.conf.json` points `frontendDist` at the dashboard build and declares the
  proxy as an `externalBin` sidecar.
- `src/main.rs` spawns the sidecar on startup (via the shell plugin) and opens the
  dashboard window; the dashboard talks to the local proxy/status API.
- The sidecar is the same `sip-openai-proxy` you can run from the CLI — the desktop
  app just packages it for one-click use.

**License:** AGPL-3.0-or-later — see [LICENSING.md](../../LICENSING.md).

Design refs: [ROADMAP](../../ROADMAP.md) (Phase 6 desktop app), [Architecture](../../docs/architecture.md).
