#!/usr/bin/env python3
"""ReInFix single-function entry: baseline or spec-enabled pipeline.

Modes (``--mode`` or ``REINFIX_MODE``):

- ``baseline`` — original ReInFix (Joern ReAct → patch → validate)
- ``spec`` — spec generate+verify, inject into ReAct + patch prompts

Prefer batch runs from ReInFix root::

    ./run_reinfix_baseline.sh bug_list/sf_sample.txt hyperparams.json <model>
    ./run_reinfix_spec.sh bug_list/sf_sample.txt hyperparams.json <model>

Or::

    REINFIX_MODE=baseline ./run_reinfix_batch.sh ...
    python src/agent/react_sf_gen_patch.py --bug Chart-1 --mode baseline
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_AGENT = Path(__file__).resolve().parent
_SRC = _AGENT.parent
_ROOT = _SRC.parent

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from experiment_manager import current_experiment_dir, increment_experiment  # noqa: E402
from paths import reinfix_root  # noqa: E402
from reinfix_pipeline import (  # noqa: E402
    _init_runtime,
    _load_dataset,
    _load_hyperparams,
    run_batch,
    run_single_bug,
)
from spec_integration.pipeline_mode import backend_name, resolve_pipeline_mode  # noqa: E402


def _resolve_api_key() -> None:
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return
    try:
        from config import OPENAI_API_KEY

        if OPENAI_API_KEY.strip():
            os.environ.setdefault("OPENAI_API_KEY", OPENAI_API_KEY.strip())
    except ImportError:
        pass


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "bugs_file",
        nargs="?",
        help="Bug list file (Project-bug_id per line). Omit when using --bug.",
    )
    parser.add_argument(
        "hyperparams_file",
        nargs="?",
        default="hyperparams.json",
        help="Hyperparams JSON (default: hyperparams.json)",
    )
    parser.add_argument(
        "model",
        nargs="?",
        default="gpt-4o-mini",
        help="LLM for spec, ReAct, and patch generation",
    )
    parser.add_argument(
        "--bug",
        default="",
        help="Run a single bug id (e.g. Chart-1) instead of a bug list file",
    )
    parser.add_argument(
        "--mode",
        default="",
        help="Pipeline mode: baseline | spec (overrides REINFIX_MODE / hyperparams)",
    )
    parser.add_argument(
        "--analysis-model",
        default="",
        help="Optional separate model for Joern ReAct (default: same as model)",
    )
    parser.add_argument(
        "--dataset",
        default="",
        help="Path to defects4j-sf.json (default: D4J_dataset/defects4j-sf.json)",
    )
    return parser.parse_args(argv)


def _resolve_path(root: Path, candidate: str) -> Path:
    path = Path(candidate)
    if path.is_file():
        return path
    alt = root / candidate
    if alt.is_file():
        return alt
    alt2 = root.parent / "repair_agent" / candidate
    if alt2.is_file():
        return alt2
    return path


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    _resolve_api_key()

    root = reinfix_root()
    os.chdir(root)

    hyper_path = _resolve_path(root, args.hyperparams_file)
    if not hyper_path.is_file():
        hyper_path = root / "hyperparams.json"

    ds_path = Path(args.dataset) if args.dataset else root / "D4J_dataset" / "defects4j-sf.json"
    if not ds_path.is_file():
        raise SystemExit("Dataset not found: {}".format(ds_path))

    hyperparams = _load_hyperparams(str(hyper_path))
    mode = resolve_pipeline_mode(cli_mode=args.mode or None, hyperparams=hyperparams)
    _init_runtime(mode)

    max_spec_attempts = int(hyperparams.get("spec_control", {}).get("max_attempts", 3))
    dataset = _load_dataset(ds_path)
    analysis_model = args.analysis_model or args.model
    output_root = root / "output"

    print("Pipeline mode:", mode, "({})".format(backend_name(mode)))

    if args.bug:
        increment_experiment()
        print("Experiment dir:", current_experiment_dir())
        print("Running single bug:", args.bug)
        run_single_bug(
            args.bug.replace(" ", "-"),
            dataset,
            model=args.model,
            analysis_model=analysis_model,
            max_spec_attempts=max_spec_attempts,
            dataset_path=str(ds_path),
            output_root=output_root,
            pipeline_mode=mode,
        )
        return

    bugs_file = args.bugs_file
    if not bugs_file:
        default_bugs = root / "bug_list" / "sf_v12_sample.txt"
        if not default_bugs.is_file():
            default_bugs = root / "bug_list" / "sf_sample.txt"
        if default_bugs.is_file():
            bugs_file = str(default_bugs)
        else:
            raise SystemExit("Provide bugs_file or --bug Chart-1")

    bugs_path = _resolve_path(root, bugs_file)
    if not bugs_path.is_file():
        raise SystemExit("Bug list not found: {}".format(bugs_file))

    exp_dir = run_batch(
        bugs_file=str(bugs_path),
        hyperparams_file=str(hyper_path),
        model=args.model,
        analysis_model=analysis_model,
        dataset_path=str(ds_path),
        pipeline_mode=mode,
    )
    exp_name = Path(exp_dir).name
    print("\nExperiment finished:", exp_dir)
    print("Results:", os.path.join(exp_dir, "bug_results.jsonl"))
    print("Summarize:")
    print("  cd {} && python experimental_setups/summarize_experiment.py {}".format(root, exp_name))


if __name__ == "__main__":
    main()
