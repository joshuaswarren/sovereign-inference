# SPDX-License-Identifier: AGPL-3.0-or-later
"""``python -m sip_openai_proxy`` entry point (also used to freeze the sidecar)."""

from __future__ import annotations

from .app import run

if __name__ == "__main__":
    raise SystemExit(run())
