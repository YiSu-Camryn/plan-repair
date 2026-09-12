"""Write bug_results.jsonl and bug_run_metrics for ReInFix runs (RepairAgent schema)."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from experiment_manager import current_experiment_dir, patch_repairagent_experiment_hooks
from paths import ensure_repairagent_on_path


METRICS_JSON = "bug_run_metrics.json"
METRICS_CSV = "bug_run_metrics.csv"
CSV_HEADERS = [
    "bug_name",
    "project",
    "bug_index",
    "model",
    "pipeline_mode",
    "backend",
    "elapsed_seconds",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cost_usd",
    "recorded_at",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _spec_fields(spec_result: dict[str, Any]) -> dict[str, Any]:
    if spec_result.get("skipped"):
        return {
            "spec_success": False,
            "spec_skipped": True,
            "spec_attempts_used": spec_result.get("attempts_used"),
            "spec_max_attempts": spec_result.get("max_attempts"),
            "spec_final_verdict": "SKIPPED",
            "spec_failure_reason": None,
            "spec_verifier_summary": None,
        }

    success = bool(spec_result.get("success"))
    final_verdict = spec_result.get("spec_final_verdict")
    if not final_verdict:
        if not success:
            final_verdict = "FAILED"
        elif spec_result.get("attempts_used", 0) == 0 and not spec_result.get("prompt_section"):
            final_verdict = "SKIPPED"
        else:
            final_verdict = "ACCEPT"
    return {
        "spec_success": success,
        "spec_skipped": False,
        "spec_attempts_used": spec_result.get("attempts_used"),
        "spec_max_attempts": spec_result.get("max_attempts"),
        "spec_final_verdict": final_verdict,
        "spec_failure_reason": spec_result.get("failure_reason"),
        "spec_verifier_summary": spec_result.get("spec_verifier_summary"),
    }


def append_metrics(exp_dir: str, record: dict[str, Any]) -> None:
    json_path = os.path.join(exp_dir, METRICS_JSON)
    rows: list[dict[str, Any]] = []
    if os.path.isfile(json_path):
        with open(json_path, encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, list):
                rows = data
    rows.append(record)
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
    csv_path = os.path.join(exp_dir, METRICS_CSV)
    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in CSV_HEADERS})


def record_spec_failed(
    project: str,
    bug_index: str,
    spec_result: dict[str, Any],
    model: str,
    elapsed_seconds: float,
    started_at: str,
    token_stats: dict[str, Any],
    backend: str = "reinfix+spec",
    pipeline_mode: str = "spec",
    repair_scenario: str | None = None,
    dataset: str | None = None,
) -> None:
    ensure_repairagent_on_path()
    exp_dir = current_experiment_dir()
    patch_repairagent_experiment_hooks(exp_dir)

    from autogpt.bug_log_metrics import extract_plan_localization_metrics, extract_spec_log_metrics
    from autogpt.bug_results_recorder import append_bug_result
    from autogpt.spec_failure_recorder import record_spec_failure

    record_spec_failure(project, bug_index, spec_result)
    record = {
        "project": project,
        "bug_index": bug_index,
        "model": model,
        "pipeline_mode": pipeline_mode,
        "started_at": started_at,
        "ended_at": _utc_now(),
        "outcome": "SPEC_FAILED",
        **_spec_fields(spec_result),
        "repair_ran": False,
        "repair_cycles_used": None,
        "fixes_attempted": None,
        "repair_failure_reason": None,
        "backend": backend,
        "spec_log_metrics": extract_spec_log_metrics(exp_dir, project, bug_index, spec_result),
        "repair_context_metrics": None,
        "plan_localization": extract_plan_localization_metrics(
            exp_dir, project, bug_index, spec_result
        ),
        **token_stats,
        "elapsed_seconds": round(elapsed_seconds, 2),
    }
    if repair_scenario:
        record["repair_scenario"] = repair_scenario
    if dataset:
        record["dataset"] = dataset
    append_bug_result(record)
    append_metrics(
        exp_dir,
        {
            "bug_name": "{} {}".format(project, bug_index),
            "project": project,
            "bug_index": str(bug_index),
            "model": model,
            "pipeline_mode": pipeline_mode,
            "backend": backend,
            **token_stats,
            "elapsed_seconds": round(elapsed_seconds, 2),
            "recorded_at": _utc_now(),
        },
    )


def record_bug_run(
    project: str,
    bug_index: str,
    spec_result: dict[str, Any],
    model: str,
    outcome: str,
    elapsed_seconds: float,
    started_at: str,
    token_stats: dict[str, Any],
    repair_cycles_used: int,
    fixes_attempted: int,
    repair_failure_reason: Optional[str] = None,
    plausible_patch_path: Optional[str] = None,
    react_output_path: Optional[str] = None,
    spec_prompt_artifact: Optional[str] = None,
    injection_prompt_artifacts: Optional[dict[str, str]] = None,
    backend: str = "reinfix+spec",
    pipeline_mode: str = "spec",
    repair_scenario: str | None = None,
    dataset: str | None = None,
) -> None:
    ensure_repairagent_on_path()
    exp_dir = current_experiment_dir()
    patch_repairagent_experiment_hooks(exp_dir)

    from autogpt.bug_log_metrics import extract_plan_localization_metrics, extract_spec_log_metrics

    from autogpt.bug_results_recorder import append_bug_result

    injection = injection_prompt_artifacts or {}
    spec_skipped = bool(spec_result.get("skipped"))
    artifacts = {
        "spec_logs_dir": None if spec_skipped else os.path.join(exp_dir, "spec_logs"),
        "spec_prompt_section": spec_prompt_artifact,
        "react_injection_prompt": injection.get("react_prompt"),
        "patch_injection_prompt_sample": injection.get("patch_prompt_sample"),
        "model_responses": react_output_path,
        "plausible_patches": plausible_patch_path,
        "prompt_history": None,
        "saved_context": None,
        "spec_failure_detail": None,
        "mutations_history_dir": None,
    }

    if spec_skipped:
        spec_log_metrics = None
        plan_localization = None
    else:
        spec_log_metrics = extract_spec_log_metrics(exp_dir, project, bug_index, spec_result)
        plan_localization = extract_plan_localization_metrics(
            exp_dir, project, bug_index, spec_result
        )

    record = {
        "project": project,
        "bug_index": bug_index,
        "model": model,
        "pipeline_mode": pipeline_mode,
        "started_at": started_at,
        "ended_at": _utc_now(),
        "outcome": outcome,
        **_spec_fields(spec_result),
        "repair_ran": True,
        "repair_cycles_used": repair_cycles_used,
        "fixes_attempted": fixes_attempted,
        "repair_failure_reason": repair_failure_reason,
        "backend": backend,
        "spec_log_metrics": spec_log_metrics,
        "repair_context_metrics": {
            "react_output_path": react_output_path,
            "fixes_attempted": fixes_attempted,
            "pipeline_mode": pipeline_mode,
        },
        "plan_localization": plan_localization,
        **token_stats,
        "elapsed_seconds": round(elapsed_seconds, 2),
        "artifacts": artifacts,
    }
    if repair_scenario:
        record["repair_scenario"] = repair_scenario
    if dataset:
        record["dataset"] = dataset
    append_bug_result(record)
    append_metrics(
        exp_dir,
        {
            "bug_name": "{} {}".format(project, bug_index),
            "project": project,
            "bug_index": str(bug_index),
            "model": model,
            "pipeline_mode": pipeline_mode,
            "backend": backend,
            **token_stats,
            "elapsed_seconds": round(elapsed_seconds, 2),
            "recorded_at": _utc_now(),
        },
    )
