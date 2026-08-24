"""Resolve ReInFix and RepairAgent roots for spec bridge imports."""

from __future__ import annotations

import os
from pathlib import Path

_REINFIX_ROOT = Path(__file__).resolve().parents[1]
def _resolve_repairagent_root() -> Path:
    for key in ("REPAIRAGENT_SRC", "REPAIRAGENT_ROOT"):
        val = os.environ.get(key, "").strip()
        if val:
            return Path(val).resolve()
    return (_REINFIX_ROOT.parent / "repair_agent").resolve()


_REPAIRAGENT_ROOT = _resolve_repairagent_root()


def reinfix_root() -> Path:
    return _REINFIX_ROOT


def repairagent_root() -> Path:
    return _REPAIRAGENT_ROOT


def ensure_repairagent_on_path() -> Path:
    root = repairagent_root()
    root_str = str(root)
    if root_str not in os.sys.path:
        os.sys.path.insert(0, root_str)
    if not root.is_dir():
        raise FileNotFoundError(
            "RepairAgent root not found: {} (set REPAIRAGENT_ROOT)".format(root)
        )
    return root
