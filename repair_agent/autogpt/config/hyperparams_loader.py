"""Load hyperparams JSON with built-in defaults (including commands_limit)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_COMMANDS_LIMIT = 40
DEFAULT_SPEC_MAX_ATTEMPTS = 3

# Process exit codes used when stopping a bug run early.
EXIT_BUDGET_EXHAUSTED = 2
EXIT_STAGNATION = 3
EXIT_SPEC_FAILED = 4

DEFAULT_STAGNATION_CONTROL: dict[str, int] = {
    # Same command + args repeated this many times → stop (wasted re-reads).
    "same_command_repeat_limit": 3,
    # Last N commands all info-gathering, no fix attempt → stop (spinning).
    "max_consecutive_info_commands": 12,
}

DEFAULT_SPEC_CONTROL: dict[str, int] = {
    "max_attempts": DEFAULT_SPEC_MAX_ATTEMPTS,
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
    "spec_control": DEFAULT_SPEC_CONTROL,
}


def resolve_spec_max_attempts(
    hyperparams: dict[str, Any], cli_override: int | None = None
) -> int:
    if cli_override is not None:
        return max(1, cli_override)
    spec_control = hyperparams.get("spec_control") or {}
    max_attempts = spec_control.get("max_attempts", DEFAULT_SPEC_MAX_ATTEMPTS)
    if not isinstance(max_attempts, int) or max_attempts < 1:
        return DEFAULT_SPEC_MAX_ATTEMPTS
    return max_attempts


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
    if "spec_control" in hyperparams:
        merged["spec_control"] = {
            **DEFAULT_SPEC_CONTROL,
            **hyperparams["spec_control"],
        }
    limit = merged.get("commands_limit")
    if not isinstance(limit, int) or limit < 1:
        merged["commands_limit"] = DEFAULT_COMMANDS_LIMIT
    return merged


def load_hyperparams(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return normalize_hyperparams(json.load(f))
