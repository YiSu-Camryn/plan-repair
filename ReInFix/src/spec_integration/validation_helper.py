"""Defects4J validation wrapper for ReInFix single-function patches."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from spec_integration.paths import dataset_sf_path, reinfix_root


def validate_sf_patches(patch_file: Path, bug_name: str) -> tuple[bool, Path | None]:
    """Run sf_val_d4j on one patch JSON; return (has_plausible, plausible_file_path)."""
    val_cwd = reinfix_root() / "src" / "validation" / "D4J"
    val_script = val_cwd / "sf_val_d4j.py"
    if not val_script.is_file() or not patch_file.is_file():
        return False, None

    out_dir = reinfix_root() / "output" / "validation_tmp" / bug_name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    dataset = dataset_sf_path()
    cmd = [
        sys.executable,
        str(val_script),
        "-i",
        str(patch_file.resolve()),
        "-o",
        str(out_dir.resolve()),
        "-d",
        str(dataset.resolve()),
    ]
    subprocess.run(cmd, cwd=str(val_cwd), check=False)

    plausible_dir = val_cwd / "sf-plausible"
    plausible_file = plausible_dir / "{}-plausible.json".format(bug_name)
    if plausible_file.is_file():
        try:
            data = json.loads(plausible_file.read_text(encoding="utf-8"))
            if data:
                return True, plausible_file
        except json.JSONDecodeError:
            pass
    return False, None


def copy_plausible_to_experiment(plausible_file: Path, project: str, bug_index: str) -> str | None:
    exp_dir = _current_experiment_dir()
    if not exp_dir or not plausible_file.is_file():
        return None
    dest_dir = os.path.join(exp_dir, "plausible_patches")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "plausible_patches_{}_{}.json".format(project, bug_index))
    shutil.copy2(plausible_file, dest)
    return dest


def _current_experiment_dir() -> str | None:
    list_path = reinfix_root() / "experimental_setups" / "experiments_list.txt"
    try:
        exps = list_path.read_text(encoding="utf-8").splitlines()
        if exps:
            return str(reinfix_root() / "experimental_setups" / exps[-1])
    except OSError:
        pass
    return None
