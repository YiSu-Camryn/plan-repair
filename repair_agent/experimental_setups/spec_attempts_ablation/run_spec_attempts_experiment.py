#!/usr/bin/env python3
"""Spec-only batch experiment using RepairAgent's generate_spec + verifier.

Runs max_attempts=N (default 5) per bug without starting the repair agent loop.
Pass@2/3/4/5 are derived offline via summarize_spec_pass_rates.py.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ABLATION_DIR = Path(__file__).resolve().parent
REPAIR_AGENT_ROOT = ABLATION_DIR.parents[1]
DEFAULT_BUGS_FILE = ABLATION_DIR / "sample_40.txt"
DEFAULT_SAMPLE_JSON = ABLATION_DIR / "sample_40.json"
DEFAULT_HYPERPARAMS = REPAIR_AGENT_ROOT / "hyperparams.json"
BUG_RESULTS_FILENAME = "bug_results.jsonl"
RUN_META_FILENAME = "run_meta.json"
WORKSPACE = "auto_gpt_workspace"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _setup_repair_agent_cwd() -> None:
    os.chdir(REPAIR_AGENT_ROOT)
    root = str(REPAIR_AGENT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def patch_repairagent_experiment_dir(exp_dir: str) -> None:
    """Point RepairAgent spec logs and bug_results at a custom experiment folder."""
    spec_logs = os.path.join(exp_dir, "spec_logs")
    os.makedirs(spec_logs, exist_ok=True)

    def _get_spec_log_dir() -> str:
        os.makedirs(spec_logs, exist_ok=True)
        return spec_logs

    def _current_experiment_dir() -> str:
        return exp_dir

    import autogpt.bug_results_recorder as bug_results_recorder
    import autogpt.commands.spec_generator as spec_generator
    import autogpt.spec_failure_recorder as spec_failure_recorder

    spec_generator._get_spec_log_dir = _get_spec_log_dir  # type: ignore[attr-defined]
    bug_results_recorder._current_experiment_dir = _current_experiment_dir  # type: ignore[assignment]
    spec_failure_recorder._current_experiment_dir = _current_experiment_dir  # type: ignore[assignment]


def load_batch_lookup(sample_json: Path | None = None) -> dict[str, int]:
    path = sample_json or DEFAULT_SAMPLE_JSON
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return {b["bug_key"]: int(b["batch"]) for b in data.get("bugs", [])}


def load_bug_lines(bugs_file: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for raw in bugs_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            rows.append((parts[0], parts[1]))
    return rows


def bug_key(project: str, bug_index: str) -> str:
    return f"{project}-{bug_index}"


def load_completed_keys(results_path: Path) -> set[str]:
    if not results_path.is_file():
        return set()
    done: set[str] = set()
    with open(results_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            project = row.get("project")
            bug_index = str(row.get("bug_index") or "")
            if project and bug_index:
                done.add(bug_key(project, bug_index))
    return done


def write_run_meta(output_dir: Path, meta: dict) -> None:
    with open(output_dir / RUN_META_FILENAME, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def run_spec_for_bug(
    project: str,
    bug_index: str,
    model: str,
    max_attempts: int,
    checkout: bool,
) -> dict:
    from autogpt.commands.defects4j_static import get_info, run_tests
    from autogpt.commands.spec_generator import generate_spec

    if checkout:
        from repairagent import checkout_bug

        checkout_bug(project, bug_index)

    buggy_dir = os.path.join(
        WORKSPACE, f"{project.lower()}_{bug_index}_buggy"
    )
    if not os.path.isdir(buggy_dir):
        raise RuntimeError(f"Buggy workspace missing: {buggy_dir}")

    localization_info = get_info(project, bug_index, WORKSPACE)
    test_results = run_tests(project, bug_index, WORKSPACE, restore_after=False)

    return generate_spec(
        project_name=project,
        bug_index=bug_index,
        localization_info=localization_info,
        test_results=test_results,
        model=model,
        workspace=WORKSPACE,
        max_attempts=max_attempts,
    )


def run_experiment(args: argparse.Namespace) -> int:
    bugs_file = Path(args.bugs_file)
    if not bugs_file.is_file():
        print(f"ERROR: bugs file not found: {bugs_file}", file=sys.stderr)
        return 1

    max_attempts = args.max_attempts

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = ABLATION_DIR / "runs" / f"max{max_attempts}_{stamp}"

    bugs = load_bug_lines(bugs_file)
    if args.limit:
        bugs = bugs[: args.limit]

    results_path = output_dir / BUG_RESULTS_FILENAME
    completed = load_completed_keys(results_path) if args.resume else set()
    pending = [(p, i) for p, i in bugs if bug_key(p, i) not in completed]

    if args.dry_run:
        print(f"Output dir: {output_dir}")
        print(f"Bugs scheduled: {len(bugs)} | resume skip: {len(completed)} | pending: {len(pending)}")
        print(f"max_attempts={max_attempts} model={args.model} backend=repairagent-spec-only\n")
        for project, bug_index in pending:
            print(f"  would run: {bug_key(project, bug_index)}")
        return 0

    _setup_repair_agent_cwd()

    from autogpt.bug_results_recorder import (
        BUG_RESULTS_FILENAME as RA_BUG_RESULTS,
        record_bug_result_spec_failed,
        record_bug_result_spec_ok,
    )
    from autogpt.config.hyperparams_loader import load_hyperparams, resolve_spec_max_attempts
    from autogpt.spec_failure_recorder import record_spec_failure

    assert RA_BUG_RESULTS == BUG_RESULTS_FILENAME

    max_attempts = resolve_spec_max_attempts(
        load_hyperparams(args.hyperparams),
        args.max_attempts,
    )

    if not args.output_dir:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = ABLATION_DIR / "runs" / f"max{max_attempts}_{stamp}"

    output_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("spec_logs", "logs", "responses"):
        (output_dir / sub).mkdir(exist_ok=True)

    results_path = output_dir / BUG_RESULTS_FILENAME
    if args.resume:
        completed = load_completed_keys(results_path)
        pending = [(p, i) for p, i in bugs if bug_key(p, i) not in completed]

    patch_repairagent_experiment_dir(str(output_dir.resolve()))

    if not args.skip_preflight and not os.environ.get("OPENAI_API_KEY", "").strip():
        print("ERROR: set OPENAI_API_KEY before running.", file=sys.stderr)
        return 1

    meta = {
        "backend": "repairagent-spec-only",
        "bugs_file": str(bugs_file.resolve()),
        "output_dir": str(output_dir.resolve()),
        "model": args.model,
        "max_attempts": max_attempts,
        "hyperparams": str(Path(args.hyperparams).resolve()),
        "scheduled_bugs": len(bugs),
        "already_completed": len(completed),
        "pending_bugs": len(pending),
        "checkout": not args.no_checkout,
        "started_at": _utc_now(),
    }
    write_run_meta(output_dir, meta)

    failures = 0

    print(f"Output dir: {output_dir}")
    print(f"Pending bugs: {len(pending)} | max_attempts={max_attempts} | model={args.model}\n")

    for idx, (project, bug_index) in enumerate(pending, start=1):
        key = bug_key(project, bug_index)
        started_at = _utc_now()
        t0 = time.monotonic()
        print(f"[{idx}/{len(pending)}] {key} ...", flush=True)

        try:
            spec_result = run_spec_for_bug(
                project,
                bug_index,
                model=args.model,
                max_attempts=max_attempts,
                checkout=not args.no_checkout,
            )
        except Exception as exc:
            spec_result = {
                "success": False,
                "failure_reason": "EXCEPTION",
                "error": str(exc),
                "attempts_used": 0,
                "max_attempts": max_attempts,
                "project_name": project,
                "bug_index": bug_index,
            }
            print(f"  EXCEPTION: {exc}", flush=True)

        elapsed = time.monotonic() - t0

        if spec_result.get("success"):
            record_bug_result_spec_ok(
                spec_result,
                model=args.model,
                elapsed_seconds=elapsed,
                started_at=started_at,
            )
            status = "PASS"
        else:
            record_spec_failure(project, bug_index, spec_result)
            record_bug_result_spec_failed(
                spec_result,
                model=args.model,
                elapsed_seconds=elapsed,
                started_at=started_at,
            )
            status = "FAIL"
            failures += 1

        attempts = spec_result.get("attempts_used")
        print(f"  -> {status} attempts_used={attempts} elapsed={elapsed:.1f}s", flush=True)

    meta["ended_at"] = _utc_now()
    meta["ran_bugs"] = len(pending)
    meta["spec_failures"] = failures
    write_run_meta(output_dir, meta)

    print(f"\nDone. Results: {results_path}")
    print(f"Summarize: py summarize_spec_pass_rates.py {output_dir}")

    if args.summarize and pending:
        sys.path.insert(0, str(ABLATION_DIR))
        from summarize_spec_pass_rates import summarize_file, write_summary, print_summary

        summary = summarize_file(results_path, ks=(2, 3, 4, 5))
        write_summary(output_dir, summary)
        print_summary(summary)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bugs-file", default=str(DEFAULT_BUGS_FILE))
    parser.add_argument("--output-dir", default="")
    parser.add_argument(
        "--model",
        default=os.environ.get("REPAIRAGENT_MODEL", "deepseek.v3.2"),
    )
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--hyperparams", default=str(DEFAULT_HYPERPARAMS))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-checkout", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    return parser


def main() -> int:
    return run_experiment(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
