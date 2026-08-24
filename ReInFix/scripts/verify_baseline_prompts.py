#!/usr/bin/env python3
"""Verify baseline prompts exclude behavioral spec (Step 1)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from spec_integration.spec_adapter import joern_project_name, load_dataset_entry, parse_bug_id  # noqa: E402
from spec_integration.spec_prompts import (  # noqa: E402
    build_baseline_patch_context_lines,
    build_baseline_patch_generation_prompt,
    render_baseline_react_prompt,
    verify_baseline_patch_prompt_excludes_spec,
    verify_baseline_react_prompt_excludes_spec,
    verify_patch_prompt_contains_spec,
    verify_react_prompt_contains_spec,
)


def main() -> int:
    bug = (sys.argv[1:2] or ["Chart-1"])[0]
    sample_spec = (
        "## Behavioral Spec (sample)\n"
        "When input is null, return an empty collection instead of null."
    )

    entry = load_dataset_entry(bug)
    project, bug_index = parse_bug_id(bug)
    joern_id = joern_project_name(project, bug_index)

    react_prompt = render_baseline_react_prompt(
        entry,
        joern_id,
        tool_descriptions="1. open_proj_tool\n",
        tool_names="1. open_proj_tool\n",
        trigger_src="[]",
        err_msg="[]",
    )
    patch_ctx = build_baseline_patch_context_lines(bug, entry, joern_id, "[]", "[]")
    patch_prompt = build_baseline_patch_generation_prompt(
        patch_ctx,
        "Null return causes NPE",
        "Suggestion 1: return empty list when input is null",
    )

    baseline_react_ok = verify_baseline_react_prompt_excludes_spec(react_prompt)
    baseline_patch_ok = verify_baseline_patch_prompt_excludes_spec(patch_prompt)
    spec_still_in_baseline = verify_react_prompt_contains_spec(react_prompt, sample_spec)

    print("Step 1 baseline prompt check (bug={})".format(bug))
    print(
        "[{}] baseline ReAct excludes spec".format("OK" if baseline_react_ok else "FAIL")
    )
    print(
        "[{}] baseline patch excludes spec".format("OK" if baseline_patch_ok else "FAIL")
    )
    print(
        "[{}] baseline ReAct does not contain sample spec text".format(
            "OK" if not spec_still_in_baseline else "FAIL"
        )
    )

    if "behavioral_spec" in "\n".join(patch_ctx).lower():
        print("[FAIL] baseline patch context contains behavioral_spec")
        return 1

    if baseline_react_ok and baseline_patch_ok and not spec_still_in_baseline:
        print("\nBaseline prompts look correct (no spec injection).")
        return 0

    print("\nBaseline prompt verification failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
