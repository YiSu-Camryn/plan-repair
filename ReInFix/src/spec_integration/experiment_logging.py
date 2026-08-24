"""Experiment folders, bug_results.jsonl, and bug_run_metrics (RepairAgent-compatible)."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

from spec_integration.paths import reinfix_root


class TokenTracker:
    def __init__(self) -> None:
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cost_usd = 0.0

    def add_openai_usage(self, usage: Any, prompt_rate: float = 0.000005, completion_rate: float = 0.00002) -> None:
        if not usage:
            return
        self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
        self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
        self.cost_usd += (
            (getattr(usage, "prompt_tokens", 0) or 0) * prompt_rate
            + (getattr(usage, "completion_tokens", 0) or 0) * completion_rate
        )

    def add_langchain_callback(self, cb: Any) -> None:
        self.prompt_tokens += getattr(cb, "prompt_tokens", 0) or 0
        self.completion_tokens += getattr(cb, "completion_tokens", 0) or 0
        self.cost_usd += getattr(cb, "total_cost", 0.0) or 0.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_experiment_dir() -> str | None:
    list_path = reinfix_root() / "experimental_setups" / "experiments_list.txt"
    try:
        exps = list_path.read_text(encoding="utf-8").splitlines()
        if exps:
            return str(reinfix_root() / "experimental_setups" / exps[-1])
    except OSError:
        pass
    return None


def ensure_experiment_started() -> str:
    root = reinfix_root()
    script = root / "experimental_setups" / "increment_experiment.py"
    subprocess.run([sys.executable, str(script)], cwd=str(root), check=True)
    exp = _current_experiment_dir()
    if not exp:
        raise RuntimeError("Failed to create experiment folder")
    return exp


def _spec_fields(spec_result: dict[str, Any]) -> dict[str, Any]:
    success = bool(spec_result.get("success"))
    final_verdict = spec_result.get("spec_final_verdict")
    if not final_verdict:
        final_verdict = "ACCEPT" if success else "FAILED"
    return {
        "spec_success": success,
        "spec_attempts_used": spec_result.get("attempts_used"),
        "spec_max_attempts": spec_result.get("max_attempts"),
        "spec_final_verdict": final_verdict,
        "spec_failure_reason": spec_result.get("failure_reason"),
        "spec_verifier_summary": spec_result.get("spec_verifier_summary"),
    }


def _append_bug_run_metrics(record: dict[str, Any]) -> None:
    exp_dir = _current_experiment_dir()
    if not exp_dir:
        return
    json_path = os.path.join(exp_dir, "bug_run_metrics.json")
    csv_path = os.path.join(exp_dir, "bug_run_metrics.csv")
    headers = [
        "bug_name",
        "project",
        "bug_index",
        "model",
        "backend",
        "outcome",
        "elapsed_seconds",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cost_usd",
        "recorded_at",
    ]
    rows: list[dict[str, Any]] = []
    if os.path.isfile(json_path):
        with open(json_path, encoding="utf-8") as handle:
            loaded = json.load(handle)
            if isinstance(loaded, list):
                rows = loaded
    rows.append({key: record.get(key, "") for key in headers})
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


def record_spec_failed(
    spec_result: dict[str, Any],
    model: str,
    elapsed_seconds: float,
    started_at: str,
) -> None:
    from autogpt.bug_results_recorder import append_bug_result
    from autogpt.bug_log_metrics import extract_plan_localization_metrics, extract_spec_log_metrics
    from autogpt.spec_failure_recorder import record_spec_failure

    project = spec_result.get("project_name") or spec_result.get("project") or "unknown"
    bug_index = str(spec_result.get("bug_index") or "unknown")
    exp_dir = _current_experiment_dir()
    record_spec_failure(project, bug_index, spec_result)

    record = {
        "project": project,
        "bug_index": bug_index,
        "model": model,
        "backend": "reinfix+spec",
        "started_at": started_at,
        "ended_at": _utc_now(),
        "outcome": "SPEC_FAILED",
        **_spec_fields(spec_result),
        "repair_ran": False,
        "repair_cycles_used": None,
        "fixes_attempted": None,
        "repair_failure_reason": None,
        "spec_log_metrics": extract_spec_log_metrics(exp_dir, project, bug_index, spec_result),
        "repair_context_metrics": None,
        "plan_localization": extract_plan_localization_metrics(
            exp_dir, project, bug_index, spec_result
        ),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0.0,
        "artifacts": {"spec_logs_dir": os.path.join(exp_dir, "spec_logs") if exp_dir else None},
    }
    append_bug_result(record)
    _append_bug_run_metrics(record)


def record_bug_completed(
    project: str,
    bug_index: str,
    spec_result: dict[str, Any],
    model: str,
    started_at: str,
    elapsed_seconds: float,
    tracker: TokenTracker,
    outcome: str,
    repair_cycles_used: int,
    fixes_attempted: int,
    repair_failure_reason: str | None = None,
    artifacts: dict[str, Any] | None = None,
) -> None:
    from autogpt.bug_results_recorder import append_bug_result
    from autogpt.bug_log_metrics import extract_plan_localization_metrics, extract_spec_log_metrics

    exp_dir = _current_experiment_dir()
    record = {
        "project": project,
        "bug_index": bug_index,
        "model": model,
        "backend": "reinfix+spec",
        "started_at": started_at,
        "ended_at": _utc_now(),
        "outcome": outcome,
        **_spec_fields(spec_result),
        "repair_ran": True,
        "repair_cycles_used": repair_cycles_used,
        "fixes_attempted": fixes_attempted,
        "repair_failure_reason": repair_failure_reason,
        "spec_log_metrics": extract_spec_log_metrics(exp_dir, project, bug_index, spec_result),
        "repair_context_metrics": {
            "backend": "reinfix",
            "react_analysis_rounds": repair_cycles_used,
            "patches_generated": fixes_attempted,
        },
        "plan_localization": extract_plan_localization_metrics(
            exp_dir, project, bug_index, spec_result
        ),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "prompt_tokens": tracker.prompt_tokens,
        "completion_tokens": tracker.completion_tokens,
        "total_tokens": tracker.prompt_tokens + tracker.completion_tokens,
        "cost_usd": round(tracker.cost_usd, 6),
        "artifacts": artifacts or {},
    }
    append_bug_result(record)
    _append_bug_run_metrics(record)
