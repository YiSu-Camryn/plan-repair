"""Run behavioral spec (generate + verify) for a ReInFix D4J dataset entry."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal, Optional

from spec_integration.bootstrap import link_directory, setup_environment
from spec_integration.paths import (
    dataset_mf_path,
    dataset_sf_path,
    hyperparams_path,
    reinfix_root,
)

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE = "auto_gpt_workspace"


def normalize_bug_name(bug_name: str) -> str:
    """Accept ``Chart-1`` or ``Chart 1`` (batch file style)."""
    name = bug_name.strip()
    if " " in name:
        parts = name.split()
        if len(parts) >= 2 and "-" not in parts[0]:
            return "{}-{}".format(parts[0], parts[1])
    return name.replace(" ", "-")


def parse_bug_id(bug_name: str) -> tuple[str, str]:
    project, index = normalize_bug_name(bug_name).split("-", 1)
    return project, index


def load_dataset(
    path: Optional[str | Path] = None,
    variant: Literal["sf", "mf"] = "sf",
) -> dict[str, Any]:
    if path:
        ds_path = Path(path)
    elif variant == "mf":
        ds_path = dataset_mf_path()
    else:
        ds_path = dataset_sf_path()
    with open(ds_path, encoding="utf-8") as handle:
        return json.load(handle)


def load_dataset_entry(
    bug_name: str,
    path: Optional[str | Path] = None,
    variant: Literal["sf", "mf"] = "sf",
) -> dict[str, Any]:
    data = load_dataset(path=path, variant=variant)
    key = normalize_bug_name(bug_name)
    if key not in data:
        raise KeyError("Bug {} not in dataset ({})".format(key, path or variant))
    return data[key]


def build_test_results(dataset_entry: dict[str, Any]) -> str:
    parts: list[str] = []
    for test_info in (dataset_entry.get("trigger_test") or {}).values():
        msg = test_info.get("clean_error_msg") or test_info.get("error_msg") or ""
        if msg.strip():
            parts.append(msg.strip())
    return "\n\n".join(parts)


def spec_workspace_dir(workspace: str = DEFAULT_WORKSPACE) -> Path:
    return reinfix_root() / workspace


def spec_checkout_dir(
    project_name: str,
    bug_index: str,
    workspace: str = DEFAULT_WORKSPACE,
) -> Path:
    """RepairAgent-style checkout path used by ``generate_spec``."""
    return spec_workspace_dir(workspace) / "{}_{}_buggy".format(
        project_name.lower(), bug_index
    )


def joern_project_name(project_name: str, bug_index: str) -> str:
    """Project id passed to Joern ``open_proj`` (e.g. ``Chart-1_buggy``)."""
    return "{}-{}_buggy".format(project_name, bug_index)


def joern_checkout_link(project_name: str, bug_index: str) -> Path:
    """Path under ``ReInFix/defects4j/`` that Joern tools open."""
    return reinfix_root() / "defects4j" / joern_project_name(project_name, bug_index)


def link_joern_checkout(
    project_name: str,
    bug_index: str,
    workspace: str = DEFAULT_WORKSPACE,
) -> Path:
    """Point ``defects4j/Project-N_buggy`` at the spec checkout tree."""
    spec_dir = spec_checkout_dir(project_name, bug_index, workspace)
    if not (spec_dir / ".defects4j.config").is_file():
        raise RuntimeError(
            "Spec checkout missing before Joern link: {}".format(spec_dir)
        )
    link_path = joern_checkout_link(project_name, bug_index)
    link_directory(spec_dir.resolve(), link_path)
    return link_path


def _format_failing_tests(content: str) -> str:
    """Format ``failing_tests`` file (RepairAgent ``extract_fail_report`` parity)."""
    lines = content.splitlines()
    failing_cases: list[list[str]] = []
    current_case: list[str] = []
    case_base = ""

    for line in lines:
        if line.startswith("---"):
            if current_case:
                failing_cases.append(current_case)
                current_case = []
                case_base = ""
            current_case.append(line)
            if "::" in line:
                case_base = line[4 : line.find("::")]
                case_base = ".".join(case_base.split(".")[:-1])
        elif line.startswith("\tat "):
            if case_base and case_base in line:
                current_case.append(line)
        else:
            current_case.append(line)

    if current_case:
        failing_cases.append(current_case)

    if not failing_cases:
        return content.strip()

    return (
        "There are {} failing test cases, here is the full log of failing cases:\n".format(
            len(failing_cases)
        )
        + "\n\n".join("\n".join(case) for case in failing_cases)
    )


def should_restore_after_tests(restore_after: bool | None = None) -> bool:
    if restore_after is not None:
        return restore_after
    flag = os.environ.get("REINFIX_SPEC_RESTORE_AFTER_TEST", "0").strip().lower()
    return flag in ("1", "true", "yes", "on")


def run_tests_for_spec(
    project_name: str,
    bug_index: str,
    workspace: str = DEFAULT_WORKSPACE,
    restore_after: bool | None = None,
) -> str:
    """Run ``defects4j compile && test`` in the spec checkout directory."""
    setup_environment()
    checkout_dir = spec_checkout_dir(project_name, bug_index, workspace)
    if not checkout_dir.is_dir():
        raise RuntimeError("Checkout directory missing: {}".format(checkout_dir))

    try:
        result = subprocess.run(
            "defects4j compile && defects4j test",
            shell=True,
            cwd=str(checkout_dir),
            capture_output=True,
            text=True,
        )
        failing_path = checkout_dir / "failing_tests"
        if failing_path.is_file():
            return _format_failing_tests(failing_path.read_text(encoding="utf-8"))

        combined = (result.stdout or "") + (result.stderr or "")
        if "BUILD FAILED" in combined:
            return combined[combined.find("BUILD FAILED") :].strip()
        return combined.strip()
    finally:
        if should_restore_after_tests(restore_after):
            logger.info(
                "Restoring spec checkout after test for %s-%s",
                project_name,
                bug_index,
            )
            checkout_for_spec(
                project_name,
                bug_index,
                workspace=spec_workspace_dir(workspace),
                link_joern=True,
            )


def should_run_live_tests(run_tests: bool | None = None) -> bool:
    if run_tests is not None:
        return run_tests
    flag = os.environ.get("REINFIX_SPEC_RUN_TESTS", "1").strip().lower()
    return flag not in ("0", "false", "no", "off")


def resolve_test_results(
    dataset_entry: dict[str, Any],
    project_name: str,
    bug_index: str,
    workspace: str = DEFAULT_WORKSPACE,
    run_tests: bool | None = None,
) -> str:
    """Prefer live ``defects4j test`` output; fall back to dataset error messages."""
    if should_run_live_tests(run_tests):
        try:
            live = run_tests_for_spec(project_name, bug_index, workspace)
            if live.strip():
                return live
        except Exception as exc:
            logger.warning(
                "Live defects4j test failed for %s-%s: %s; using dataset errors",
                project_name,
                bug_index,
                exc,
            )
    return build_test_results(dataset_entry)


def build_localization_info(dataset_entry: dict[str, Any]) -> str:
    loc = dataset_entry.get("loc") or ""
    sig = dataset_entry.get("method_signature") or {}
    method = sig.get("method_name") or ""
    ret = sig.get("return_type") or ""
    params = sig.get("params_string") or ""
    lines = [
        "Buggy file: {}".format(loc),
        "Method: {} {}({})".format(ret, method, params).strip(),
    ]
    if dataset_entry.get("start") and dataset_entry.get("end"):
        lines.append(
            "Buggy line range: {}-{}".format(dataset_entry["start"], dataset_entry["end"])
        )
    if dataset_entry.get("issue_title"):
        lines.append("Issue: {}".format(dataset_entry["issue_title"]))
    if dataset_entry.get("issue_description"):
        desc = str(dataset_entry["issue_description"]).strip()
        if desc:
            lines.append("Description: {}".format(desc[:2000]))
    buggy_fl = dataset_entry.get("buggy_fl") or dataset_entry.get("buggy") or ""
    if buggy_fl:
        lines.append("Buggy function (from dataset):")
        lines.append(str(buggy_fl).strip()[:4000])
    return "\n".join(lines)


def has_spec_checkout(
    project_name: str,
    bug_index: str,
    workspace: str = DEFAULT_WORKSPACE,
) -> bool:
    """Return True when a defects4j checkout exists for spec generation."""
    return (
        spec_checkout_dir(project_name, bug_index, workspace) / ".defects4j.config"
    ).is_file()


def fetch_defects4j_gt_localization(project_name: str, bug_index: str) -> str:
    """Read GT buggy-lines / buggy-methods (RepairAgent ``get_localization`` parity)."""
    root = reinfix_root()
    lines_dir = root / "defects4j" / "buggy-lines"
    methods_dir = root / "defects4j" / "buggy-methods"
    parts: list[str] = []

    lines_file = lines_dir / "{}-{}.buggy.lines".format(project_name, bug_index)
    if lines_file.is_file():
        bug_lines = lines_file.read_text(encoding="utf-8").strip()
        if bug_lines:
            parts.append(
                "The bug is located at exactly these lines numbers: "
                "(the format is file-name#line-number# line-code):\n"
                + bug_lines
            )

    methods_file = methods_dir / "{}-{}.buggy.methods".format(project_name, bug_index)
    if methods_file.is_file():
        methods_info = "The following is the list of buggy methods:\n"
        for line in methods_file.read_text(encoding="utf-8").splitlines():
            if line.endswith("1"):
                methods_info += line + "\n"
        if methods_info.strip() != "The following is the list of buggy methods:":
            parts.append(methods_info.rstrip())

    return "\n".join(parts).strip()


def _extract_root_cause_from_info(info: str) -> str:
    separator = "--------------------------------------------------------------------------------"
    start = info.find("Root cause")
    if start < 0:
        return ""
    end = info[start:].find(separator)
    if end < 0:
        return info[start:].strip()
    return info[start : start + end].strip()


def fetch_defects4j_info(project_name: str, bug_index: str) -> str:
    """Run ``defects4j info`` and return the root-cause section when available."""
    setup_environment()
    result = subprocess.run(
        "defects4j info -p {} -b {}".format(project_name, bug_index),
        shell=True,
        cwd=str(reinfix_root()),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning(
            "defects4j info failed for %s-%s: %s",
            project_name,
            bug_index,
            (result.stderr or result.stdout or "").strip(),
        )
        return ""
    return _extract_root_cause_from_info(result.stdout or "")


def should_use_d4j_info(use_d4j_info: bool | None = None) -> bool:
    if use_d4j_info is not None:
        return use_d4j_info
    flag = os.environ.get("REINFIX_SPEC_USE_D4J_INFO", "1").strip().lower()
    return flag not in ("0", "false", "no", "off")


def resolve_localization_info(
    dataset_entry: dict[str, Any],
    project_name: str,
    bug_index: str,
    use_d4j_info: bool | None = None,
) -> str:
    """Merge dataset localization with GT files and optional ``defects4j info``."""
    parts = [build_localization_info(dataset_entry)]
    gt = fetch_defects4j_gt_localization(project_name, bug_index)
    if gt:
        parts.append(gt)
    if should_use_d4j_info(use_d4j_info):
        try:
            info = fetch_defects4j_info(project_name, bug_index)
            if info:
                parts.append(info)
        except Exception as exc:
            logger.warning(
                "defects4j info unavailable for %s-%s: %s",
                project_name,
                bug_index,
                exc,
            )
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def checkout_for_spec(
    project_name: str,
    bug_index: str,
    workspace: Optional[str | Path] = None,
    link_joern: bool = True,
) -> str:
    setup_environment()
    workspace_path = Path(workspace) if workspace else spec_workspace_dir()
    workspace_path.mkdir(parents=True, exist_ok=True)
    write_to = spec_checkout_dir(project_name, bug_index, workspace_path.name)
    config_file = write_to / ".defects4j.config"
    if write_to.is_dir():
        shutil.rmtree(write_to)
    cmd = "defects4j checkout -p {} -v {}b -w {}".format(
        project_name, bug_index, write_to
    )
    subprocess.run(cmd, shell=True, check=True, cwd=str(reinfix_root()))
    if not config_file.is_file():
        raise RuntimeError("Spec checkout failed: missing {}".format(config_file))
    if link_joern:
        link_joern_checkout(project_name, bug_index, workspace_path.name)
    return str(write_to)


def load_spec_max_attempts(hyperparams_file: Optional[str | Path] = None) -> int:
    path = Path(hyperparams_file) if hyperparams_file else hyperparams_path()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return int((data.get("spec_control") or {}).get("max_attempts", 3))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return 3


def get_spec_prompt_section(spec_result: dict[str, Any]) -> str:
    """Verified spec text for ReInFix ReAct / patch prompts."""
    return (spec_result.get("prompt_section") or "").strip()


def resolve_experiment_dir(exp_dir: str | None = None) -> str:
    """Return an experiment folder path, creating one if ``experiments_list`` is empty."""
    if exp_dir:
        spec_logs = os.path.join(exp_dir, "spec_logs")
        os.makedirs(spec_logs, exist_ok=True)
        return exp_dir

    list_path = reinfix_root() / "experimental_setups" / "experiments_list.txt"
    try:
        entries = [
            ln.strip()
            for ln in list_path.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
    except OSError:
        entries = []

    if entries:
        active = reinfix_root() / "experimental_setups" / entries[-1]
        os.makedirs(active / "spec_logs", exist_ok=True)
        return str(active)

    from spec_integration.experiment_logging import ensure_experiment_started

    return ensure_experiment_started()


def ensure_spec_runtime(exp_dir: str | None = None) -> str:
    """Chdir to ReInFix root, link Defects4J assets, patch spec log hooks."""
    setup_environment()
    from experiment_manager import patch_experiment_hooks

    active = resolve_experiment_dir(exp_dir)
    return patch_experiment_hooks(active)


def build_spec_inputs(
    bug_name: str,
    dataset_entry: dict[str, Any],
    model: str,
    max_attempts: int | None = None,
    hyperparams_file: str | Path | None = None,
    workspace: str = DEFAULT_WORKSPACE,
    run_tests: bool | None = None,
    use_d4j_info: bool | None = None,
) -> dict[str, Any]:
    """Map a ReInFix dataset row to ``generate_spec`` keyword arguments."""
    project_name, bug_index = parse_bug_id(bug_name)
    attempts = (
        max_attempts
        if max_attempts is not None
        else load_spec_max_attempts(hyperparams_file)
    )
    return {
        "project_name": project_name,
        "bug_index": bug_index,
        "localization_info": resolve_localization_info(
            dataset_entry,
            project_name,
            bug_index,
            use_d4j_info=use_d4j_info,
        ),
        "test_results": resolve_test_results(
            dataset_entry,
            project_name,
            bug_index,
            workspace=workspace,
            run_tests=run_tests,
        ),
        "model": model,
        "workspace": workspace,
        "max_attempts": attempts,
    }


def run_spec_for_dataset_bug(
    bug_name: str,
    dataset_entry: dict[str, Any],
    model: str,
    max_attempts: int | None = None,
    exp_dir: str | None = None,
    hyperparams_file: str | Path | None = None,
    workspace: str = DEFAULT_WORKSPACE,
    checkout: bool = True,
    run_tests: bool | None = None,
    use_d4j_info: bool | None = None,
) -> dict[str, Any]:
    """Checkout buggy project and run generate+verify spec (ReInFix ``spec`` package)."""
    bug_key = normalize_bug_name(bug_name)
    project_name, bug_index = parse_bug_id(bug_key)
    ensure_spec_runtime(exp_dir)

    if checkout:
        checkout_for_spec(
            project_name,
            bug_index,
            workspace=spec_workspace_dir(workspace),
            link_joern=True,
        )
    elif (spec_checkout_dir(project_name, bug_index, workspace) / ".defects4j.config").is_file():
        link_joern_checkout(project_name, bug_index, workspace)

    spec_inputs = build_spec_inputs(
        bug_key,
        dataset_entry,
        model=model,
        max_attempts=max_attempts,
        hyperparams_file=hyperparams_file,
        workspace=workspace,
        run_tests=run_tests,
        use_d4j_info=use_d4j_info,
    )

    from spec.spec_generator import generate_spec

    result = generate_spec(**spec_inputs)
    result.setdefault("project_name", project_name)
    result.setdefault("bug_index", bug_index)
    result["joern_project_name"] = joern_project_name(project_name, bug_index)
    result["spec_checkout_dir"] = str(spec_checkout_dir(project_name, bug_index, workspace))
    result["joern_checkout_link"] = str(joern_checkout_link(project_name, bug_index))
    return result


def run_spec_for_bug_name(
    bug_name: str,
    model: str,
    max_attempts: int | None = None,
    exp_dir: str | None = None,
    dataset_path: str | Path | None = None,
    variant: Literal["sf", "mf"] = "sf",
    hyperparams_file: str | Path | None = None,
    run_tests: bool | None = None,
    use_d4j_info: bool | None = None,
) -> dict[str, Any]:
    """Load dataset entry by bug id and run the spec pipeline."""
    entry = load_dataset_entry(bug_name, path=dataset_path, variant=variant)
    return run_spec_for_dataset_bug(
        bug_name,
        entry,
        model=model,
        max_attempts=max_attempts,
        exp_dir=exp_dir,
        hyperparams_file=hyperparams_file,
        run_tests=run_tests,
        use_d4j_info=use_d4j_info,
    )
