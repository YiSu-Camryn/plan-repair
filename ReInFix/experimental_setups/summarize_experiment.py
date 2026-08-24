#!/usr/bin/env python3
"""Summarize ReInFix experiment (delegates to repair_agent summarize_experiment)."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_REINFIX = Path(__file__).resolve().parents[1]
_REPAIR = _REINFIX.parent / "repair_agent"
_SCRIPT = _REPAIR / "experimental_setups" / "summarize_experiment.py"

if not _SCRIPT.is_file():
    raise SystemExit("RepairAgent summarize script not found: {}".format(_SCRIPT))

sys.path.insert(0, str(_REPAIR))
runpy.run_path(str(_SCRIPT), run_name="__main__")
