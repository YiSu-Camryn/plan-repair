"""Record and display behavioral-spec pipeline failures."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from autogpt.logs import logger


class SpecPipelineError(Exception):
    """Raised when spec generate/verify does not reach ACCEPT."""

    def __init__(self, result: dict[str, Any]):
        self.result = result
        reason = result.get("failure_reason") or result.get("error") or "unknown"
        super().__init__("Spec pipeline failed: {}".format(reason))


def _current_experiment_dir() -> str | None:
    try:
        with open("experimental_setups/experiments_list.txt", encoding="utf-8") as handle:
            exps = handle.read().splitlines()
        if exps:
            return os.path.join("experimental_setups", exps[-1])
    except OSError:
        pass
    return None


def record_spec_failure(
    project_name: str, bug_index: str, result: dict[str, Any]
) -> str:
    """Write failure artifacts and return the detail JSON path."""
    exp_dir = _current_experiment_dir()
    spec_logs_dir = os.path.join(exp_dir, "spec_logs") if exp_dir else "spec_logs"
    os.makedirs(spec_logs_dir, exist_ok=True)

    detail = {
        "project": project_name,
        "bug_index": bug_index,
        "failure_reason": result.get("failure_reason"),
        "error": result.get("error"),
        "attempts_used": result.get("attempts_used"),
        "max_attempts": result.get("max_attempts"),
        "attempts": result.get("attempts"),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    detail_filename = "spec_failure_{}_{}.json".format(project_name, bug_index)
    detail_path = os.path.join(spec_logs_dir, detail_filename)
    with open(detail_path, "w", encoding="utf-8") as handle:
        json.dump({**result, **detail}, handle, indent=2)

    if exp_dir:
        jsonl_path = os.path.join(exp_dir, "spec_failures.jsonl")
        with open(jsonl_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(detail) + "\n")

        marker_path = os.path.join(
            exp_dir, "SPEC_FAILED_{}_{}.txt".format(project_name, bug_index)
        )
        with open(marker_path, "w", encoding="utf-8") as handle:
            handle.write(
                "SPEC PIPELINE FAILED — {} {}\n".format(project_name, bug_index)
            )
            handle.write("Reason: {}\n".format(detail["failure_reason"]))
            handle.write(
                "Attempts: {}/{}\n".format(
                    detail.get("attempts_used"), detail.get("max_attempts")
                )
            )
            handle.write("Detail: {}\n".format(detail_path))

    return detail_path


def log_spec_failure_banner(
    project_name: str,
    bug_index: str,
    result: dict[str, Any],
    detail_path: str,
) -> None:
    reason = result.get("failure_reason") or "UNKNOWN"
    used = result.get("attempts_used", "?")
    max_attempts = result.get("max_attempts", "?")
    logger.error(
        "\n"
        "============================================================\n"
        "  SPEC PIPELINE FAILED — {} {}\n"
        "  Reason: {}\n"
        "  Attempts: {}/{}\n"
        "  Detail: {}\n"
        "============================================================",
        project_name,
        bug_index,
        reason,
        used,
        max_attempts,
        detail_path,
    )
