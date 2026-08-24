#!/usr/bin/env python3
"""Verify checkout path conventions for baseline vs spec mode (Step 2)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from spec_integration.checkout import (  # noqa: E402
    baseline_checkout_dir,
    checkout_path_for_mode,
    describe_checkout_layout,
    ensure_bug_checkout,
    joern_project_id,
    verify_checkout_layout,
)
from spec_integration.pipeline_mode import resolve_pipeline_mode  # noqa: E402
from spec_integration.spec_adapter import parse_bug_id, spec_checkout_dir  # noqa: E402


def _check_path_conventions(bug_name: str) -> list[str]:
    project, bug_index = parse_bug_id(bug_name)
    joern_id = joern_project_id(project, bug_index)
    errors: list[str] = []

    baseline_path = baseline_checkout_dir(project, bug_index)
    spec_path = spec_checkout_dir(project, bug_index)
    expected_joern_suffix = "{}-{}_buggy".format(project, bug_index)

    if joern_id != expected_joern_suffix:
        errors.append("joern_project_id mismatch: {} vs {}".format(joern_id, expected_joern_suffix))
    if baseline_path.name != joern_id:
        errors.append("baseline dir name should be {} (got {})".format(joern_id, baseline_path.name))
    if spec_path.name != "{}_{}_buggy".format(project.lower(), bug_index):
        errors.append("unexpected spec checkout dir name: {}".format(spec_path.name))
    if str(baseline_path.parent.name) != "defects4j":
        errors.append("baseline checkout should live under defects4j/")
    if spec_path.parent.name != "auto_gpt_workspace":
        errors.append("spec checkout should live under auto_gpt_workspace/")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bug", nargs="?", default="Chart-1")
    parser.add_argument(
        "--mode",
        choices=("baseline", "spec", "both"),
        default="both",
        help="Which pipeline mode layout to inspect (default: both)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run defects4j checkout via ensure_bug_checkout (requires defects4j)",
    )
    args = parser.parse_args()

    project, bug_index = parse_bug_id(args.bug)
    modes = ["baseline", "spec"] if args.mode == "both" else [args.mode]

    print("Step 2 checkout strategy check (bug={})".format(args.bug))
    path_errors = _check_path_conventions(args.bug)
    for err in path_errors:
        print("[FAIL] path convention: {}".format(err))
    if path_errors:
        return 1

    print("[OK] path conventions for Chart-style ids")
    failed = 0

    for mode in modes:
        resolved = resolve_pipeline_mode(cli_mode=mode)
        info = describe_checkout_layout(resolved, project, bug_index)
        layout_errors = verify_checkout_layout(resolved, project, bug_index)
        print("\n--- mode={} ---".format(resolved))
        print("expected checkout:", info["expected_checkout"])
        print("joern project id:", info["joern_project_id"])
        print("joern link:", info["joern_link_path"])
        print("checkout ready:", info.get("checkout_ready"))
        if info.get("joern_resolves_to"):
            print("joern resolves to:", info["joern_resolves_to"])
        if layout_errors:
            for err in layout_errors:
                print("[WARN] {}".format(err))
        else:
            print("[OK] layout rules satisfied (checkout may still be absent)")

        if args.live:
            try:
                checkout_path, joern_id = ensure_bug_checkout(
                    resolved, project, bug_index, force=False
                )
                print("[OK] live checkout:", checkout_path, "joern:", joern_id)
                post_errors = verify_checkout_layout(resolved, project, bug_index)
                for err in post_errors:
                    print("[FAIL] post-checkout: {}".format(err))
                    failed += 1
            except Exception as exc:
                print("[FAIL] live checkout (mode={}): {}".format(resolved, exc))
                failed += 1

    if failed:
        print("\n{} live checkout check(s) failed.".format(failed))
        return 1

    print("\nStep 2 checkout strategy verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
