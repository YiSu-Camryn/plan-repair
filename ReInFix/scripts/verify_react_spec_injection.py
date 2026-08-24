#!/usr/bin/env python3
"""Verify Joern ReAct prompt includes verified spec (injection point 1, no LLM)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from spec_integration.spec_adapter import joern_project_name, load_dataset_entry, parse_bug_id  # noqa: E402
from spec_integration.spec_prompts import (  # noqa: E402
    render_react_prompt,
    verify_react_prompt_contains_spec,
)


def main() -> int:
    bug = (sys.argv[1:2] or ["Chart-1"])[0]
    sample_spec = (
        "## Behavioral Spec (sample)\n"
        "When input is null, the method must return an empty collection instead of null.\n"
        "Do not change public API signatures."
    )

    entry = load_dataset_entry(bug)
    project, bug_index = parse_bug_id(bug)
    joern_id = joern_project_name(project, bug_index)

    react_prompt = render_react_prompt(
        sample_spec,
        entry,
        joern_id,
        tool_descriptions="1. open_proj_tool — open Joern project\n",
        tool_names="1. open_proj_tool\n",
        trigger_src="[]",
        err_msg="[]",
    )

    ok = verify_react_prompt_contains_spec(react_prompt, sample_spec)
    print("Joern ReAct spec injection check (bug={})".format(bug))
    print("[{}] ReAct prompt includes verified spec".format("OK" if ok else "FAIL"))
    print("Joern project id in prompt: {}".format(joern_id in react_prompt))

    if ok and joern_id in react_prompt:
        print("\nReAct injection point 1 OK.")
        return 0

    print("\nReAct injection verification failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
