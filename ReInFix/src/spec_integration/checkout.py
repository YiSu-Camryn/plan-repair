"""Checkout strategy for baseline vs spec-enabled ReInFix runs."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from spec_integration.bootstrap import setup_environment
from spec_integration.paths import reinfix_root, repairagent_src
from spec_integration.pipeline_mode import PipelineMode, is_spec_enabled
from spec_integration.spec_adapter import (
    checkout_for_spec,
    has_spec_checkout,
    joern_checkout_link,
    joern_project_name,
    link_joern_checkout,
    spec_checkout_dir,
    spec_workspace_dir,
)

logger = logging.getLogger(__name__)


def joern_project_id(project_name: str, bug_index: str) -> str:
    """Joern ``open_proj`` id (same for baseline and spec modes)."""
    return joern_project_name(project_name, bug_index)


def baseline_checkout_dir(project_name: str, bug_index: str) -> Path:
    """Original ReInFix checkout: ``defects4j/Chart-1_buggy``."""
    return reinfix_root() / "defects4j" / joern_project_id(project_name, bug_index)


def checkout_path_for_mode(
    mode: PipelineMode,
    project_name: str,
    bug_index: str,
) -> Path:
    """Return expected checkout directory for ``mode`` (may not exist yet)."""
    if is_spec_enabled(mode):
        return spec_checkout_dir(project_name, bug_index)
    return baseline_checkout_dir(project_name, bug_index)


def has_baseline_checkout(project_name: str, bug_index: str) -> bool:
    path = baseline_checkout_dir(project_name, bug_index)
    if not path.exists() or path.is_symlink():
        return False
    return (path / ".defects4j.config").is_file()


def _paths_same_tree(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def _ensure_defects4j_path() -> None:
    root = reinfix_root()
    candidates = [
        root / "defects4j" / "framework" / "bin",
        repairagent_src() / "defects4j" / "framework" / "bin",
    ]
    path_env = os.environ.get("PATH", "")
    for framework_bin in candidates:
        if not framework_bin.is_dir():
            continue
        bin_str = str(framework_bin)
        if bin_str not in path_env:
            os.environ["PATH"] = bin_str + os.pathsep + path_env
            path_env = os.environ["PATH"]


def _remove_checkout_target(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def checkout_baseline(
    project_name: str,
    bug_index: str,
    *,
    force: bool = False,
) -> Path:
    """Checkout buggy project directly under ``ReInFix/defects4j/`` (real dir)."""
    _ensure_defects4j_path()
    checkout_dir = baseline_checkout_dir(project_name, bug_index)
    config_file = checkout_dir / ".defects4j.config"

    if checkout_dir.is_symlink():
        logger.info(
            "Removing Joern symlink at %s before baseline checkout", checkout_dir
        )
        checkout_dir.unlink()
    elif force and checkout_dir.exists():
        _remove_checkout_target(checkout_dir)
    elif config_file.is_file() and checkout_dir.is_dir():
        return checkout_dir

    checkout_dir.parent.mkdir(parents=True, exist_ok=True)
    cmd = "defects4j checkout -p {} -v {}b -w {}".format(
        project_name, bug_index, checkout_dir
    )
    subprocess.run(cmd, shell=True, check=True, cwd=str(reinfix_root()))
    if not config_file.is_file():
        raise RuntimeError("Baseline checkout failed: missing {}".format(config_file))
    return checkout_dir


def ensure_bug_checkout(
    mode: PipelineMode,
    project_name: str,
    bug_index: str,
    *,
    force: bool = False,
) -> tuple[Path, str]:
    """Ensure checkout exists; return ``(checkout_path, joern_project_id)``."""
    joern_id = joern_project_id(project_name, bug_index)
    if is_spec_enabled(mode):
        setup_environment()
        spec_dir = spec_checkout_dir(project_name, bug_index)
        if force or not has_spec_checkout(project_name, bug_index):
            checkout_for_spec(
                project_name,
                bug_index,
                workspace=spec_workspace_dir(),
                link_joern=True,
            )
        else:
            link_path = joern_checkout_link(project_name, bug_index)
            if not link_path.exists() or not _paths_same_tree(link_path, spec_dir):
                link_joern_checkout(project_name, bug_index)
        return spec_checkout_dir(project_name, bug_index), joern_id

    checkout_path = checkout_baseline(project_name, bug_index, force=force)
    return checkout_path, joern_id


def describe_checkout_layout(
    mode: PipelineMode,
    project_name: str,
    bug_index: str,
) -> dict[str, Any]:
    """Return expected vs actual checkout paths for diagnostics."""
    joern_id = joern_project_id(project_name, bug_index)
    joern_path = joern_checkout_link(project_name, bug_index)
    expected = checkout_path_for_mode(mode, project_name, bug_index)
    layout = {
        "mode": mode,
        "joern_project_id": joern_id,
        "expected_checkout": str(expected),
        "joern_link_path": str(joern_path),
        "joern_link_exists": joern_path.exists() or joern_path.is_symlink(),
        "expected_is_spec_workspace": is_spec_enabled(mode),
    }
    if expected.is_dir() and (expected / ".defects4j.config").is_file():
        layout["checkout_ready"] = True
        layout["checkout_is_symlink"] = expected.is_symlink()
    else:
        layout["checkout_ready"] = False
        layout["checkout_is_symlink"] = expected.is_symlink() if expected.exists() else False

    if layout["joern_link_exists"]:
        try:
            layout["joern_resolves_to"] = str(joern_path.resolve())
        except OSError as exc:
            layout["joern_resolves_to"] = "broken: {}".format(exc)
    else:
        layout["joern_resolves_to"] = None

    if is_spec_enabled(mode):
        layout["spec_checkout_ready"] = has_spec_checkout(project_name, bug_index)
        if layout["joern_link_exists"] and has_spec_checkout(project_name, bug_index):
            layout["joern_link_aligned"] = _paths_same_tree(joern_path, expected)
        else:
            layout["joern_link_aligned"] = None
    else:
        layout["baseline_checkout_ready"] = has_baseline_checkout(project_name, bug_index)
        layout["joern_link_aligned"] = (
            layout["baseline_checkout_ready"]
            and layout["joern_link_exists"]
            and not joern_path.is_symlink()
            and _paths_same_tree(joern_path, expected)
        )

    return layout


def verify_checkout_layout(
    mode: PipelineMode,
    project_name: str,
    bug_index: str,
) -> list[str]:
    """Return human-readable layout errors; empty list if paths look consistent."""
    info = describe_checkout_layout(mode, project_name, bug_index)
    errors: list[str] = []

    if is_spec_enabled(mode):
        if info.get("joern_link_exists") and info.get("joern_link_aligned") is False:
            errors.append(
                "Spec mode: Joern link {} should point to spec checkout {}".format(
                    info["joern_link_path"], info["expected_checkout"]
                )
            )
        if info.get("checkout_ready") and info.get("checkout_is_symlink"):
            errors.append(
                "Spec mode: spec checkout should be a real directory under auto_gpt_workspace, "
                "not a symlink ({})".format(info["expected_checkout"])
            )
    else:
        if info.get("joern_link_exists") and joern_checkout_link(project_name, bug_index).is_symlink():
            errors.append(
                "Baseline mode: {} should be a real checkout directory, not a symlink "
                "(leftover from spec mode?)".format(info["joern_link_path"])
            )
        if info.get("checkout_ready") and info.get("checkout_is_symlink"):
            errors.append(
                "Baseline mode: checkout must not be a symlink ({})".format(
                    info["expected_checkout"]
                )
            )

    return errors
