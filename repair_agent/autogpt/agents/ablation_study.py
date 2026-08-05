"""Independent ablation study

Six spec conditions (``hyperparams_ablation.json`` → ``spec_level``):

- ``none`` (A0): no spec injection — baseline RepairAgent
- ``no_javadoc`` (A1): full E39-style spec minus Javadoc-derived fields
- ``no_failed_tests`` (A2): full spec minus failing-test information
- ``no_code_analysis`` (A3): full spec minus static code-analysis fields
- ``no_fix_direction`` (A4): full spec minus fix_direction / ACTION labels
- ``raw_context`` (A5): raw gathered bug context — no spec LLM, no verification

Each of A1–A4 is a leave-one-out ablation from the full spec pipeline (E39-style
generation + injection). The complete spec is the default non-ablation path
(``hyperparams.json`` + standard ``Agent``).

Optional verifier ablation (``use_spec_verifier``):

- ``true`` (default): run ``verify_spec`` and regenerate on REJECT
- ``false``: skip spec verification (same spec JSON from first LLM call)

Optional self-clarification ablation (``use_self_clarification``):

- ``true`` (default): when ``confidence`` is LOW, answer ``clarifying_question`` via LLM
- ``false``: skip Phase 4c; no ``developer_clarification`` field added

Usage (instead of ``./run.sh``)::

    ./run_ablation.sh --ai-settings ai_settings.yaml \\
        --experiment-file hyperparams_ablation.json \\
        --model gpt-4o-mini -c -l 40 -m json_file

Batch::

    ./run_on_ablation_defects4j.sh experimental_setups/pilot_bugs_list \\
        hyperparams_ablation.json gpt-4o-mini
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional, TYPE_CHECKING

from autogpt.logs import logger

if TYPE_CHECKING:
    from autogpt.config import AIConfig, Config
    from autogpt.memory.vector import VectorMemory
    from autogpt.models.command_registry import CommandRegistry

from autogpt.agents.agent import Agent

SPEC_LEVEL_NONE = "none"
SPEC_LEVEL_NO_JAVADOC = "no_javadoc"
SPEC_LEVEL_NO_FAILED_TESTS = "no_failed_tests"
SPEC_LEVEL_NO_CODE_ANALYSIS = "no_code_analysis"
SPEC_LEVEL_NO_FIX_DIRECTION = "no_fix_direction"
SPEC_LEVEL_RAW_CONTEXT = "raw_context"

SPEC_LEVELS = (
    SPEC_LEVEL_NONE,
    SPEC_LEVEL_NO_JAVADOC,
    SPEC_LEVEL_NO_FAILED_TESTS,
    SPEC_LEVEL_NO_CODE_ANALYSIS,
    SPEC_LEVEL_NO_FIX_DIRECTION,
    SPEC_LEVEL_RAW_CONTEXT,
)

LEAVE_ONE_OUT_SPEC_LEVELS = (
    SPEC_LEVEL_NO_JAVADOC,
    SPEC_LEVEL_NO_FAILED_TESTS,
    SPEC_LEVEL_NO_CODE_ANALYSIS,
    SPEC_LEVEL_NO_FIX_DIRECTION,
)

SPEC_LEVEL_ALIASES = {
    "a0": SPEC_LEVEL_NONE,
    "a1": SPEC_LEVEL_NO_JAVADOC,
    "a2": SPEC_LEVEL_NO_FAILED_TESTS,
    "a3": SPEC_LEVEL_NO_CODE_ANALYSIS,
    "a4": SPEC_LEVEL_NO_FIX_DIRECTION,
    "a5": SPEC_LEVEL_RAW_CONTEXT,
    "no_spec": SPEC_LEVEL_NONE,
    "concat": SPEC_LEVEL_RAW_CONTEXT,
    # Legacy names from the previous short/core/full/e39 ladder
    "short": SPEC_LEVEL_NO_CODE_ANALYSIS,
    "core": SPEC_LEVEL_NO_JAVADOC,
    "full": SPEC_LEVEL_NO_FIX_DIRECTION,
    "e39": SPEC_LEVEL_NO_JAVADOC,
    "minimal": SPEC_LEVEL_NO_CODE_ANALYSIS,
}

DEFAULT_SPEC_LEVEL = SPEC_LEVEL_NO_JAVADOC
DEFAULT_USE_SPEC_VERIFIER = True
DEFAULT_USE_SELF_CLARIFICATION = True

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


def is_leave_one_out_ablation_level(level: str) -> bool:
    return level in LEAVE_ONE_OUT_SPEC_LEVELS


def ablation_flags(level: str) -> dict[str, bool]:
    """Inclusion flags for the full E39-style spec. False = ablated away."""
    return {
        "include_javadoc": level != SPEC_LEVEL_NO_JAVADOC,
        "include_failed_tests": level != SPEC_LEVEL_NO_FAILED_TESTS,
        "include_code_analysis": level != SPEC_LEVEL_NO_CODE_ANALYSIS,
        "include_fix_direction": level != SPEC_LEVEL_NO_FIX_DIRECTION,
    }


def resolve_spec_level(hyperparams: Optional[dict]) -> str:
    """Read and normalize ``spec_level`` from ablation hyperparams."""
    if not hyperparams:
        return DEFAULT_SPEC_LEVEL

    level = hyperparams.get("spec_level", DEFAULT_SPEC_LEVEL)
    normalized = str(level).lower().strip()
    if normalized in SPEC_LEVEL_ALIASES:
        resolved = SPEC_LEVEL_ALIASES[normalized]
        if normalized in ("short", "core", "full", "e39", "minimal"):
            logger.warning(
                "ABLATION: Legacy spec_level {!r} mapped to {!r}".format(
                    level, resolved
                )
            )
        return resolved
    if normalized in SPEC_LEVELS:
        return normalized

    logger.warning(
        "ABLATION: Unknown spec_level {!r}, defaulting to {!r}".format(
            level, DEFAULT_SPEC_LEVEL
        )
    )
    return DEFAULT_SPEC_LEVEL


def _resolve_bool_hyperparam(
    hyperparams: Optional[dict],
    key: str,
    default: bool,
) -> bool:
    """Read a boolean flag from ablation hyperparams."""
    if not hyperparams or key not in hyperparams:
        return default

    value = hyperparams[key]
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.lower().strip()
        if normalized in ("false", "0", "no", "off"):
            return False
        if normalized in ("true", "1", "yes", "on"):
            return True
    if isinstance(value, (int, float)):
        return bool(value)

    logger.warning(
        "ABLATION: Unknown {} {!r}, defaulting to {!r}".format(key, value, default)
    )
    return default


def resolve_use_spec_verifier(hyperparams: Optional[dict]) -> bool:
    """Read ``use_spec_verifier`` from ablation hyperparams (default True)."""
    return _resolve_bool_hyperparam(
        hyperparams, "use_spec_verifier", DEFAULT_USE_SPEC_VERIFIER
    )


def resolve_use_self_clarification(hyperparams: Optional[dict]) -> bool:
    """Read ``use_self_clarification`` from ablation hyperparams (default True)."""
    return _resolve_bool_hyperparam(
        hyperparams, "use_self_clarification", DEFAULT_USE_SELF_CLARIFICATION
    )


def load_ablation_hyperparams(experiment_file: str) -> dict:
    from autogpt.config.hyperparams_loader import load_hyperparams

    return load_hyperparams(experiment_file)


def sanitize_spec_json_for_ablation(
    spec_json: Optional[dict],
    level: str,
) -> Optional[dict]:
    """Drop ablated fields from parsed spec JSON before prompt formatting."""
    if not spec_json or not isinstance(spec_json, dict):
        return spec_json
    if not is_leave_one_out_ablation_level(level):
        return spec_json

    flags = ablation_flags(level)
    sanitized = dict(spec_json)
    if not flags["include_javadoc"]:
        sanitized.pop("javadoc_key_rules", None)
    if not flags["include_failed_tests"]:
        sanitized.pop("test_expectation", None)
    if not flags["include_code_analysis"]:
        sanitized.pop("code_violations", None)
        sanitized.pop("fix_targets", None)
        sanitized.pop("fix_target_line", None)
    if not flags["include_fix_direction"]:
        sanitized.pop("fix_direction", None)
    return sanitized


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

    spec_json = sanitize_spec_json_for_ablation(spec_json, level)
    flags = ablation_flags(level) if is_leave_one_out_ablation_level(level) else {
        "include_javadoc": True,
        "include_failed_tests": True,
        "include_code_analysis": True,
        "include_fix_direction": True,
    }

    parts = [SPEC_HEADER]

    if spec_json.get("purpose"):
        parts.append("**Purpose:** {}\n".format(spec_json["purpose"]))

    if flags["include_javadoc"] and spec_json.get("javadoc_key_rules"):
        parts.append("**Javadoc Rules:**")
        for i, rule in enumerate(spec_json["javadoc_key_rules"], 1):
            parts.append("  {}. {}".format(i, rule))
        parts.append("")

    if flags["include_code_analysis"] and spec_json.get("code_violations"):
        parts.append("**Code Violations (what's wrong):**")
        for i, violation in enumerate(spec_json["code_violations"], 1):
            parts.append("  {}. {}".format(i, violation))
        parts.append("")

    if flags["include_failed_tests"] and spec_json.get("test_expectation"):
        parts.append("**What the tests expect:** {}\n".format(spec_json["test_expectation"]))

    if spec_json.get("rules"):
        parts.append("**Behavioral rules the correct implementation must satisfy:**")
        for i, rule in enumerate(spec_json["rules"], 1):
            parts.append("  {}. {}".format(i, rule))
        parts.append("")

    if flags["include_code_analysis"] and spec_json.get("fix_target_line"):
        parts.append("**Fix target line:** {}\n".format(spec_json["fix_target_line"]))

    if flags["include_code_analysis"] and spec_json.get("fix_targets"):
        parts.append("**Fix targets:**")
        for i, target in enumerate(spec_json["fix_targets"], 1):
            parts.append(
                "  {}. Line {}: {}".format(
                    i, target.get("line", "?"), target.get("description", "")
                )
            )
        parts.append("")

    if flags["include_fix_direction"] and spec_json.get("fix_direction"):
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

    if spec_json.get("confidence"):
        parts.append("**Diagnosis confidence:** {}\n".format(spec_json["confidence"]))

    if spec_json.get("developer_clarification"):
        parts.append(
            "**Developer clarification:** {}\n".format(spec_json["developer_clarification"])
        )

    parts.append(_FOOTER_IMPORTANT)
    parts.append(_FOOTER_CRITICAL)

    if flags["include_failed_tests"]:
        parts.append(_FOOTER_ANTI_OVERFITTING)

    return "\n".join(parts)


def _make_patched_generate_spec(
    original: Callable[..., dict],
    level: str,
    use_spec_verifier: bool,
    use_self_clarification: bool,
) -> Callable[..., dict]:
    if level == SPEC_LEVEL_NONE:

        def skip_generate_spec(*_args, **_kwargs) -> dict:
            logger.info("ABLATION: spec_level=none — skipping spec generation and injection")
            return {
                "success": True,
                "spec_json": None,
                "prompt_section": "",
                "error": None,
                "failure_reason": None,
                "attempts_used": 0,
                "attempts": [],
                "max_attempts": _kwargs.get("max_attempts"),
                "project_name": _args[0] if _args else _kwargs.get("project_name"),
                "bug_index": _args[1] if len(_args) > 1 else _kwargs.get("bug_index"),
                "spec_final_verdict": "SKIPPED",
                "spec_verifier_summary": "spec_level=none",
            }

        return skip_generate_spec

    if level == SPEC_LEVEL_RAW_CONTEXT:

        def raw_context_generate_spec(*args, **kwargs) -> dict:
            from autogpt.commands.spec_generator import generate_raw_context_injection

            logger.info("ABLATION: spec_level=raw_context — injecting gathered context only")
            result = generate_raw_context_injection(*args, **kwargs)
            if result.get("success") and result.get("prompt_section", "").strip():
                logger.info(
                    "ABLATION: Injected level=raw_context ({} chars)".format(
                        len(result["prompt_section"])
                    )
                )
            return result

        return raw_context_generate_spec

    def ablation_generate_spec(*args, **kwargs) -> dict:
        kwargs["use_spec_verifier"] = use_spec_verifier
        kwargs["use_self_clarification"] = use_self_clarification
        kwargs["spec_ablation_level"] = level
        result = original(*args, **kwargs)
        if not result.get("success"):
            return result

        project_name = args[0] if args else kwargs.get("project_name")
        bug_index = args[1] if len(args) > 1 else kwargs.get("bug_index")
        spec_json = sanitize_spec_json_for_ablation(result.get("spec_json"), level)
        result["spec_json"] = spec_json
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
def patch_generate_spec_for_level(
    level: str,
    use_spec_verifier: bool = DEFAULT_USE_SPEC_VERIFIER,
    use_self_clarification: bool = DEFAULT_USE_SELF_CLARIFICATION,
) -> Iterator[None]:
    """Temporarily replace ``generate_spec`` while ``BaseAgent.__init__`` runs."""
    import autogpt.commands.spec_generator as spec_generator

    original = spec_generator.generate_spec
    spec_generator.generate_spec = _make_patched_generate_spec(
        original, level, use_spec_verifier, use_self_clarification
    )
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
        spec_max_attempts: Optional[int] = None,
    ):
        hyperparams = load_ablation_hyperparams(experiment_file)
        self.spec_level = resolve_spec_level(hyperparams)
        self.use_spec_verifier = resolve_use_spec_verifier(hyperparams)
        self.use_self_clarification = resolve_use_self_clarification(hyperparams)

        logger.info(
            "ABLATION: Using AblationAgent with spec_level={}, "
            "use_spec_verifier={}, use_self_clarification={}".format(
                self.spec_level, self.use_spec_verifier, self.use_self_clarification
            )
        )

        with patch_generate_spec_for_level(
            self.spec_level, self.use_spec_verifier, self.use_self_clarification
        ):
            super().__init__(
                ai_config=ai_config,
                command_registry=command_registry,
                memory=memory,
                triggering_prompt=triggering_prompt,
                config=config,
                cycle_budget=cycle_budget,
                experiment_file=experiment_file,
                spec_max_attempts=spec_max_attempts,
            )

        if "spec_section" in self.prompt_dictionary:
            self.prompt_dictionary["spec_ablation_level"] = self.spec_level
            self.prompt_dictionary["spec_ablation_use_verifier"] = self.use_spec_verifier
            self.prompt_dictionary["spec_ablation_use_self_clarification"] = (
                self.use_self_clarification
            )


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
