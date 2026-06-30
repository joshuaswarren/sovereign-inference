# SPDX-License-Identifier: AGPL-3.0-or-later
# PyInstaller spec for the Sovereign Inference desktop sidecar (the unified app server).
#
# The critical job here is bundling DATA, not just code: the model catalog, the
# JSON Schemas (loaded via importlib.resources), the runtime-adapter entry-point
# metadata, and the built dashboard. A code-only freeze passes every dev test and
# then 404s / crashes in the packaged app — so collect_all + copy_metadata below
# are load-bearing. Build:  pyinstaller apps/desktop/sip-app-server.spec
import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = []
binaries = []
hiddenimports = [
    # dynamically reached at runtime; the analyzer can miss these
    "sin_node.api",
    "sin_node.hardware",
    "sin_node.recommend",
    "sin_node.adapter",
    "sin_node.catalog",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]

# Collect code + DATA FILES + dynamic submodules for every package the server
# imports — including catalog JSON (sin_node), schemas (sip_protocol), and the
# native psutil backend.
for pkg in (
    "sip_openai_proxy",
    "sip_router",
    "sip_discovery",
    "sip_policy",
    "sip_protocol",
    "sip_gateway",
    "sip_pic",
    "sip_arweave",
    "sip_compute",
    "sin_node",
    "sip_runtime_ollama",
    "sip_runtime_llamacpp",
    "psutil",
):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

# Entry-point metadata so importlib.metadata.entry_points(group=...) still finds
# plugins/adapters inside the frozen app.
for dist in ("sip-runtime-ollama", "sip-runtime-llamacpp", "sip-openai-proxy"):
    try:
        datas += copy_metadata(dist)
    except Exception:  # noqa: BLE001 - a missing dist is simply not bundled
        pass

# The built dashboard, mounted at "/" by the app server. Resolved at runtime via
# sys._MEIPASS/dashboard (see server._resolve_dashboard_dir).
_dashboard_dist = os.path.join(SPECPATH, "..", "dashboard", "dist")  # noqa: F821 - SPECPATH is a PyInstaller global
if os.path.isdir(_dashboard_dist):
    datas += [(_dashboard_dist, "dashboard")]

a = Analysis(
    [os.path.join(SPECPATH, "sidecar_entry.py")],  # noqa: F821
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="sip-app-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
