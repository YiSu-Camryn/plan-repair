"""Path helpers for ReInFix runs (root, output, datasets)."""

from __future__ import annotations

import os
from pathlib import Path


def reinfix_root() -> Path:
    return Path(__file__).resolve().parents[2]


def repairagent_src() -> Path:
    for key in ("REPAIRAGENT_SRC", "REPAIRAGENT_ROOT"):
        env = os.environ.get(key, "").strip()
        if env:
            return Path(env)
    return reinfix_root().parent / "repair_agent"


def output_dir(*parts: str) -> Path:
    path = reinfix_root() / "output"
    for part in parts:
        path = path / part
    return path


def dataset_sf_path() -> Path:
    return reinfix_root() / "D4J_dataset" / "defects4j-sf.json"


def dataset_mf_path() -> Path:
    return reinfix_root() / "D4J_dataset" / "defects4j-mf.json"


def hyperparams_path() -> Path:
    return reinfix_root() / "hyperparams.json"


def experiments_base() -> Path:
    return reinfix_root() / "experimental_setups"
