# Sovereign Inference — desktop app (Tauri)

A cross-platform desktop app (macOS / Linux / Windows) that bundles:

- the **React dashboard** ([`apps/dashboard`](../dashboard)) as its UI, and
- the Python **OpenAI proxy** as a **sidecar** binary,

so a non-technical user installs one app, and it starts a local
`http://localhost:11435/v1` OpenAI-compatible endpoint — no terminal required.

> **Built and verified on macOS (Apple Silicon).** `cargo tauri build` produces a
> signed-able `Sovereign Inference.app` + a `.dmg`; on launch the app spawns the
> bundled proxy sidecar and serves `/v1/models` + `/healthz` on port 11435 (verified).
> Linux (`.AppImage`/`.deb`) and Windows (`.msi`/`.exe`) are built the same way **on
> those platforms** (Tauri does not cross-compile the OS webview). Built binaries and
> `target/` are git-ignored — build them locally per platform.

## Build it

```console
# prerequisites: Rust (https://rustup.rs), Node 20+, and the Tauri CLI v2
cargo install tauri-cli --version "^2" --locked

# 1. freeze the Python proxy into a self-contained sidecar for your platform triple
#    (macOS arm64 shown; use your `rustc -vV | grep host` triple)
uv run --with pyinstaller pyinstaller --noconfirm --onefile --name sip-openai-proxy \
  --collect-all uvicorn --collect-all fastapi --collect-all pydantic --collect-all sip_openai_proxy \
  --collect-submodules sip_router --collect-submodules sip_discovery --collect-submodules sip_policy \
  --collect-submodules sip_protocol --collect-submodules sip_gateway --collect-submodules sip_pic \
  --collect-submodules sip_compute --collect-submodules sip_arweave \
  apps/desktop/sidecar_entry.py
cp dist/sip-openai-proxy "apps/desktop/src-tauri/binaries/sip-openai-proxy-$(rustc -vV | sed -n 's/host: //p')"

# 2. build the app (this also builds the dashboard via beforeBuildCommand)
cd apps/desktop/src-tauri && cargo tauri build
# -> target/release/bundle/macos/Sovereign Inference.app  and  .../dmg/*.dmg
```

To regenerate the icon set from a 1024px source: `cargo tauri icon ../icon-source.png`.

## How it works

- `tauri.conf.json` points `frontendDist` at the dashboard build and declares the
  proxy as a `bundle.externalBin` sidecar.
- `capabilities/default.json` grants the app permission to run that sidecar — in
  Tauri v2 sidecar permissions live in **capabilities**, *not* in `plugins.shell`.
- `src/main.rs` spawns the sidecar on startup (forwarding its logs as `[proxy] …`)
  and opens the dashboard window; the dashboard / any local OpenAI client talks to
  the proxy at `http://localhost:11435/v1`.
- `sidecar_entry.py` is the PyInstaller entry (an absolute-import launcher, so the
  frozen binary runs standalone).

## Signing & distribution

For a distributable build, sign and notarize per platform (see [RELEASING.md](../../RELEASING.md)):
macOS Developer ID + notarization, Windows Authenticode, Linux detached signatures.
The local build is ad-hoc-signed (fine for development).

**License:** AGPL-3.0-or-later — see [LICENSING.md](../../LICENSING.md).

Design refs: [ROADMAP](../../ROADMAP.md) (Phase 6 desktop app), [Architecture](../../docs/architecture.md).
