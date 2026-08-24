"""ReInFix single-function pipeline: baseline or spec-enabled repair."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import openai
from langchain.agents import AgentExecutor, create_react_agent
from langchain_community.callbacks import get_openai_callback
from langchain_openai import ChatOpenAI

from experiment_manager import (
    current_experiment_dir,
    experiment_subdir,
    increment_experiment,
    patch_repairagent_experiment_hooks,
)
from paths import reinfix_root, repairagent_root
from results_recorder import record_bug_run, record_spec_failed
from spec_bridge import parse_bug_name
from spec_integration.checkout import ensure_bug_checkout
from spec_integration.pipeline_mode import (
    PipelineMode,
    backend_name,
    is_spec_enabled,
    mode_label,
    resolve_pipeline_mode,
    skipped_spec_result,
)
from spec_integration.spec_adapter import (
    get_spec_prompt_section,
    joern_project_name,
    run_spec_for_dataset_bug,
)
from spec_integration.spec_prompts import (
    baseline_react_prompt_kwargs,
    build_baseline_patch_context_lines,
    build_baseline_patch_generation_prompt,
    build_baseline_react_prompt_template,
    build_patch_context_lines,
    build_patch_generation_prompt,
    build_react_prompt_template,
    react_prompt_kwargs,
    save_injection_prompt_artifacts,
    save_prompt_section_artifact,
    verify_baseline_patch_prompt_excludes_spec,
    verify_baseline_react_prompt_excludes_spec,
    verify_patch_prompt_contains_spec,
    verify_react_prompt_contains_spec,
)

try:
    from spec_integration.bootstrap import setup_environment as _setup_reinfix_env
except ImportError:
    _setup_reinfix_env = None  # type: ignore[misc, assignment]

# Joern tools live in agent/; import after cwd setup in run_single_bug
AGENT_DIR = Path(__file__).resolve().parent / "agent"


def _init_runtime(pipeline_mode: PipelineMode) -> None:
    """Baseline: defects4j PATH only. Spec: full bootstrap + RepairAgent assets."""
    from paths import ensure_repairagent_on_path

    ensure_repairagent_on_path()
    root = reinfix_root()
    os.chdir(root)

    for framework_bin in (
        root / "defects4j" / "framework" / "bin",
        repairagent_root() / "defects4j" / "framework" / "bin",
    ):
        if framework_bin.is_dir():
            bin_str = str(framework_bin)
            path_env = os.environ.get("PATH", "")
            if bin_str not in path_env:
                os.environ["PATH"] = bin_str + os.pathsep + path_env

    if is_spec_enabled(pipeline_mode) and _setup_reinfix_env is not None:
        _setup_reinfix_env()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


def _load_hyperparams(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _load_dataset(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(f)


def _load_bug_list(path: Path) -> list[str]:
    bugs = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if " " in line and "-" not in line.split()[0]:
                parts = line.split()
                bugs.append("{}-{}".format(parts[0], parts[1]))
            elif "-" in line:
                bugs.append(line.replace(" ", "-"))
            else:
                bugs.append(line)
    return bugs


def _trigger_context(entry: dict[str, Any]) -> tuple[list[str], list[str]]:
    trigger_src_list = []
    err_msg_list = []
    for trigger_test in entry.get("trigger_test", {}):
        t = entry["trigger_test"][trigger_test]
        trigger_src_list.append(t.get("src", ""))
        err_msg_list.append(t.get("clean_error_msg", ""))
    return trigger_src_list, err_msg_list


def _extract_and_save_final_answer(text: str, output_file: str, name: str) -> dict[str, Any]:
    root_cause_match = re.search(
        r"(?i)root\s*cause:?\s*(.+?)(?=\n+ *suggestion|\Z)", text, re.DOTALL | re.IGNORECASE
    )
    suggestions_matches = re.finditer(
        r"(?i)suggestion\s*(\d+):?\s*(.*?)(?=\n\s*suggestion|\Z)", text, re.DOTALL | re.IGNORECASE
    )
    if not root_cause_match:
        raise ValueError("Root Cause not found in the text")
    root_cause = root_cause_match.group(1).strip()
    suggestions = []
    for match in suggestions_matches:
        suggestion_number = match.group(1)
        suggestion_text = match.group(2).strip()
        lines = suggestion_text.split("\n", 1)
        title = lines[0].strip()
        details = lines[1].strip() if len(lines) > 1 else ""
        suggestions.append(
            "Suggestion {}. {} {}\n".format(suggestion_number, title, details)
        )
    if os.path.exists(output_file):
        with open(output_file, encoding="utf-8") as handle:
            all_analyses = json.load(handle)
    else:
        all_analyses = {}
    all_analyses[name] = {root_cause: suggestions}
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as handle:
        json.dump(all_analyses, handle, ensure_ascii=False, indent=2)
    return all_analyses


def _parse_patches(result: str) -> list[str]:
    pattern = r"\[START PATCH \d+\]\n```\w*\n(.*?)\n```\n\[END PATCH \d+\]"
    return [p.strip() for p in re.findall(pattern, result, re.DOTALL)]


def _append_patches_to_json(patches: list[str], file_path: str, project_name: str) -> None:
    data = {}
    if os.path.exists(file_path):
        with open(file_path, encoding="utf-8") as handle:
            data = json.load(handle)
    if project_name not in data:
        data[project_name] = {"patches": []}
    data[project_name]["patches"].extend(patches)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def _estimate_patch_cost(usage: Any) -> float:
    if not usage:
        return 0.0
    return usage.prompt_tokens * 0.000005 + usage.completion_tokens * 0.00002


def _validate_patches(bug_name: str, patches_file: str, dataset_path: str) -> tuple[str, Optional[str]]:
    val_dir = reinfix_root() / "src" / "validation" / "D4J"
    prev = os.getcwd()
    os.makedirs(val_dir / "sf-plausible", exist_ok=True)
    try:
        os.chdir(val_dir)
        sys.path.insert(0, str(val_dir))
        from sf_val_d4j import validate_patches_per_bug  # noqa: WPS433

        with open(patches_file, encoding="utf-8") as handle:
            candidate = json.load(handle)
        validate_patches_per_bug(candidate)
        plausible_file = val_dir / "sf-plausible" / "{}-plausible.json".format(bug_name)
        if plausible_file.is_file():
            dest = Path(current_experiment_dir()) / "plausible_patches" / "plausible_patches_{}.json".format(
                bug_name.replace("-", "_")
            )
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(plausible_file.read_text(encoding="utf-8"), encoding="utf-8")
            return "FIXED", str(dest)
        return "NOT_FIXED", None
    finally:
        if str(val_dir) in sys.path:
            sys.path.remove(str(val_dir))
        os.chdir(prev)


def run_single_bug(
    bug_name: str,
    dataset: dict[str, Any],
    model: str,
    analysis_model: str,
    max_spec_attempts: int,
    dataset_path: str,
    output_root: Path,
    pipeline_mode: PipelineMode = "spec",
) -> None:
    if bug_name not in dataset:
        print("Skipping {}: not in dataset".format(bug_name))
        return

    use_spec = is_spec_enabled(pipeline_mode)
    backend = backend_name(pipeline_mode)
    project, bug_index = parse_bug_name(bug_name)
    entry = dataset[bug_name]
    started_at = _utc_now()
    t0 = time.monotonic()
    prompt_tokens = 0
    completion_tokens = 0
    cost_usd = 0.0
    repair_cycles = 0

    exp_dir = current_experiment_dir()
    patch_repairagent_experiment_hooks(exp_dir)
    log_dir = output_root / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "{}.log".format(bug_name)

    def log(msg: str) -> None:
        line = "[{}] {}\n".format(datetime.now().isoformat(), msg)
        print(line, end="")
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(line)

    log("=== {}: {} ===".format(mode_label(pipeline_mode), bug_name))

    spec_section = ""
    spec_artifact: str | None = None
    injection_artifacts: dict[str, str] = {}
    joern_proj = joern_project_name(project, bug_index)

    if use_spec:
        spec_result = run_spec_for_dataset_bug(
            bug_name,
            entry,
            model=model,
            max_attempts=max_spec_attempts,
            exp_dir=exp_dir,
            run_tests=_env_flag("REINFIX_SPEC_RUN_TESTS", default=True),
            use_d4j_info=_env_flag("REINFIX_SPEC_USE_D4J_INFO", default=True),
        )
        if not spec_result.get("success"):
            log("Spec failed: {}".format(spec_result.get("failure_reason")))
            record_spec_failed(
                project,
                bug_index,
                spec_result,
                model,
                time.monotonic() - t0,
                started_at,
                {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "cost_usd": round(cost_usd, 6),
                },
                backend=backend,
                pipeline_mode=pipeline_mode,
            )
            return

        spec_section = get_spec_prompt_section(spec_result)
        if not spec_section:
            log("Spec succeeded but prompt_section is empty")
            spec_result = dict(spec_result)
            spec_result["success"] = False
            spec_result["failure_reason"] = "empty prompt_section after ACCEPT"
            record_spec_failed(
                project,
                bug_index,
                spec_result,
                model,
                time.monotonic() - t0,
                started_at,
                {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "cost_usd": round(cost_usd, 6),
                },
                backend=backend,
                pipeline_mode=pipeline_mode,
            )
            return

        spec_artifact = save_prompt_section_artifact(exp_dir, bug_name, spec_section)
        joern_proj = spec_result.get("joern_project_name") or joern_proj
        log(
            "Spec OK ({} chars); Joern project: {}; artifact: {}".format(
                len(spec_section), joern_proj, spec_artifact
            )
        )
    else:
        spec_result = skipped_spec_result(max_attempts=max_spec_attempts)
        checkout_path, joern_proj = ensure_bug_checkout(
            pipeline_mode, project, bug_index
        )
        log(
            "Baseline checkout: {} (Joern project: {})".format(checkout_path, joern_proj)
        )

    trigger_src_list, err_msg_list = _trigger_context(entry)
    trigger_src = str(trigger_src_list)
    err_msg = str(err_msg_list)
    solutions_path = output_root / "sf_solutions" / "{}.json".format(bug_name)
    patches_path = output_root / "sf_patches" / "{}.json".format(bug_name)
    react_out_path = experiment_subdir(
        "responses", "model_responses_{}".format(bug_name.replace("-", "_"))
    )

    if use_spec:
        patch_context = build_patch_context_lines(
            bug_name, entry, joern_proj, trigger_src, err_msg, spec_section
        )
    else:
        patch_context = build_baseline_patch_context_lines(
            bug_name, entry, joern_proj, trigger_src, err_msg
        )

    prev_cwd = os.getcwd()
    os.chdir(AGENT_DIR)
    sys.path.insert(0, str(AGENT_DIR))
    try:
        from tools import (  # noqa: WPS433
            analyze_method_control_flow_tool,
            analyze_method_details_tool,
            close_proj_tool,
            example_patch_search_tool,
            find_class_loc_tool,
            find_method_in_file_tool,
            get_imports_tool,
            identify_class_tool,
            open_proj_tool,
            trace_method_usage_tool,
        )

        tools = [
            open_proj_tool,
            trace_method_usage_tool,
            find_method_in_file_tool,
            analyze_method_details_tool,
            analyze_method_control_flow_tool,
            find_class_loc_tool,
            identify_class_tool,
            get_imports_tool,
            close_proj_tool,
            example_patch_search_tool,
        ]
        tool_descriptions = "\n".join(
            "{}. {}\n".format(i + 1, t.description) for i, t in enumerate(tools)
        )
        tool_names = "\n".join("{}. {}\n".format(i + 1, t.name) for i, t in enumerate(tools))

        if use_spec:
            prompt = build_react_prompt_template().partial(
                **react_prompt_kwargs(
                    spec_section,
                    entry,
                    joern_proj,
                    tool_descriptions,
                    tool_names,
                    trigger_src,
                    err_msg,
                )
            )
            react_prompt_preview = prompt.format(agent_scratchpad="")
            if not verify_react_prompt_contains_spec(react_prompt_preview, spec_section):
                raise RuntimeError(
                    "ReAct prompt missing verified behavioral spec (injection point 1)"
                )
            log("ReAct prompt includes spec ({} chars)".format(len(spec_section)))

            patch_prompt_sample = build_patch_generation_prompt(
                spec_section,
                patch_context,
                "<root cause from ReAct>",
                "<suggestion from ReAct>",
            )
            if not verify_patch_prompt_contains_spec(patch_prompt_sample, spec_section):
                raise RuntimeError(
                    "Patch prompt missing verified behavioral spec (injection point 2)"
                )
            injection_artifacts = save_injection_prompt_artifacts(
                exp_dir,
                bug_name,
                react_prompt_preview,
                patch_prompt_sample,
            )
            log("Saved injection prompts: {}".format(injection_artifacts))
        else:
            prompt = build_baseline_react_prompt_template().partial(
                **baseline_react_prompt_kwargs(
                    entry,
                    joern_proj,
                    tool_descriptions,
                    tool_names,
                    trigger_src,
                    err_msg,
                )
            )
            react_prompt_preview = prompt.format(agent_scratchpad="")
            if not verify_baseline_react_prompt_excludes_spec(react_prompt_preview):
                raise RuntimeError("Baseline ReAct prompt unexpectedly contains spec")
            patch_prompt_sample = build_baseline_patch_generation_prompt(
                patch_context,
                "<root cause from ReAct>",
                "<suggestion from ReAct>",
            )
            if not verify_baseline_patch_prompt_excludes_spec(patch_prompt_sample):
                raise RuntimeError("Baseline patch prompt unexpectedly contains spec")
            log("Baseline ReAct/patch prompts ready (no spec injection)")

        llm = ChatOpenAI(model_name=analysis_model)
        agent = create_react_agent(llm, tools, prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            stream_runnable=False,
            handle_parsing_errors=(
                "Check your output and make sure it conforms. "
                "Output the Final Answer as the last step."
            ),
        )
        with get_openai_callback() as cb:
            result = executor.invoke({})
            prompt_tokens += cb.prompt_tokens
            completion_tokens += cb.completion_tokens
            cost_usd += cb.total_cost
            repair_cycles = len(result.get("intermediate_steps") or [])

        output_text = result.get("output", "")
        with open(react_out_path, "w", encoding="utf-8") as handle:
            handle.write(output_text)
        _extract_and_save_final_answer(output_text, str(solutions_path), bug_name)
    except Exception as exc:
        log("ReAct failed: {}".format(exc))
        record_bug_run(
            project,
            bug_index,
            spec_result,
            model,
            "NOT_FIXED",
            time.monotonic() - t0,
            started_at,
            {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "cost_usd": round(cost_usd, 6),
            },
            repair_cycles_used=repair_cycles,
            fixes_attempted=0,
            repair_failure_reason=str(exc),
            react_output_path=react_out_path if os.path.exists(react_out_path) else None,
            spec_prompt_artifact=spec_artifact,
            injection_prompt_artifacts=injection_artifacts or None,
            backend=backend,
            pipeline_mode=pipeline_mode,
        )
        os.chdir(prev_cwd)
        return
    finally:
        if str(AGENT_DIR) in sys.path:
            sys.path.remove(str(AGENT_DIR))
        os.chdir(prev_cwd)

    with open(solutions_path, encoding="utf-8") as handle:
        solutions = json.load(handle)

    fixes_attempted = 0
    openai.api_key = os.environ.get("OPENAI_API_KEY", "")

    for root_cause in solutions.get(bug_name, {}):
        for suggestion in solutions[bug_name][root_cause]:
            if use_spec:
                prompt_patch = build_patch_generation_prompt(
                    spec_section,
                    patch_context,
                    str(root_cause),
                    str(suggestion),
                )
            else:
                prompt_patch = build_baseline_patch_generation_prompt(
                    patch_context,
                    str(root_cause),
                    str(suggestion),
                )
            try:
                response = openai.chat.completions.create(
                    messages=[{"role": "user", "content": prompt_patch}],
                    model=analysis_model,
                    n=5,
                    temperature=0.8,
                )
                usage = response.usage
                if usage:
                    prompt_tokens += usage.prompt_tokens
                    completion_tokens += usage.completion_tokens
                    cost_usd += _estimate_patch_cost(usage)
                for choice in response.choices:
                    patches = _parse_patches(choice.message.content.strip())
                    if patches:
                        fixes_attempted += len(patches)
                        _append_patches_to_json(patches, str(patches_path), bug_name)
            except openai.OpenAIError as exc:
                log("Patch API error: {}".format(exc))
                break

    outcome = "NOT_FIXED"
    plausible_path = None
    if patches_path.is_file():
        outcome, plausible_path = _validate_patches(bug_name, str(patches_path), dataset_path)

    record_bug_run(
        project,
        bug_index,
        spec_result,
        model,
        outcome,
        time.monotonic() - t0,
        started_at,
        {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost_usd": round(cost_usd, 6),
        },
        repair_cycles_used=repair_cycles,
        fixes_attempted=fixes_attempted,
        repair_failure_reason=None if outcome == "FIXED" else "No plausible patch after validation",
        plausible_patch_path=plausible_path,
        react_output_path=str(react_out_path),
        spec_prompt_artifact=spec_artifact,
        injection_prompt_artifacts=injection_artifacts or None,
        backend=backend,
        pipeline_mode=pipeline_mode,
    )
    log("Done {} → {} ({})".format(bug_name, outcome, backend))


def run_batch(
    bugs_file: str,
    hyperparams_file: str,
    model: str,
    analysis_model: Optional[str] = None,
    dataset_path: Optional[str] = None,
    pipeline_mode: str | None = None,
) -> str:
    hyperparams = _load_hyperparams(hyperparams_file)
    mode = resolve_pipeline_mode(cli_mode=pipeline_mode, hyperparams=hyperparams)
    _init_runtime(mode)
    root = reinfix_root()
    os.chdir(root)
    increment_experiment()
    exp = current_experiment_dir()
    print("Pipeline mode:", mode, "({})".format(backend_name(mode)))
    print("Experiment dir:", exp)

    max_spec_attempts = int(hyperparams.get("spec_control", {}).get("max_attempts", 3))
    ds_path = Path(dataset_path or root / "D4J_dataset" / "defects4j-sf.json")
    dataset = _load_dataset(ds_path)
    bugs = _load_bug_list(Path(bugs_file))
    if not bugs:
        bugs = list(dataset.keys())

    output_root = root / "output"
    analysis_model = analysis_model or model

    for bug_name in bugs:
        run_single_bug(
            bug_name,
            dataset,
            model=model,
            analysis_model=analysis_model,
            max_spec_attempts=max_spec_attempts,
            dataset_path=str(ds_path),
            output_root=output_root,
            pipeline_mode=mode,
        )
    return exp


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "ReInFix pipeline: baseline or spec-enabled "
            "(spec generate+verify → Joern ReAct → patch → validate)"
        )
    )
    parser.add_argument(
        "bugs_file",
        help="Bug list file (Project bug_id per line, or Project-bug_id)",
    )
    parser.add_argument(
        "hyperparams_file",
        nargs="?",
        default="hyperparams.json",
        help="Hyperparams JSON (pipeline_mode, spec_control.max_attempts)",
    )
    parser.add_argument(
        "model",
        nargs="?",
        default="gpt-4o-mini",
        help="LLM for spec generate/verify and patch generation",
    )
    parser.add_argument(
        "--analysis-model",
        default="",
        help="Optional separate model for Joern ReAct analysis (default: same as model)",
    )
    parser.add_argument(
        "--dataset",
        default="",
        help="Path to defects4j-sf.json (default: D4J_dataset/defects4j-sf.json)",
    )
    parser.add_argument(
        "--mode",
        default="",
        help="Pipeline mode: baseline | spec (overrides REINFIX_MODE and hyperparams.pipeline_mode)",
    )
    args = parser.parse_args()

    root = reinfix_root()
    bugs_path = Path(args.bugs_file)
    if not bugs_path.is_file():
        alt = root / args.bugs_file
        if alt.is_file():
            bugs_path = alt
        else:
            alt2 = root.parent / "repair_agent" / args.bugs_file
            if alt2.is_file():
                bugs_path = alt2

    hyper_path = Path(args.hyperparams_file)
    if not hyper_path.is_file():
        alt = root / args.hyperparams_file
        if alt.is_file():
            hyper_path = alt

    try:
        from config import OPENAI_API_KEY
    except ImportError:
        from src.config import OPENAI_API_KEY  # type: ignore[no-redef]

    if OPENAI_API_KEY:
        os.environ.setdefault("OPENAI_API_KEY", OPENAI_API_KEY)

    exp_dir = run_batch(
        bugs_file=str(bugs_path),
        hyperparams_file=str(hyper_path),
        model=args.model,
        analysis_model=args.analysis_model or None,
        dataset_path=args.dataset or None,
        pipeline_mode=args.mode or None,
    )
    exp_name = Path(exp_dir).name
    print("\nExperiment finished:", exp_dir)
    print("Results:", os.path.join(exp_dir, "bug_results.jsonl"))
    print("Summarize:")
    print("  cd {} && python experimental_setups/summarize_experiment.py {}".format(root, exp_name))


if __name__ == "__main__":
    main()
