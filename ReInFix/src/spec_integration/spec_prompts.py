"""Step 3 — inject verified behavioral spec into ReInFix prompts.

Two injection points:
1. Joern ReAct analysis (``build_react_prompt_template`` / ``react_prompt_kwargs``)
2. Patch generation (``build_patch_generation_prompt``)
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.prompts import PromptTemplate


REACT_SPEC_HEADER = (
    "## Verified Behavioral Spec (follow this plan during analysis and suggestions)"
)
PATCH_SPEC_HEADER = "## Verified Behavioral Spec"
REACT_SPEC_MARKER = "Verified Behavioral Spec"
PATCH_SPEC_MARKER = "Follow the verified behavioral spec"


def format_spec_section(spec_section: str) -> str:
    text = (spec_section or "").strip()
    if not text:
        return "(No verified behavioral spec available.)"
    return text


REACT_PROMPT_TEMPLATE = """
You are an expert Java programmer and code analyzer. Your task is to analyze a given Java code snippet, identify the root cause of a bug, and provide repair suggestions.

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
2. Analyze the buggy code, focusing on the area marked with /* bug is here */
3. Use tools to gather necessary information
4. Synthesize gathered information
5. Close the project before outputting the Summary Answer
6. Output the Summary Answer, optionally using example_patch_search_tool
7. Output the Final Answer

## Input Context
- Buggy ID(proj_name): {buggy_id}
- Buggy File: {buggy_file_path}
- Buggy Function:
```java
{buggy_code}
```
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
You are an expert Java programmer and code analyzer. Your task is to analyze a given Java code snippet, identify the root cause of a bug, and provide repair suggestions.

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
2. Analyze the buggy code, focusing on the area marked with /* bug is here */
3. Use tools to gather necessary information
4. Synthesize gathered information
5. Close the project before outputting the Summary Answer
6. Output the Summary Answer, optionally using example_patch_search_tool
7. Output the Final Answer

## Input Context
- Buggy ID(proj_name): {buggy_id}
- Buggy File: {buggy_file_path}
- Buggy Function:
```java
{buggy_code}
```
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
    """Injection point 1: ReAct agent system prompt (spec-enabled)."""
    from langchain_core.prompts import PromptTemplate

    return PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)


def build_baseline_react_prompt_template() -> PromptTemplate:
    """Original ReInFix ReAct prompt (no behavioral spec)."""
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
        "buggy_file_path": entry.get("loc") or "",
        "buggy_code": entry.get("buggy_fl") or entry.get("buggy") or "",
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
    """Keyword args for ``build_react_prompt_template().partial(...)``."""
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
    """Keyword args for ``build_baseline_react_prompt_template().partial(...)``."""
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
    """Context lines shared across patch-generation calls."""
    buggy_code = entry.get("buggy_fl") or entry.get("buggy") or ""
    return [
        "buggy_id: " + joern_project_name,
        "buggy_name: " + bug_name,
        "buggy_code: " + buggy_code,
        "buggy_file_path: " + (entry.get("loc") or ""),
        "trigger_src: " + trigger_src,
        "err_msg: " + err_msg,
        "behavioral_spec: " + format_spec_section(spec_section),
    ]


def build_patch_generation_prompt(
    spec_section: str,
    context_lines: list[str],
    root_cause: str,
    suggestion: str,
) -> str:
    """Injection point 2: patch generation user prompt (spec-enabled)."""
    return (
        "You are an expert Java programmer generating patches.\n"
        "Bug context:\n{ctx}\n\n"
        "{patch_spec_header}:\n{spec}\n\n"
        "Root Cause: {rc}\n{sugg}\n\n"
        "Follow the verified behavioral spec when generating the fix.\n"
        "Generate ONE complete fixed function. Format:\n"
        "[START PATCH 1]\n```java\n<full function>\n```\n[END PATCH 1]\n"
    ).format(
        ctx="\n".join(context_lines),
        patch_spec_header=PATCH_SPEC_HEADER,
        spec=format_spec_section(spec_section),
        rc=str(root_cause).strip(),
        sugg=str(suggestion).strip(),
    )


def build_baseline_patch_context_lines(
    bug_name: str,
    entry: dict[str, Any],
    joern_project_name: str,
    trigger_src: str,
    err_msg: str,
) -> list[str]:
    """Patch context for original ReInFix (no behavioral spec)."""
    buggy_code = entry.get("buggy_fl") or entry.get("buggy") or ""
    return [
        "buggy_id: " + joern_project_name,
        "buggy_name: " + bug_name,
        "buggy_code: " + buggy_code,
        "buggy_file_path: " + (entry.get("loc") or ""),
        "trigger_src: " + trigger_src,
        "err_msg: " + err_msg,
    ]


def build_baseline_patch_generation_prompt(
    context_lines: list[str],
    root_cause: str,
    suggestion: str,
) -> str:
    """Original ReInFix patch prompt (no spec injection)."""
    return (
        "You are an expert Java programmer generating patches.\n"
        "Bug context:\n{ctx}\n\n"
        "Root Cause: {rc}\n{sugg}\n\n"
        "Generate ONE complete fixed function. Format:\n"
        "[START PATCH 1]\n```java\n<full function>\n```\n[END PATCH 1]\n"
    ).format(
        ctx="\n".join(context_lines),
        rc=str(root_cause).strip(),
        sugg=str(suggestion).strip(),
    )


def render_react_prompt(
    spec_section: str,
    entry: dict[str, Any],
    joern_project_name: str,
    tool_descriptions: str,
    tool_names: str,
    trigger_src: str,
    err_msg: str,
    agent_scratchpad: str = "",
) -> str:
    """Render injection point 1 for tests / debugging (no LangChain required)."""
    kwargs = react_prompt_kwargs(
        spec_section,
        entry,
        joern_project_name,
        tool_descriptions,
        tool_names,
        trigger_src,
        err_msg,
    )
    kwargs["agent_scratchpad"] = agent_scratchpad
    return REACT_PROMPT_TEMPLATE.format(**kwargs)


def render_baseline_react_prompt(
    entry: dict[str, Any],
    joern_project_name: str,
    tool_descriptions: str,
    tool_names: str,
    trigger_src: str,
    err_msg: str,
    agent_scratchpad: str = "",
) -> str:
    """Render baseline ReAct prompt for tests / debugging."""
    kwargs = baseline_react_prompt_kwargs(
        entry,
        joern_project_name,
        tool_descriptions,
        tool_names,
        trigger_src,
        err_msg,
    )
    kwargs["agent_scratchpad"] = agent_scratchpad
    return BASELINE_REACT_PROMPT_TEMPLATE.format(**kwargs)


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


def save_prompt_section_artifact(
    exp_dir: str,
    bug_name: str,
    spec_section: str,
) -> str:
    """Persist verified spec text used for Step 3 injection."""
    from pathlib import Path

    safe = bug_name.replace("-", "_")
    out_dir = Path(exp_dir) / "spec_artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "prompt_section_{}.txt".format(safe)
    path.write_text(format_spec_section(spec_section), encoding="utf-8")
    return str(path)


def save_injection_prompt_artifacts(
    exp_dir: str,
    bug_name: str,
    react_prompt: str,
    patch_prompt_sample: str,
) -> dict[str, str]:
    """Persist rendered ReAct / patch prompts (Step 3 injection audit trail)."""
    from pathlib import Path

    safe = bug_name.replace("-", "_")
    out_dir = Path(exp_dir) / "spec_artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    react_path = out_dir / "react_prompt_{}.txt".format(safe)
    patch_path = out_dir / "patch_prompt_sample_{}.txt".format(safe)
    react_path.write_text(react_prompt, encoding="utf-8")
    patch_path.write_text(patch_prompt_sample, encoding="utf-8")
    return {
        "react_prompt": str(react_path),
        "patch_prompt_sample": str(patch_path),
    }
