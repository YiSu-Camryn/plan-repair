"""Load hyperparams JSON with built-in defaults (including commands_limit)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_COMMANDS_LIMIT = 100

# Process exit codes used when stopping a bug run early.
EXIT_BUDGET_EXHAUSTED = 2
EXIT_STAGNATION = 3

DEFAULT_STAGNATION_CONTROL: dict[str, int] = {
    # Same command + args repeated this many times → stop (wasted re-reads).
    "same_command_repeat_limit": 3,
    # Last N commands all info-gathering, no fix attempt → stop (spinning).
    "max_consecutive_info_commands": 12,
}

DEFAULT_HYPERPARAMS: dict[str, Any] = {
    "budget_control": {
        "name": "FULL-TRACK",
        "params": {"#fixes": 4},
    },
    "repetition_handling": "RESTRICT",
    "external_fix_strategy": 0,
    "commands_limit": DEFAULT_COMMANDS_LIMIT,
    "stagnation_control": DEFAULT_STAGNATION_CONTROL,
}


def normalize_hyperparams(hyperparams: dict[str, Any]) -> dict[str, Any]:
    """Merge user hyperparams over defaults so commands_limit is always enforced."""
    merged = {**DEFAULT_HYPERPARAMS, **hyperparams}
    if "budget_control" in hyperparams:
        merged["budget_control"] = {
            **DEFAULT_HYPERPARAMS["budget_control"],
            **hyperparams["budget_control"],
        }
        if "params" in hyperparams["budget_control"]:
            merged["budget_control"]["params"] = {
                **DEFAULT_HYPERPARAMS["budget_control"]["params"],
                **hyperparams["budget_control"]["params"],
            }
    if "stagnation_control" in hyperparams:
        merged["stagnation_control"] = {
            **DEFAULT_STAGNATION_CONTROL,
            **hyperparams["stagnation_control"],
        }
    limit = merged.get("commands_limit")
    if not isinstance(limit, int) or limit < 1:
        merged["commands_limit"] = DEFAULT_COMMANDS_LIMIT
    return merged


def load_hyperparams(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return normalize_hyperparams(json.load(f))
