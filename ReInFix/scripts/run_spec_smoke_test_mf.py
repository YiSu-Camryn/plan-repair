#!/usr/bin/env python3
"""Step 2 smoke test for MF: run generate+verify spec for one D4J MF bug."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


def _resolve_api_key() -> bool:
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return True
    try:
        from config import OPENAI_API_KEY

        if OPENAI_API_KEY.strip():
            os.environ.setdefault("OPENAI_API_KEY", OPENAI_API_KEY.strip())
            return True
    except ImportError:
        pass
    return False


def _verify_joern_link(bug_name: str, checkout_performed: bool) -> tuple[bool, str]:
    from spec_integration.spec_adapter import (
        has_spec_checkout,
        joern_checkout_link,
        parse_bug_id,
        spec_checkout_dir,
    )

    if not checkout_performed and not has_spec_checkout(*parse_bug_id(bug_name)):
        return True, "skipped (no checkout)"

    project, bug_index = parse_bug_id(bug_name)
    spec_path = spec_checkout_dir(project, bug_index)
    link_path = joern_checkout_link(project, bug_index)
    if not link_path.exists() and not link_path.is_symlink():
        return False, "missing Joern link at {}".format(link_path)
    try:
        resolved = link_path.resolve()
    except OSError as exc:
        return False, "broken Joern link: {}".format(exc)
    if resolved != spec_path.resolve():
        return False, "points to {}, expected {}".format(resolved, spec_path.resolve())
    return True, str(resolved)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "bug",
        nargs="?",
        default="Chart-2",
        help="MF bug id, e.g. Chart-2 (default: Chart-2)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("SPEC_SMOKE_MODEL", "gpt-4o-mini"),
        help="LLM model for spec generate/verify",
    )
    parser.add_argument(
        "--no-checkout",
        action="store_true",
        help="Skip defects4j checkout (reuse existing auto_gpt_workspace checkout)",
    )
    parser.add_argument(
        "--no-tests",
        action="store_true",
        help="Do not run defects4j test for test_results (use dataset errors only)",
    )
    parser.add_argument(
        "--no-d4j-info",
        action="store_true",
        help="Do not call defects4j info for localization_info (dataset + GT only)",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip environment preflight (not recommended)",
    )
    parser.add_argument(
        "--hyperparams",
        default=str(ROOT / "hyperparams.json"),
        help="Path to hyperparams.json",
    )
    args = parser.parse_args()

    from spec_integration.mf_localization import MF_DATASET_NAME, mf_function_count
    from spec_integration.mf_spec_adapter import get_spec_prompt_section, run_spec_for_mf_dataset_bug
    from spec_integration.spec_adapter import ensure_spec_runtime, load_dataset_entry
    from spec_integration.verify import format_check_line, run_preflight_checks

    if not args.skip_preflight:
        print("=== Step 2 MF preflight ===")
        checks, failed = run_preflight_checks(args.bug, include_optional=False)
        for item in checks:
            line = format_check_line(item, include_optional=False)
            if line:
                print(line)
        if failed:
            print("\nFix environment before smoke test:")
            print("  python scripts/verify_spec_environment.py {}".format(args.bug))
            return 1
        print("Preflight OK.\n")
    else:
        print("=== Step 2 MF preflight skipped ===\n")

    if not _resolve_api_key():
        print("ERROR: set OPENAI_API_KEY before smoke test.")
        return 1

    if args.no_tests:
        os.environ["REINFIX_SPEC_RUN_TESTS"] = "0"
    else:
        os.environ.setdefault("REINFIX_SPEC_RUN_TESTS", "1")

    if args.no_d4j_info:
        os.environ["REINFIX_SPEC_USE_D4J_INFO"] = "0"
    else:
        os.environ.setdefault("REINFIX_SPEC_USE_D4J_INFO", "1")

    exp_dir = ensure_spec_runtime()
    print("Experiment dir: {}\n".format(exp_dir))

    entry = load_dataset_entry(args.bug, variant="mf")
    print(
        "=== Running MF spec for {} (model={}, {} functions) ===".format(
            args.bug, args.model, mf_function_count(entry)
        )
    )
    print(
        "Options: checkout={}, run_tests={}, use_d4j_info={}".format(
            not args.no_checkout,
            not args.no_tests,
            not args.no_d4j_info,
        )
    )

    result = run_spec_for_mf_dataset_bug(
        args.bug,
        entry,
        model=args.model,
        hyperparams_file=args.hyperparams,
        checkout=not args.no_checkout,
        run_tests=not args.no_tests,
        use_d4j_info=not args.no_d4j_info,
    )

    joern_ok, joern_msg = _verify_joern_link(args.bug, checkout_performed=not args.no_checkout)

    print("\n=== Result ===")
    summary = {
        "success": result.get("success"),
        "failure_reason": result.get("failure_reason"),
        "attempts_used": result.get("attempts_used"),
        "max_attempts": result.get("max_attempts"),
        "prompt_section_chars": len(get_spec_prompt_section(result)),
        "joern_project_name": result.get("joern_project_name"),
        "spec_checkout_dir": result.get("spec_checkout_dir"),
        "joern_checkout_link": result.get("joern_checkout_link"),
        "joern_link_ok": joern_ok,
        "joern_link_detail": joern_msg,
        "repair_scenario": result.get("repair_scenario"),
        "dataset": result.get("dataset") or MF_DATASET_NAME,
    }
    print(json.dumps(summary, indent=2))

    spec_logs = Path(exp_dir) / "spec_logs"
    if spec_logs.is_dir():
        logs = sorted(spec_logs.glob("*"))
        print("\nSpec logs ({} files):".format(len(logs)))
        for path in logs[:8]:
            print("  {}".format(path.name))
        if len(logs) > 8:
            print("  ...")

    if not joern_ok:
        print("\nJoern/spec checkout alignment failed: {}".format(joern_msg))
        return 1

    if not result.get("success"):
        print("\nSpec failed. See spec_logs/spec_failure_* and stderr.")
        return 1

    section = get_spec_prompt_section(result)
    if not section:
        print("\nWARN: success but empty prompt_section.")
        return 1

    print("\nMF Step 2 smoke test PASSED (prompt_section {} chars).".format(len(section)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
