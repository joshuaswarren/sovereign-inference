# SPDX-License-Identifier: Apache-2.0
"""Allow ``python -m sip_receipts``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
