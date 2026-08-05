"""Extract structured metrics from spec_logs/ and saved_contexts/ for bug_results.jsonl."""

from __future__ import annotations

import glob
import json
import os
import re
from collections import Counter
from typing import Any, Optional


def _load_json(path: str) -> Optional[Any]:
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return None


def _spec_logs_dir(exp_dir: Optional[str]) -> Optional[str]:
    if not exp_dir:
        return None
    path = os.path.join(exp_dir, "spec_logs")
    return path if os.path.isdir(path) else None


def _spec_log_path(exp_dir: Optional[str], suffix: str, project: str, bug_index: str) -> Optional[str]:
    logs_dir = _spec_logs_dir(exp_dir)
    if not logs_dir:
        return None
    return os.path.join(logs_dir, "spec_{}_{}_{}.json".format(suffix, project, bug_index))


def _find_last_attempt_file(
    exp_dir: Optional[str], project: str, bug_index: str, kind: str
) -> Optional[str]:
    logs_dir = _spec_logs_dir(exp_dir)
    if not logs_dir:
        return None
    pattern = os.path.join(
        logs_dir, "spec_attempt_*_{}_{}_{}.json".format(kind, project, bug_index)
    )
    candidates = glob.glob(pattern)
    if not candidates:
        return None

    def attempt_num(path: str) -> int:
        match = re.search(r"spec_attempt_(\d+)_" + re.escape(kind) + r"_", os.path.basename(path))
        return int(match.group(1)) if match else 0

    return max(candidates, key=attempt_num)


def _resolve_spec_json(
    exp_dir: Optional[str],
    project: str,
    bug_index: str,
    spec_result: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    if spec_result and isinstance(spec_result.get("spec_json"), dict):
        return spec_result["spec_json"]

    last_parsed = _find_last_attempt_file(exp_dir, project, bug_index, "parsed")
    data = _load_json(last_parsed) if last_parsed else None
    if isinstance(data, dict):
        return data

    fallback = _load_json(_spec_log_path(exp_dir, "parsed_json", project, bug_index))
    if isinstance(fallback, dict):
        return fallback
    return None


def _summarize_verify_issues(verify_result: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not verify_result:
        return {
            "verdict": None,
            "issue_count": 0,
            "critical_count": 0,
            "warning_count": 0,
            "checks_failed": [],
        }

    issues = verify_result.get("issues") or []
    checks: list[str] = []
    critical = 0
    warning = 0
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        check = issue.get("check")
        if check:
            checks.append(str(check))
        severity = str(issue.get("severity") or "").upper()
        if severity == "CRITICAL":
            critical += 1
        elif severity == "WARNING":
            warning += 1

    return {
        "verdict": verify_result.get("verdict"),
        "issue_count": len(issues),
        "critical_count": critical,
        "warning_count": warning,
        "checks_failed": sorted(set(checks)),
    }


def _resolve_last_verify_result(
    exp_dir: Optional[str],
    project: str,
    bug_index: str,
    spec_result: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    last_verify_path = _find_last_attempt_file(exp_dir, project, bug_index, "verify")
    data = _load_json(last_verify_path) if last_verify_path else None
    if isinstance(data, dict):
        return data

    failure_path = None
    if exp_dir:
        failure_path = os.path.join(
            exp_dir, "spec_logs", "spec_failure_{}_{}.json".format(project, bug_index)
        )
    failure_detail = _load_json(failure_path) if failure_path else None
    if isinstance(failure_detail, dict):
        attempts = failure_detail.get("attempts") or []
        for item in reversed(attempts):
            if item.get("stage") == "verify" and item.get("summary"):
                return {"verdict": item.get("verdict"), "issues": [], "summary": item.get("summary")}

    if spec_result:
        for item in reversed(spec_result.get("attempts") or []):
            if item.get("stage") == "verify":
                return {
                    "verdict": item.get("verdict"),
                    "issues": [],
                    "summary": item.get("summary"),
                }
    return None


def extract_spec_log_metrics(
    exp_dir: Optional[str],
    project: str,
    bug_index: str,
    spec_result: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Metrics from spec_logs/ (evidence, spec content, verifier issues)."""
    gathered = _load_json(_spec_log_path(exp_dir, "gathered_info_json", project, bug_index))
    evidence: dict[str, Any] = {}
    if isinstance(gathered, dict):
        evidence = {
            "buggy_file": gathered.get("buggy_file"),
            "buggy_method_name": gathered.get("buggy_method_name"),
            "javadoc_found": gathered.get("javadoc_found"),
            "method_body_found": gathered.get("method_body_found"),
            "test_code_found": gathered.get("test_code_found"),
            "localization_included": gathered.get("localization_included"),
            "test_failure_source": gathered.get("test_failure_source"),
            "trigger_tests_found": gathered.get("trigger_tests_found"),
            "source_checkout_available": gathered.get("source_checkout_available"),
        }

    spec_json = _resolve_spec_json(exp_dir, project, bug_index, spec_result)
    content: dict[str, Any] = {}
    if spec_json:
        content = {
            "confidence": spec_json.get("confidence"),
            "fix_direction": spec_json.get("fix_direction"),
            "code_violations_count": len(spec_json.get("code_violations") or []),
            "rules_count": len(spec_json.get("rules") or []),
            "fix_targets_count": len(spec_json.get("fix_targets") or []),
            "had_clarifying_question": bool(spec_json.get("clarifying_question")),
            "had_developer_clarification": bool(spec_json.get("developer_clarification")),
        }

    verify_result = _resolve_last_verify_result(exp_dir, project, bug_index, spec_result)
    verifier = _summarize_verify_issues(verify_result)

    return {
        "evidence": evidence,
        "content": content,
        "verifier": verifier,
    }


def _command_name_from_history_entry(entry: Any) -> str:
    if not isinstance(entry, str):
        return ""
    if " , Your reasoning" in entry:
        return entry.split(" , Your reasoning")[0].strip()
    if " ," in entry:
        return entry.split(" ,")[0].strip()
    return entry.strip()


def _repair_context_from_dict(ctx: dict[str, Any]) -> dict[str, Any]:
    read_files = ctx.get("read_files") or {}
    files_read = len(read_files) if isinstance(read_files, dict) else 0
    line_ranges_read = 0
    if isinstance(read_files, dict):
        for ranges in read_files.values():
            if isinstance(ranges, list):
                line_ranges_read += len(ranges)

    search_queries = ctx.get("search_queries") or []
    extracted_methods = ctx.get("extracted_methods") or []
    hypothesises = ctx.get("hypothesises") or []
    commands_history = ctx.get("commands_history") or []
    suggested_fixes = ctx.get("suggested_fixes") or []

    command_names = [
        name for name in (_command_name_from_history_entry(e) for e in commands_history) if name
    ]
    command_counts = dict(Counter(command_names))

    similar_calls = ctx.get("similar_calls")
    similar_calls_count = 0
    if isinstance(similar_calls, list):
        similar_calls_count = len(similar_calls)

    return {
        "final_state": ctx.get("current_state"),
        "hypothesis_count": len(hypothesises) if isinstance(hypothesises, list) else 0,
        "files_read_count": files_read,
        "line_ranges_read_count": line_ranges_read,
        "search_queries_count": len(search_queries) if isinstance(search_queries, list) else 0,
        "extracted_methods_count": len(extracted_methods) if isinstance(extracted_methods, list) else 0,
        "similar_calls_count": similar_calls_count,
        "commands_executed_count": len(command_names),
        "unique_commands_count": len(command_counts),
        "command_counts": command_counts,
        "suggested_fixes_count": len(suggested_fixes) if isinstance(suggested_fixes, list) else 0,
    }


def _agent_to_context_dict(agent: Any) -> dict[str, Any]:
    return {
        "current_state": getattr(agent, "current_state", None),
        "hypothesises": getattr(agent, "hypothesises", []) or [],
        "read_files": getattr(agent, "read_files", {}) or {},
        "search_queries": getattr(agent, "search_queries", []) or [],
        "commands_history": getattr(agent, "commands_history", []) or [],
        "suggested_fixes": getattr(agent, "suggested_fixes", []) or [],
        "extracted_methods": getattr(agent, "extracted_methods", []) or [],
        "similar_calls": getattr(agent, "similar_calls", None),
    }


def extract_repair_context_metrics(
    exp_dir: Optional[str],
    project: str,
    bug_index: str,
    agent: Any = None,
) -> Optional[dict[str, Any]]:
    """Metrics from saved_contexts/ final snapshot (or live agent state)."""
    ctx: Optional[dict[str, Any]] = None
    if exp_dir:
        path = os.path.join(
            exp_dir, "saved_contexts", "saved_context_{}_{}".format(project, bug_index)
        )
        loaded = _load_json(path)
        if isinstance(loaded, dict):
            ctx = loaded

    if ctx is None and agent is not None:
        ctx = _agent_to_context_dict(agent)

    if ctx is None:
        return None

    return _repair_context_from_dict(ctx)
