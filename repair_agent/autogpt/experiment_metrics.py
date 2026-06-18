"""Per-bug run metrics (time, tokens, cost) written into each experiment folder."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from autogpt.llm.api_manager import ApiManager
from autogpt.logs import logger

if TYPE_CHECKING:
    from autogpt.agents.agent import Agent

METRICS_JSON = "bug_run_metrics.json"
METRICS_CSV = "bug_run_metrics.csv"

CSV_HEADERS = [
    "bug_name",
    "project",
    "bug_index",
    "model",
    "elapsed_seconds",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cost_usd",
    "recorded_at",
]


def _experiment_dir(agent: Agent) -> Optional[str]:
    exps = getattr(agent, "exps", None)
    if not exps:
        return None
    return os.path.join("experimental_setups", exps[-1])


def _bug_label(project_name: str, bug_index: str) -> str:
    return f"{project_name} {bug_index}"


def _primary_model(agent: Agent) -> str:
    return agent.config.smart_llm if agent.big_brain else agent.config.fast_llm


def _load_metrics_json(path: str) -> list[dict[str, Any]]:
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return data
    return []


def _write_metrics_csv(path: str, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in CSV_HEADERS})


def record_bug_run_metrics(agent: Agent, elapsed_seconds: float) -> None:
    """Append one bug's time/token/cost record to the active experiment folder."""
    exp_dir = _experiment_dir(agent)
    project_name = getattr(agent, "project_name", None)
    bug_index = getattr(agent, "bug_index", None)
    if not exp_dir or not project_name or not bug_index:
        logger.debug("Skipping bug run metrics: experiment or bug identity unavailable")
        return

    api_manager = ApiManager()
    prompt_tokens = api_manager.get_total_prompt_tokens()
    completion_tokens = api_manager.get_total_completion_tokens()
    cost_usd = api_manager.get_total_cost()
    model = _primary_model(agent)
    bug_name = _bug_label(project_name, bug_index)
    recorded_at = datetime.now(timezone.utc).isoformat()

    record = {
        "bug_name": bug_name,
        "project": project_name,
        "bug_index": str(bug_index),
        "model": model,
        "elapsed_seconds": round(elapsed_seconds, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": round(cost_usd, 6),
        "recorded_at": recorded_at,
    }

    os.makedirs(exp_dir, exist_ok=True)
    json_path = os.path.join(exp_dir, METRICS_JSON)
    csv_path = os.path.join(exp_dir, METRICS_CSV)

    rows = _load_metrics_json(json_path)
    rows.append(record)

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)

    _write_metrics_csv(csv_path, rows)

    logger.info(
        "BUG METRICS: {} | {:.1f}s | {} prompt + {} completion tokens | ${:.4f}".format(
            bug_name,
            elapsed_seconds,
            prompt_tokens,
            completion_tokens,
            cost_usd,
        )
    )
