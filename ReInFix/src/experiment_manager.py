"""Experiment directory helpers (mirrors repair_agent experimental_setups layout)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from paths import reinfix_root


def _list_path() -> Path:
    return reinfix_root() / "experimental_setups" / "experiments_list.txt"


def increment_experiment() -> str:
    script = reinfix_root() / "experimental_setups" / "increment_experiment.py"
    subprocess.run([sys.executable, str(script)], check=True, cwd=str(reinfix_root()))
    return current_experiment_name()


def current_experiment_name() -> str:
    with open(_list_path(), encoding="utf-8") as handle:
        lines = [ln.strip() for ln in handle.read().splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("experiments_list.txt is empty")
    return lines[-1]


def current_experiment_dir() -> str:
    return str(reinfix_root() / "experimental_setups" / current_experiment_name())


def experiment_subdir(*parts: str) -> str:
    path = Path(current_experiment_dir()).joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def patch_experiment_hooks(exp_dir: Optional[str] = None) -> str:
    """Point ReInFix-local spec + RepairAgent results modules at the active experiment dir."""
    exp = exp_dir or current_experiment_dir()
    spec_logs = os.path.join(exp, "spec_logs")
    os.makedirs(spec_logs, exist_ok=True)

    def _get_spec_log_dir():
        os.makedirs(spec_logs, exist_ok=True)
        return spec_logs

    def _current_experiment_dir():
        return exp

    import spec.spec_generator as local_spec_generator
    import spec.spec_failure_recorder as local_spec_failure_recorder

    local_spec_generator._get_spec_log_dir = _get_spec_log_dir  # type: ignore[attr-defined]
    local_spec_failure_recorder._current_experiment_dir = _current_experiment_dir  # type: ignore[attr-defined]

    try:
        from paths import ensure_repairagent_on_path

        ensure_repairagent_on_path()
        import autogpt.bug_results_recorder as bug_results_recorder
        import autogpt.commands.spec_generator as ra_spec_generator

        ra_spec_generator._get_spec_log_dir = _get_spec_log_dir  # type: ignore[attr-defined]
        bug_results_recorder._current_experiment_dir = _current_experiment_dir  # type: ignore[attr-defined]
    except ImportError:
        pass

    return exp


def patch_repairagent_experiment_hooks(exp_dir: Optional[str] = None) -> str:
    """Alias for patch_experiment_hooks (backward compatible)."""
    return patch_experiment_hooks(exp_dir)
