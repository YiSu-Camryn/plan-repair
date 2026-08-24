#!/usr/bin/env python3
"""Verify ReInFix Step 2 spec adapter environment (no LLM).

Usage:
  python scripts/verify_spec_environment.py [BUG_ID]

Example:
  python scripts/verify_spec_environment.py Chart-1
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from spec_integration.verify import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
