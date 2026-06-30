# SPDX-License-Identifier: AGPL-3.0-or-later
"""PyInstaller entry point for the bundled desktop sidecar.

Runs the unified app server (OpenAI proxy + node status + onboarding admin).
Uses an absolute import (unlike ``sip_openai_proxy.__main__``) so it works when
PyInstaller runs it as a standalone script rather than a package submodule.
"""

import sys

from sip_openai_proxy.server import run

if __name__ == "__main__":
    sys.exit(run())
