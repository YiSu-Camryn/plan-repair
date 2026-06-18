"""Independent ablation study

Five spec injection conditions (``hyperparams_ablation.json`` → ``spec_level``):

- ``none``  (A0): no spec injection — baseline RepairAgent
- ``short`` (A1): purpose + test_expectation (~100 tokens)
- ``core``  (A2): short + code_violations + fix_targets (~250 tokens)
- ``full``  (A3): E34-style — all diagnostic fields (~600 tokens)
- ``e39``   (A4): full + fix_direction, confidence, ACTION tweaks

Usage (instead of ``./run.sh``)::

    ./run_ablation.sh --ai-settings ai_settings.yaml \\
        --experiment-file hyperparams_ablation.json \\
        --model gpt-4o-mini -c -l 40 -m json_file

Batch::

    ./run_on_ablation_defects4j.sh experimental_setups/pilot_bugs_list \\
        hyperparams_ablation.json gpt-4o-mini
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional, TYPE_CHECKING

from autogpt.logs import logger

if TYPE_CHECKING:
    from autogpt.config import AIConfig, Config
    from autogpt.memory.vector import VectorMemory
    from autogpt.models.command_registry import CommandRegistry

from autogpt.agents.agent import Agent

SPEC_LEVEL_NONE = "none"
SPEC_LEVEL_SHORT = "short"
SPEC_LEVEL_CORE = "core"
SPEC_LEVEL_FULL = "full"
SPEC_LEVEL_E39 = "e39"

SPEC_LEVELS = (
    SPEC_LEVEL_NONE,
    SPEC_LEVEL_SHORT,
    SPEC_LEVEL_CORE,
    SPEC_LEVEL_FULL,
    SPEC_LEVEL_E39,
)

SPEC_LEVEL_ALIASES = {
    "a0": SPEC_LEVEL_NONE,
    "a1": SPEC_LEVEL_SHORT,
    "a2": SPEC_LEVEL_CORE,
    "a3": SPEC_LEVEL_FULL,
    "a4": SPEC_LEVEL_E39,
    "no_spec": SPEC_LEVEL_NONE,
    "minimal": SPEC_LEVEL_SHORT,
}

DEFAULT_SPEC_LEVEL = SPEC_LEVEL_E39

SPEC_HEADER = "## Behavioral Specification of Buggy Method\n\n"

_FOOTER_IMPORTANT = (
    "**IMPORTANT:** This specification describes WHAT is wrong, not HOW to fix it. "
    "Use the code_violations and fix targets above to understand the problem, "
    "then determine the fix approach yourself based on the code."
)
_FOOTER_CRITICAL = (
    "**CRITICAL:** Do NOT add trailing comments (// ...) to modified or inserted lines. "
    "Write CLEAN code only — comments can cause write_fix to fail."
)
_FOOTER_ANTI_OVERFITTING = (
    "**ANTI-OVERFITTING:** The fix must work for arbitrary inputs, not just the specific "
    "test values. Never hardcode expected outputs or special-case the exact inputs from "
    "the failing test."
)


def resolve_spec_level(hyperparams: Optional[dict]) -> str:
    """Read and normalize ``spec_level`` from ablation hyperparams."""
    if not hyperparams:
        return DEFAULT_SPEC_LEVEL

    level = hyperparams.get("spec_level", DEFAULT_SPEC_LEVEL)
    normalized = str(level).lower().strip()
    if normalized in SPEC_LEVEL_ALIASES:
        return SPEC_LEVEL_ALIASES[normalized]
    if normalized in SPEC_LEVELS:
        return normalized

    logger.warning(
        "ABLATION: Unknown spec_level {!r}, defaulting to {!r}".format(
            level, DEFAULT_SPEC_LEVEL
        )
    )
    return DEFAULT_SPEC_LEVEL


def load_ablation_hyperparams(experiment_file: str) -> dict:
    with open(experiment_file) as f:
        return json.load(f)


def format_spec_for_prompt_by_level(
    spec_json: Optional[dict],
    raw_text: str,
    level: str,
) -> str:
    """Render spec JSON into a prompt section for the given ablation level."""
    if level == SPEC_LEVEL_NONE:
        return ""

    if not spec_json or not isinstance(spec_json, dict):
        return SPEC_HEADER + str(raw_text)[:2000]

    parts = [SPEC_HEADER]

    if spec_json.get("purpose"):
        parts.append("**Purpose:** {}\n".format(spec_json["purpose"]))

    if level in (SPEC_LEVEL_FULL, SPEC_LEVEL_E39) and spec_json.get("javadoc_key_rules"):
        parts.append("**Javadoc Rules:**")
        for i, rule in enumerate(spec_json["javadoc_key_rules"], 1):
            parts.append("  {}. {}".format(i, rule))
        parts.append("")

    if level in (SPEC_LEVEL_CORE, SPEC_LEVEL_FULL, SPEC_LEVEL_E39) and spec_json.get(
        "code_violations"
    ):
        parts.append("**Code Violations (what's wrong):**")
        for i, violation in enumerate(spec_json["code_violations"], 1):
            parts.append("  {}. {}".format(i, violation))
        parts.append("")

    if spec_json.get("test_expectation"):
        parts.append("**What the tests expect:** {}\n".format(spec_json["test_expectation"]))

    if level in (SPEC_LEVEL_FULL, SPEC_LEVEL_E39) and spec_json.get("rules"):
        parts.append("**Behavioral rules the correct implementation must satisfy:**")
        for i, rule in enumerate(spec_json["rules"], 1):
            parts.append("  {}. {}".format(i, rule))
        parts.append("")

    if level in (SPEC_LEVEL_FULL, SPEC_LEVEL_E39) and spec_json.get("fix_target_line"):
        parts.append("**Fix target line:** {}\n".format(spec_json["fix_target_line"]))

    if level in (SPEC_LEVEL_CORE, SPEC_LEVEL_FULL, SPEC_LEVEL_E39) and spec_json.get(
        "fix_targets"
    ):
        parts.append("**Fix targets:**")
        for i, target in enumerate(spec_json["fix_targets"], 1):
            parts.append(
                "  {}. Line {}: {}".format(
                    i, target.get("line", "?"), target.get("description", "")
                )
            )
        parts.append("")

    if level == SPEC_LEVEL_E39 and spec_json.get("fix_direction"):
        parts.append("**Fix direction:** {}\n".format(spec_json["fix_direction"]))
        if spec_json["fix_direction"] == "DELETE_CODE":
            parts.append(
                "**ACTION:** The fix requires REMOVING existing code. Use the `deletions` "
                "field in write_fix to delete the buggy lines. If replacement code is "
                "needed, use `insertions` after deleting.\n"
            )
        elif spec_json["fix_direction"] == "SIMPLIFY":
            parts.append(
                "**ACTION:** The fix requires SIMPLIFYING existing code. Consider deleting "
                "unnecessary guards, branches, or logic rather than adding new code.\n"
            )

    if level == SPEC_LEVEL_E39 and spec_json.get("confidence"):
        parts.append("**Diagnosis confidence:** {}\n".format(spec_json["confidence"]))

    if level == SPEC_LEVEL_E39 and spec_json.get("developer_clarification"):
        parts.append(
            "**Developer clarification:** {}\n".format(spec_json["developer_clarification"])
        )

    if level in (SPEC_LEVEL_FULL, SPEC_LEVEL_E39):
        parts.append(_FOOTER_IMPORTANT)
        parts.append(_FOOTER_CRITICAL)

    if level == SPEC_LEVEL_E39:
        parts.append(_FOOTER_ANTI_OVERFITTING)

    return "\n".join(parts)


def _make_patched_generate_spec(
    original: Callable[..., dict],
    level: str,
) -> Callable[..., dict]:
    if level == SPEC_LEVEL_NONE:

        def skip_generate_spec(*_args, **_kwargs) -> dict:
            logger.info("ABLATION: spec_level=none — skipping spec generation and injection")
            return {
                "success": True,
                "spec_json": None,
                "prompt_section": "",
                "error": None,
            }

        return skip_generate_spec

    def ablation_generate_spec(*args, **kwargs) -> dict:
        result = original(*args, **kwargs)
        if not result.get("success"):
            return result

        project_name = args[0] if args else kwargs.get("project_name")
        bug_index = args[1] if len(args) > 1 else kwargs.get("bug_index")
        spec_json = result.get("spec_json")
        raw_text = result.get("prompt_section") or ""
        prompt_section = format_spec_for_prompt_by_level(spec_json, raw_text, level)
        result["prompt_section"] = prompt_section

        if prompt_section.strip():
            from autogpt.commands.spec_generator import _save_spec_log

            logger.info(
                "ABLATION: Injected level={} ({} chars)".format(level, len(prompt_section))
            )
            _save_spec_log(
                project_name,
                bug_index,
                "ablation_injected_{}".format(level),
                prompt_section,
            )

        return result

    return ablation_generate_spec


@contextmanager
def patch_generate_spec_for_level(level: str) -> Iterator[None]:
    """Temporarily replace ``generate_spec`` while ``BaseAgent.__init__`` runs."""
    import autogpt.commands.spec_generator as spec_generator

    original = spec_generator.generate_spec
    spec_generator.generate_spec = _make_patched_generate_spec(original, level)
    try:
        yield
    finally:
        spec_generator.generate_spec = original


class AblationAgent(Agent):
    """RepairAgent variant for spec ablation — only used via ``run_ablation.sh``."""

    def __init__(
        self,
        ai_config: AIConfig,
        command_registry: CommandRegistry,
        memory: VectorMemory,
        triggering_prompt: str,
        config: Config,
        cycle_budget: Optional[int] = None,
        experiment_file: str = None,
    ):
        hyperparams = load_ablation_hyperparams(experiment_file)
        self.spec_level = resolve_spec_level(hyperparams)

        logger.info("ABLATION: Using AblationAgent with spec_level={}".format(self.spec_level))

        with patch_generate_spec_for_level(self.spec_level):
            super().__init__(
                ai_config=ai_config,
                command_registry=command_registry,
                memory=memory,
                triggering_prompt=triggering_prompt,
                config=config,
                cycle_budget=cycle_budget,
                experiment_file=experiment_file,
            )

        if "spec_section" in self.prompt_dictionary:
            self.prompt_dictionary["spec_ablation_level"] = self.spec_level


def run_ablation_auto_gpt(*args, **kwargs):
    """Same as ``run_auto_gpt`` but instantiates ``AblationAgent`` instead of ``Agent``."""
    import autogpt.app.main as main_module

    original_agent = main_module.Agent
    main_module.Agent = AblationAgent
    try:
        from autogpt.app.main import run_auto_gpt

        run_auto_gpt(*args, **kwargs)
    finally:
        main_module.Agent = original_agent
