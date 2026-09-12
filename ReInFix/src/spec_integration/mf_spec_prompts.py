"""Step 3 — inject verified behavioral spec into multi-function ReInFix prompts."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from spec_integration.mf_localization import (
    format_mf_functions_block,
    mf_function_count,
    mf_primary_file_path,
)
from spec_integration.spec_prompts import (
    PATCH_SPEC_HEADER,
    PATCH_SPEC_MARKER,
    REACT_SPEC_HEADER,
    REACT_SPEC_MARKER,
    format_spec_section,
)

if TYPE_CHECKING:
    from langchain_core.prompts import PromptTemplate


REACT_PROMPT_TEMPLATE = """
You are an expert Java programmer and code analyzer. Your task is to analyze buggy Java code spanning multiple functions, identify the root cause of a bug, and provide repair suggestions.

{react_spec_header}
{spec_section}

## Available Tools
You have access to the following Joern-based tools and one Example Patch Search tool:
{tools}
{tool_names}

for each tool call:
  "tool": "Tool to be called from tools, if applicable. Set to 'None' if no tool is needed.",
  "parameters": "The input parameter(s) used by the tools."

- IMPORTANT: Do not modify tool parameters in any way.

## Analysis Process
1. Open the CPG for the buggy code (always required as first stage)
2. Analyze all buggy functions below, focusing on areas marked with /* bug is here */
3. Use tools to gather necessary information across related functions
4. Synthesize gathered information
5. Close the project before outputting the Summary Answer
6. Output the Summary Answer, optionally using example_patch_search_tool
7. Output the Final Answer

## Input Context
- Buggy ID(proj_name): {buggy_id}
- Buggy file(s): {buggy_file_path}
- Number of functions to repair: {function_count}

{buggy_functions_block}

- Trigger Test: {trigger_src}
- Error Message: {err_msg}

## Output Format
Thought: ...
Action: ...
Action Input: ...
Observation: ...
Final Answer:
Root Cause: ...
Suggestion 1: ...
Suggestion 2: ...

Thought: {agent_scratchpad}
"""

BASELINE_REACT_PROMPT_TEMPLATE = """
You are an expert Java programmer and code analyzer. Your task is to analyze buggy Java code spanning multiple functions, identify the root cause of a bug, and provide repair suggestions.

## Available Tools
You have access to the following Joern-based tools and one Example Patch Search tool:
{tools}
{tool_names}

for each tool call:
  "tool": "Tool to be called from tools, if applicable. Set to 'None' if no tool is needed.",
  "parameters": "The input parameter(s) used by the tools."

- IMPORTANT: Do not modify tool parameters in any way.

## Analysis Process
1. Open the CPG for the buggy code (always required as first stage)
2. Analyze all buggy functions below, focusing on areas marked with /* bug is here */
3. Use tools to gather necessary information across related functions
4. Synthesize gathered information
5. Close the project before outputting the Summary Answer
6. Output the Summary Answer, optionally using example_patch_search_tool
7. Output the Final Answer

## Input Context
- Buggy ID(proj_name): {buggy_id}
- Buggy file(s): {buggy_file_path}
- Number of functions to repair: {function_count}

{buggy_functions_block}

- Trigger Test: {trigger_src}
- Error Message: {err_msg}

## Output Format
Thought: ...
Action: ...
Action Input: ...
Observation: ...
Final Answer:
Root Cause: ...
Suggestion 1: ...
Suggestion 2: ...

Thought: {agent_scratchpad}
"""


def build_react_prompt_template() -> PromptTemplate:
    from langchain_core.prompts import PromptTemplate

    return PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)


def build_baseline_react_prompt_template() -> PromptTemplate:
    from langchain_core.prompts import PromptTemplate

    return PromptTemplate.from_template(BASELINE_REACT_PROMPT_TEMPLATE)


def _shared_react_fields(
    entry: dict[str, Any],
    joern_project_name: str,
    tool_descriptions: str,
    tool_names: str,
    trigger_src: str,
    err_msg: str,
) -> dict[str, str]:
    return {
        "tools": tool_descriptions,
        "tool_names": tool_names,
        "buggy_id": joern_project_name,
        "buggy_file_path": mf_primary_file_path(entry),
        "function_count": str(mf_function_count(entry)),
        "buggy_functions_block": format_mf_functions_block(entry),
        "trigger_src": trigger_src,
        "err_msg": err_msg,
    }


def react_prompt_kwargs(
    spec_section: str,
    entry: dict[str, Any],
    joern_project_name: str,
    tool_descriptions: str,
    tool_names: str,
    trigger_src: str,
    err_msg: str,
) -> dict[str, str]:
    return {
        "react_spec_header": REACT_SPEC_HEADER,
        "spec_section": format_spec_section(spec_section),
        **_shared_react_fields(
            entry, joern_project_name, tool_descriptions, tool_names, trigger_src, err_msg
        ),
    }


def baseline_react_prompt_kwargs(
    entry: dict[str, Any],
    joern_project_name: str,
    tool_descriptions: str,
    tool_names: str,
    trigger_src: str,
    err_msg: str,
) -> dict[str, str]:
    return _shared_react_fields(
        entry, joern_project_name, tool_descriptions, tool_names, trigger_src, err_msg
    )


def build_patch_context_lines(
    bug_name: str,
    entry: dict[str, Any],
    joern_project_name: str,
    trigger_src: str,
    err_msg: str,
    spec_section: str,
) -> list[str]:
    return [
        "buggy_id: " + joern_project_name,
        "buggy_name: " + bug_name,
        "repair_scenario: MF",
        "function_count: " + str(mf_function_count(entry)),
        "buggy_file_path: " + mf_primary_file_path(entry),
        "buggy_functions: " + format_mf_functions_block(entry, include_markers=False),
        "trigger_src: " + trigger_src,
        "err_msg: " + err_msg,
        "behavioral_spec: " + format_spec_section(spec_section),
    ]


def build_baseline_patch_context_lines(
    bug_name: str,
    entry: dict[str, Any],
    joern_project_name: str,
    trigger_src: str,
    err_msg: str,
) -> list[str]:
    return [
        "buggy_id: " + joern_project_name,
        "buggy_name: " + bug_name,
        "repair_scenario: MF",
        "function_count: " + str(mf_function_count(entry)),
        "buggy_file_path: " + mf_primary_file_path(entry),
        "buggy_functions: " + format_mf_functions_block(entry, include_markers=False),
        "trigger_src: " + trigger_src,
        "err_msg: " + err_msg,
    ]


def _mf_patch_format_instructions(function_count: int) -> str:
    lines = [
        "Generate ONE complete multi-function fix covering all {} functions.".format(
            function_count
        ),
        "Output each fixed function in order using this format:",
    ]
    for idx in range(1, function_count + 1):
        lines.append(
            "[START PATCH {i}]\n```java\n<full function {i}>\n```\n[END PATCH {i}]".format(
                i=idx
            )
        )
    return "\n".join(lines)


def build_patch_generation_prompt(
    spec_section: str,
    context_lines: list[str],
    root_cause: str,
    suggestion: str,
    function_count: int,
) -> str:
    return (
        "You are an expert Java programmer generating multi-function patches.\n"
        "Bug context:\n{ctx}\n\n"
        "{patch_spec_header}:\n{spec}\n\n"
        "Root Cause: {rc}\n{sugg}\n\n"
        "Follow the verified behavioral spec when generating the fix.\n"
        "{format_instructions}\n"
    ).format(
        ctx="\n".join(context_lines),
        patch_spec_header=PATCH_SPEC_HEADER,
        spec=format_spec_section(spec_section),
        rc=str(root_cause).strip(),
        sugg=str(suggestion).strip(),
        format_instructions=_mf_patch_format_instructions(function_count),
    )


def build_baseline_patch_generation_prompt(
    context_lines: list[str],
    root_cause: str,
    suggestion: str,
    function_count: int,
) -> str:
    return (
        "You are an expert Java programmer generating multi-function patches.\n"
        "Bug context:\n{ctx}\n\n"
        "Root Cause: {rc}\n{sugg}\n\n"
        "{format_instructions}\n"
    ).format(
        ctx="\n".join(context_lines),
        rc=str(root_cause).strip(),
        sugg=str(suggestion).strip(),
        format_instructions=_mf_patch_format_instructions(function_count),
    )


def verify_react_prompt_contains_spec(prompt_text: str, spec_section: str) -> bool:
    text = (prompt_text or "").strip()
    spec = format_spec_section(spec_section)
    return REACT_SPEC_MARKER in text and spec in text


def verify_patch_prompt_contains_spec(prompt_text: str, spec_section: str) -> bool:
    text = (prompt_text or "").strip()
    spec = format_spec_section(spec_section)
    return PATCH_SPEC_MARKER in text and spec in text and PATCH_SPEC_HEADER in text


def verify_baseline_react_prompt_excludes_spec(prompt_text: str) -> bool:
    text = (prompt_text or "").strip()
    return REACT_SPEC_MARKER not in text and "behavioral_spec" not in text.lower()


def verify_baseline_patch_prompt_excludes_spec(prompt_text: str) -> bool:
    text = (prompt_text or "").strip()
    lowered = text.lower()
    return (
        PATCH_SPEC_HEADER not in text
        and PATCH_SPEC_MARKER not in text
        and "behavioral_spec" not in lowered
        and "verified behavioral spec" not in lowered
    )
