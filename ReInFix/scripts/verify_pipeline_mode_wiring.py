#!/usr/bin/env python3
"""Verify Step 3 pipeline mode wiring (imports + branch helpers, no LLM)."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from spec_integration.pipeline_mode import (  # noqa: E402
    backend_name,
    is_spec_enabled,
    resolve_pipeline_mode,
    skipped_spec_result,
)
from spec_integration.spec_prompts import (  # noqa: E402
    build_baseline_patch_generation_prompt,
    build_baseline_react_prompt_template,
    build_patch_generation_prompt,
    build_react_prompt_template,
)


def main() -> int:
    failed = 0
    print("Step 3 pipeline mode wiring check")

    sig = inspect.signature(__import__("reinfix_pipeline", fromlist=["run_single_bug"]).run_single_bug)
    if "pipeline_mode" not in sig.parameters:
        print("[FAIL] run_single_bug missing pipeline_mode parameter")
        failed += 1
    else:
        print("[OK] run_single_bug accepts pipeline_mode")

    for mode, expected_backend, spec_on in (
        ("baseline", "reinfix", False),
        ("spec", "reinfix+spec", True),
    ):
        resolved = resolve_pipeline_mode(cli_mode=mode)
        if backend_name(resolved) != expected_backend:
            print("[FAIL] backend_name({}) != {}".format(mode, expected_backend))
            failed += 1
        if is_spec_enabled(resolved) != spec_on:
            print("[FAIL] is_spec_enabled({}) != {}".format(mode, spec_on))
            failed += 1

    skipped = skipped_spec_result(max_attempts=3)
    if not skipped.get("skipped") or skipped.get("spec_final_verdict") != "SKIPPED":
        print("[FAIL] skipped_spec_result shape")
        failed += 1
    else:
        print("[OK] skipped_spec_result placeholder")

    if build_baseline_react_prompt_template() and build_react_prompt_template():
        print("[OK] baseline and spec ReAct templates importable")
    else:
        print("[FAIL] prompt templates")
        failed += 1

    baseline_patch = build_baseline_patch_generation_prompt(
        ["buggy_id: Chart-1_buggy"],
        "rc",
        "sugg",
    )
    spec_patch = build_patch_generation_prompt(
        "sample spec",
        ["buggy_id: Chart-1_buggy", "behavioral_spec: sample spec"],
        "rc",
        "sugg",
    )
    if "Verified Behavioral Spec" in baseline_patch:
        print("[FAIL] baseline patch prompt contains spec header")
        failed += 1
    elif "Verified Behavioral Spec" not in spec_patch:
        print("[FAIL] spec patch prompt missing spec header")
        failed += 1
    else:
        print("[OK] patch prompt builders differ by mode")

    if failed:
        print("\n{} check(s) failed.".format(failed))
        return 1
    print("\nStep 3 wiring checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
