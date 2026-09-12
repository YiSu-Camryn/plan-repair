"""Multi-function localization helpers for spec generation (MF dataset schema)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from spec_integration.spec_adapter import (
    fetch_defects4j_gt_localization,
    fetch_defects4j_info,
    parse_bug_id,
    resolve_test_results,
    should_use_d4j_info,
)

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE = "auto_gpt_workspace"
MF_DATASET_NAME = "defects4j-mf.json"


def mf_function_count(entry: dict[str, Any]) -> int:
    return int(entry.get("function_num") or len(entry.get("functions") or []))


def format_mf_functions_block(entry: dict[str, Any], include_markers: bool = True) -> str:
    """Render all buggy functions for ReAct / patch prompts."""
    functions = entry.get("functions") or []
    blocks: list[str] = []
    for idx, fn in enumerate(functions, 1):
        path = fn.get("path") or ""
        start = fn.get("start_loc")
        end = fn.get("end_loc")
        header = "Function {} ({}".format(idx, path)
        if start and end:
            header += ", lines {}-{}".format(start, end)
        header += "):"
        blocks.append(header)
        code = fn.get("buggy_fl") or fn.get("buggy_function") or ""
        if include_markers and "/* bug is here */" not in str(code):
            code = str(code).strip()
        blocks.append("```java\n{}\n```".format(str(code).strip()))
    return "\n\n".join(blocks)


def mf_primary_file_path(entry: dict[str, Any]) -> str:
    functions = entry.get("functions") or []
    if not functions:
        return ""
    paths = [fn.get("path") or "" for fn in functions if fn.get("path")]
    if not paths:
        return ""
    if len(set(paths)) == 1:
        return paths[0]
    return "; ".join(paths)


def build_localization_info_mf(dataset_entry: dict[str, Any]) -> str:
    functions = dataset_entry.get("functions") or []
    lines = [
        "Repair scenario: multi-function ({} function(s))".format(len(functions)),
    ]
    for idx, fn in enumerate(functions, 1):
        lines.append("")
        lines.append("--- Function {} ---".format(idx))
        lines.append("Buggy file: {}".format(fn.get("path") or ""))
        if fn.get("start_loc") and fn.get("end_loc"):
            lines.append(
                "Buggy line range: {}-{}".format(fn["start_loc"], fn["end_loc"])
            )
        buggy = fn.get("buggy_fl") or fn.get("buggy_function") or ""
        if buggy:
            lines.append("Buggy function (from dataset):")
            lines.append(str(buggy).strip()[:4000])
    if dataset_entry.get("issue_title"):
        lines.append("")
        lines.append("Issue: {}".format(dataset_entry["issue_title"]))
    if dataset_entry.get("issue_description"):
        desc = str(dataset_entry["issue_description"]).strip()
        if desc:
            lines.append("Description: {}".format(desc[:2000]))
    return "\n".join(lines)


def resolve_localization_info_mf(
    dataset_entry: dict[str, Any],
    project_name: str,
    bug_index: str,
    use_d4j_info: bool | None = None,
) -> str:
    """Merge MF dataset localization with GT files and optional ``defects4j info``."""
    parts = [build_localization_info_mf(dataset_entry)]
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


def build_spec_inputs_mf(
    bug_name: str,
    dataset_entry: dict[str, Any],
    model: str,
    max_attempts: int | None = None,
    hyperparams_file: str | Path | None = None,
    workspace: str = DEFAULT_WORKSPACE,
    run_tests: bool | None = None,
    use_d4j_info: bool | None = None,
) -> dict[str, Any]:
    """Map an MF dataset row to ``generate_spec`` keyword arguments."""
    from spec_integration.spec_adapter import load_spec_max_attempts

    project_name, bug_index = parse_bug_id(bug_name)
    attempts = (
        max_attempts
        if max_attempts is not None
        else load_spec_max_attempts(hyperparams_file)
    )
    return {
        "project_name": project_name,
        "bug_index": bug_index,
        "localization_info": resolve_localization_info_mf(
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
