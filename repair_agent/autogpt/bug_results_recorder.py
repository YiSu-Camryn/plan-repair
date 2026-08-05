"""Per-bug experiment summary — one JSON line per bug in bug_results.jsonl."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from autogpt.bug_log_metrics import extract_repair_context_metrics, extract_spec_log_metrics
from autogpt.plan_localization_metrics import extract_plan_localization_metrics
from autogpt.config.hyperparams_loader import (
    EXIT_BUDGET_EXHAUSTED,
    EXIT_STAGNATION,
)
from autogpt.llm.api_manager import ApiManager
from autogpt.logs import logger

if TYPE_CHECKING:
    from autogpt.agents.agent import Agent

BUG_RESULTS_FILENAME = "bug_results.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_experiment_dir() -> Optional[str]:
    try:
        with open("experimental_setups/experiments_list.txt", encoding="utf-8") as handle:
            exps = handle.read().splitlines()
        if exps:
            return os.path.join("experimental_setups", exps[-1])
    except OSError:
        pass
    return None


def _rel_path(path: str) -> Optional[str]:
    if path and os.path.exists(path):
        return os.path.relpath(path, ".")
    return None


def _build_artifacts(exp_dir: Optional[str], project: str, bug_index: str) -> dict[str, Optional[str]]:
    if not exp_dir:
        return {}
    tag = "{}_{}".format(project, bug_index)
    paths = {
        "prompt_history": os.path.join(exp_dir, "logs", "prompt_history_{}".format(tag)),
        "model_responses": os.path.join(exp_dir, "responses", "model_responses_{}".format(tag)),
        "plausible_patches": os.path.join(
            exp_dir, "plausible_patches", "plausible_patches_{}.json".format(tag)
        ),
        "saved_context": os.path.join(exp_dir, "saved_contexts", "saved_context_{}".format(tag)),
        "spec_failure_detail": os.path.join(
            exp_dir, "spec_logs", "spec_failure_{}_{}.json".format(project, bug_index)
        ),
        "spec_logs_dir": os.path.join(exp_dir, "spec_logs"),
        "mutations_history_dir": os.path.join(exp_dir, "mutations_history"),
    }
    return {key: _rel_path(path) for key, path in paths.items()}


def _extract_verifier_summary(spec_result: dict[str, Any]) -> Optional[str]:
    if spec_result.get("spec_verifier_summary"):
        return spec_result["spec_verifier_summary"]
    attempts = spec_result.get("attempts") or []
    for item in reversed(attempts):
        if item.get("stage") == "verify":
            summary = item.get("summary")
            if summary:
                return summary
            verdict = item.get("verdict")
            if verdict:
                return str(verdict)
    return None


def _spec_fields(spec_result: dict[str, Any]) -> dict[str, Any]:
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
        "spec_attempts_used": spec_result.get("attempts_used"),
        "spec_max_attempts": spec_result.get("max_attempts"),
        "spec_final_verdict": final_verdict,
        "spec_failure_reason": spec_result.get("failure_reason"),
        "spec_verifier_summary": _extract_verifier_summary(spec_result),
    }


def _has_plausible_patch(exp_dir: Optional[str], project: str, bug_index: str) -> bool:
    if not exp_dir:
        return False
    path = os.path.join(
        exp_dir, "plausible_patches", "plausible_patches_{}_{}.json".format(project, bug_index)
    )
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return bool(data)
    except (json.JSONDecodeError, OSError):
        return False


def _resolve_repair_outcome(
    agent: Agent, exp_dir: Optional[str]
) -> tuple[str, Optional[str]]:
    project = agent.project_name
    bug_index = agent.bug_index
    if _has_plausible_patch(exp_dir, project, bug_index):
        return "FIXED", None

    exit_code = getattr(agent, "run_exit_code", 0) or 0
    exit_reason = getattr(agent, "run_exit_reason", None)

    if exit_code == EXIT_BUDGET_EXHAUSTED:
        return "BUDGET_EXHAUSTED", exit_reason or "Command budget exhausted"
    if exit_code == EXIT_STAGNATION:
        return "STAGNATION", exit_reason or "Stagnation: repeated info-gathering without fix progress"

    return "NOT_FIXED", exit_reason or "Repair finished without a plausible patch"


def _metrics_fields(elapsed_seconds: float) -> dict[str, Any]:
    api = ApiManager()
    prompt_tokens = api.get_total_prompt_tokens()
    completion_tokens = api.get_total_completion_tokens()
    cost_usd = api.get_total_cost()
    return {
        "elapsed_seconds": round(elapsed_seconds, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": round(cost_usd, 6),
    }


def append_bug_result(record: dict[str, Any]) -> str:
    """Append one bug summary line; return path written."""
    exp_dir = _current_experiment_dir()
    if not exp_dir:
        os.makedirs("experimental_setups", exist_ok=True)
        out_path = os.path.join("experimental_setups", BUG_RESULTS_FILENAME)
    else:
        os.makedirs(exp_dir, exist_ok=True)
        out_path = os.path.join(exp_dir, BUG_RESULTS_FILENAME)

    record.setdefault("recorded_at", _utc_now())
    if exp_dir:
        record.setdefault("experiment", os.path.basename(exp_dir))

    with open(out_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(
        "BUG RESULT: {} {} → {} (spec_ok={}, repair_cycles={})".format(
            record.get("project"),
            record.get("bug_index"),
            record.get("outcome"),
            record.get("spec_success"),
            record.get("repair_cycles_used"),
        )
    )
    return out_path


def record_bug_result_spec_failed(
    spec_result: dict[str, Any],
    model: str,
    elapsed_seconds: float,
    started_at: str,
) -> None:
    project = spec_result.get("project_name", "unknown")
    bug_index = str(spec_result.get("bug_index", "unknown"))
    exp_dir = _current_experiment_dir()
    spec_fields = _spec_fields(spec_result)

    record = {
        "project": project,
        "bug_index": bug_index,
        "model": model,
        "started_at": started_at,
        "ended_at": _utc_now(),
        "outcome": "SPEC_FAILED",
        **spec_fields,
        "repair_ran": False,
        "repair_cycles_used": None,
        "fixes_attempted": None,
        "repair_failure_reason": None,
        "spec_log_metrics": extract_spec_log_metrics(exp_dir, project, bug_index, spec_result),
        "repair_context_metrics": None,
        "plan_localization": extract_plan_localization_metrics(
            exp_dir, project, bug_index, spec_result
        ),
        **_metrics_fields(elapsed_seconds),
        "artifacts": _build_artifacts(exp_dir, project, bug_index),
    }
    append_bug_result(record)


def record_bug_result_from_agent(agent: Agent, elapsed_seconds: float) -> None:
    project = getattr(agent, "project_name", "unknown")
    bug_index = str(getattr(agent, "bug_index", "unknown"))
    exp_dir = _current_experiment_dir()
    spec_result = getattr(agent, "spec_result", {}) or {}
    spec_fields = _spec_fields(spec_result)

    outcome, repair_failure_reason = _resolve_repair_outcome(agent, exp_dir)
    fixes = getattr(agent, "suggested_fixes", None)
    fixes_count = len(fixes) if fixes else 0

    model = agent.config.smart_llm if agent.big_brain else agent.config.fast_llm

    record = {
        "project": project,
        "bug_index": bug_index,
        "model": model,
        "started_at": getattr(agent, "bug_run_started_at", None) or _utc_now(),
        "ended_at": _utc_now(),
        "outcome": outcome,
        **spec_fields,
        "repair_ran": True,
        "repair_cycles_used": getattr(agent, "cycle_count", 0),
        "fixes_attempted": fixes_count,
        "repair_failure_reason": repair_failure_reason,
        "spec_log_metrics": extract_spec_log_metrics(exp_dir, project, bug_index, spec_result),
        "repair_context_metrics": extract_repair_context_metrics(
            exp_dir, project, bug_index, agent=agent
        ),
        "plan_localization": extract_plan_localization_metrics(
            exp_dir, project, bug_index, spec_result
        ),
        **_metrics_fields(elapsed_seconds),
        "artifacts": _build_artifacts(exp_dir, project, bug_index),
    }
    append_bug_result(record)
