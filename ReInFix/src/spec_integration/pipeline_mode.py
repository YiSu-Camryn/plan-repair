"""ReInFix pipeline mode: baseline (original) vs spec-enabled."""

from __future__ import annotations

import os
from typing import Any, Literal, Optional

PipelineMode = Literal["baseline", "spec"]
DEFAULT_PIPELINE_MODE: PipelineMode = "spec"
VALID_MODES = frozenset({"baseline", "spec"})


def normalize_pipeline_mode(value: str | None) -> PipelineMode | None:
    """Return a canonical mode string, or None if invalid / empty."""
    if value is None:
        return None
    mode = value.strip().lower()
    if not mode:
        return None
    if mode in VALID_MODES:
        return mode  # type: ignore[return-value]
    aliases = {
        "reinfix": "baseline",
        "original": "baseline",
        "no_spec": "baseline",
        "nospec": "baseline",
        "without_spec": "baseline",
        "reinfix+spec": "spec",
        "with_spec": "spec",
        "spec_enabled": "spec",
    }
    return aliases.get(mode)  # type: ignore[return-value]


def resolve_pipeline_mode(
    cli_mode: str | None = None,
    hyperparams: dict[str, Any] | None = None,
) -> PipelineMode:
    """Resolve mode: CLI > REINFIX_MODE env > hyperparams.pipeline_mode > default."""
    for candidate in (
        cli_mode,
        os.environ.get("REINFIX_MODE"),
        (hyperparams or {}).get("pipeline_mode"),
    ):
        if isinstance(candidate, str):
            mode = normalize_pipeline_mode(candidate)
            if mode is not None:
                return mode
    return DEFAULT_PIPELINE_MODE


def is_spec_enabled(mode: PipelineMode) -> bool:
    return mode == "spec"


def backend_name(mode: PipelineMode) -> str:
    return "reinfix+spec" if mode == "spec" else "reinfix"


def mode_label(mode: PipelineMode) -> str:
    return "ReInFix+spec" if mode == "spec" else "ReInFix (baseline)"


def skipped_spec_result(max_attempts: int | None = None) -> dict[str, Any]:
    """Placeholder result when baseline mode skips generate+verify spec."""
    return {
        "success": False,
        "skipped": True,
        "spec_final_verdict": "SKIPPED",
        "failure_reason": None,
        "attempts_used": 0,
        "max_attempts": max_attempts,
        "prompt_section": "",
        "spec_verifier_summary": None,
    }
