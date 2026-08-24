#!/usr/bin/env python3
"""Step 3 check: verified spec appears in ReAct and patch prompts (no LLM)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from spec_integration.spec_adapter import (  # noqa: E402
    joern_project_name,
    load_dataset_entry,
    parse_bug_id,
)
from spec_integration.spec_prompts import (  # noqa: E402
    build_patch_context_lines,
    build_patch_generation_prompt,
    render_react_prompt,
    verify_patch_prompt_contains_spec,
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
        tool_descriptions="1. open_proj_tool\n",
        tool_names="1. open_proj_tool\n",
        trigger_src="[]",
        err_msg="[]",
    )
    patch_ctx = build_patch_context_lines(
        bug, entry, joern_id, "[]", "[]", sample_spec
    )
    patch_prompt = build_patch_generation_prompt(
        sample_spec,
        patch_ctx,
        "Null return causes NPE in caller",
        "Suggestion 1: return Collections.emptyList() when input is null",
    )

    react_ok = verify_react_prompt_contains_spec(react_prompt, sample_spec)
    patch_ok = verify_patch_prompt_contains_spec(patch_prompt, sample_spec)

    print("Step 3 spec injection check (bug={})".format(bug))
    print("[{}] ReAct prompt (injection point 1)".format("OK" if react_ok else "FAIL"))
    print("[{}] Patch prompt (injection point 2)".format("OK" if patch_ok else "FAIL"))

    if react_ok and patch_ok:
        print("\nBoth injection points include the verified behavioral spec.")
        return 0

    print("\nSpec injection verification failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
