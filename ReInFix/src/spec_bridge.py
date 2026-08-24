"""Run spec pipeline for ReInFix.

Primary path (Step 2): ``spec_integration.spec_adapter.run_spec_for_dataset_bug``
with a dataset entry from ``D4J_dataset/defects4j-sf.json``.

This module remains for backward compatibility. When ``dataset_entry`` is omitted,
it tries to load the bug from the SF dataset first; only then falls back to the
legacy RepairAgent ``autogpt`` spec path.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import warnings
from typing import Any, Optional

from experiment_manager import patch_experiment_hooks
from paths import ensure_repairagent_on_path, reinfix_root, repairagent_root

logger = logging.getLogger(__name__)


def parse_bug_name(bug_name: str) -> tuple[str, str]:
    if " " in bug_name.strip() and "-" not in bug_name.split()[0]:
        parts = bug_name.split()
        bug_name = "{}-{}".format(parts[0], parts[1])
    project, bug_index = bug_name.replace(" ", "-").split("-", 1)
    return project, bug_index


def checkout_bug(project: str, bug_index: str) -> None:
    root = ensure_repairagent_on_path()
    checkout_script = root / "checkout_py.py"
    subprocess.run(
        [sys.executable, str(checkout_script), project, bug_index],
        check=True,
        cwd=str(root),
    )


def _load_dataset_entry(project: str, bug_index: str) -> dict[str, Any] | None:
    try:
        from spec_integration.spec_adapter import load_dataset_entry

        return load_dataset_entry("{}-{}".format(project, bug_index))
    except (KeyError, OSError, ImportError) as exc:
        logger.debug("Could not load dataset entry for %s-%s: %s", project, bug_index, exc)
        return None


def _run_legacy_repairagent_spec(
    project: str,
    bug_index: str,
    model: str,
    max_attempts: int,
    exp_dir: str,
) -> dict[str, Any]:
    warnings.warn(
        "Using legacy RepairAgent autogpt spec path. Prefer "
        "spec_integration.spec_adapter.run_spec_for_dataset_bug with a dataset entry.",
        DeprecationWarning,
        stacklevel=3,
    )
    patch_experiment_hooks(exp_dir)
    src_dir = str(reinfix_root() / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    root = repairagent_root()
    prev_cwd = os.getcwd()
    try:
        os.chdir(root)
        from autogpt.commands.defects4j_static import get_info, run_tests
        from autogpt.commands.spec_generator import generate_spec

        checkout_bug(project, bug_index)
        workspace = "auto_gpt_workspace"
        localization_info = get_info(project, int(bug_index), workspace)
        test_results = run_tests(
            project, int(bug_index), workspace, restore_after=False
        )
        return generate_spec(
            project_name=project,
            bug_index=bug_index,
            localization_info=localization_info,
            test_results=test_results,
            model=model,
            workspace=workspace,
            max_attempts=max_attempts,
        )
    finally:
        os.chdir(prev_cwd)


def run_spec_pipeline(
    project: str,
    bug_index: str,
    model: str,
    max_attempts: int,
    exp_dir: str,
    dataset_entry: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Run generate_spec + verify using the Step 2 adapter when possible."""
    entry = dataset_entry or _load_dataset_entry(project, bug_index)
    if entry is not None:
        from spec_integration.spec_adapter import run_spec_for_dataset_bug

        return run_spec_for_dataset_bug(
            "{}-{}".format(project, bug_index),
            entry,
            model=model,
            max_attempts=max_attempts,
            exp_dir=exp_dir,
        )

    return _run_legacy_repairagent_spec(project, bug_index, model, max_attempts, exp_dir)
