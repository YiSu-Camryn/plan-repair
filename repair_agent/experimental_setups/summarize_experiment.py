#!/usr/bin/env python3
"""Summarize bug_results.jsonl for one experiment folder."""

from __future__ import annotations

import argparse
import json
import os
import statistics
from collections import Counter
from typing import Any


def _load_bug_results(path: str) -> list[dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _pct(n: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return "{:.1f}%".format(100.0 * n / total)


def _mean(values: list[float | int]) -> float:
    if not values:
        return 0.0
    return statistics.mean(values)


def summarize(rows: list[dict[str, Any]]) -> str:
    total = len(rows)
    if total == 0:
        return "No bug results found."

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("Experiment summary ({} bugs)".format(total))
    lines.append("=" * 60)

    outcome_counts = Counter(r.get("outcome", "UNKNOWN") for r in rows)
    fixed = outcome_counts.get("FIXED", 0)
    spec_failed = outcome_counts.get("SPEC_FAILED", 0)
    spec_success = sum(1 for r in rows if r.get("spec_success"))

    lines.append("")
    lines.append("--- Bug repair ---")
    lines.append("Fix rate: {} / {} ({})".format(fixed, total, _pct(fixed, total)))
    for outcome, count in sorted(outcome_counts.items()):
        lines.append("  {}: {} ({})".format(outcome, count, _pct(count, total)))

    lines.append("")
    lines.append("--- Spec pipeline ---")
    lines.append(
        "Spec success rate: {} / {} ({})".format(
            spec_success, total, _pct(spec_success, total)
        )
    )
    spec_fail_reasons = Counter(
        r.get("spec_failure_reason") or "unknown"
        for r in rows
        if r.get("outcome") == "SPEC_FAILED"
    )
    if spec_fail_reasons:
        lines.append("Spec failure reasons:")
        for reason, count in spec_fail_reasons.most_common():
            lines.append("  {}: {}".format(reason, count))

    spec_attempts = [
        r["spec_attempts_used"]
        for r in rows
        if r.get("spec_success") and isinstance(r.get("spec_attempts_used"), int)
    ]
    if spec_attempts:
        lines.append(
            "Spec attempts (successful bugs): min={}, max={}, mean={:.2f}".format(
                min(spec_attempts), max(spec_attempts), _mean(spec_attempts)
            )
        )

    verifier_checks = Counter(
        check
        for r in rows
        for check in ((r.get("spec_log_metrics") or {}).get("verifier") or {}).get(
            "checks_failed", []
        )
        if r.get("outcome") == "SPEC_FAILED"
    )
    if verifier_checks:
        lines.append("Spec verifier checks failed (SPEC_FAILED bugs):")
        for check, count in verifier_checks.most_common():
            lines.append("  {}: {}".format(check, count))

    fix_directions = Counter(
        ((r.get("spec_log_metrics") or {}).get("content") or {}).get("fix_direction")
        for r in rows
        if ((r.get("spec_log_metrics") or {}).get("content") or {}).get("fix_direction")
    )
    if fix_directions:
        lines.append("Spec fix_direction (bugs with spec):")
        for direction, count in fix_directions.most_common():
            lines.append("  {}: {}".format(direction, count))

    confidences = Counter(
        ((r.get("spec_log_metrics") or {}).get("content") or {}).get("confidence")
        for r in rows
        if ((r.get("spec_log_metrics") or {}).get("content") or {}).get("confidence")
    )
    if confidences:
        lines.append("Spec confidence:")
        for conf, count in confidences.most_common():
            lines.append("  {}: {}".format(conf, count))

    missing_javadoc = sum(
        1
        for r in rows
        if ((r.get("spec_log_metrics") or {}).get("evidence") or {}).get("javadoc_found") is False
    )
    if missing_javadoc:
        lines.append("Bugs without javadoc in spec evidence: {}".format(missing_javadoc))

    lines.append("")
    lines.append("--- Repair context (saved_contexts) ---")
    repair_ctx_rows = [r for r in rows if r.get("repair_context_metrics")]
    if repair_ctx_rows:
        final_states = Counter(
            r["repair_context_metrics"].get("final_state") for r in repair_ctx_rows
        )
        lines.append("Final FSM state:")
        for state, count in final_states.most_common():
            lines.append("  {}: {}".format(state, count))

        cmd_totals: Counter[str] = Counter()
        for r in repair_ctx_rows:
            for cmd, n in (r["repair_context_metrics"].get("command_counts") or {}).items():
                cmd_totals[cmd] += n
        if cmd_totals:
            lines.append("Top commands executed:")
            for cmd, count in cmd_totals.most_common(8):
                lines.append("  {}: {}".format(cmd, count))

        fixes_ctx = [
            r["repair_context_metrics"].get("suggested_fixes_count", 0)
            for r in repair_ctx_rows
        ]
        if fixes_ctx:
            lines.append(
                "Suggested fixes (from context): mean={:.1f}".format(_mean(fixes_ctx))
            )
    else:
        lines.append("  (no repair context — all SPEC_FAILED or no saved_context)")

    lines.append("")
    lines.append("--- Repair failures (excluding SPEC_FAILED) ---")
    repair_fail_reasons = Counter(
        r.get("repair_failure_reason") or "unknown"
        for r in rows
        if r.get("repair_ran") and r.get("outcome") != "FIXED"
    )
    if repair_fail_reasons:
        for reason, count in repair_fail_reasons.most_common():
            short = (reason[:120] + "...") if len(str(reason)) > 120 else reason
            lines.append("  [{}x] {}".format(count, short))
    else:
        lines.append("  (none)")

    repair_cycles = [
        r["repair_cycles_used"]
        for r in rows
        if r.get("repair_ran") and isinstance(r.get("repair_cycles_used"), int)
    ]

    lines.append("")
    lines.append("--- Repair cycles (per bug) ---")
    fixed_bugs = [
        r for r in rows
        if r.get("outcome") == "FIXED" and isinstance(r.get("repair_cycles_used"), int)
    ]
    if fixed_bugs:
        lines.append("Fixed bugs (repair_cycles_used):")
        for r in sorted(fixed_bugs, key=lambda x: (x.get("project", ""), str(x.get("bug_index", "")))):
            lines.append(
                "  {project} {bug_index}: {cycles} cycles".format(
                    project=r.get("project"),
                    bug_index=r.get("bug_index"),
                    cycles=r.get("repair_cycles_used"),
                )
            )
    else:
        lines.append("  (no FIXED bugs)")

    if repair_cycles:
        lines.append(
            "All repair runs: min={}, max={}, mean={:.1f}".format(
                min(repair_cycles), max(repair_cycles), _mean(repair_cycles)
            )
        )

    plan_rows = [r for r in rows if (r.get("plan_localization") or {}).get("available")]
    lines.append("")
    lines.append("--- Plan localization (fix_targets vs buggy-lines) ---")
    if plan_rows:
        for r in sorted(plan_rows, key=lambda x: (x.get("project", ""), str(x.get("bug_index", "")))):
            pl = r.get("plan_localization") or {}
            lines.append(
                "  {project} {bug_index}: recall={recall}, precision={precision}, "
                "jaccard={jaccard}, top1={top1}, overlap={overlap}/{gt}".format(
                    project=r.get("project"),
                    bug_index=r.get("bug_index"),
                    recall=pl.get("recall"),
                    precision=pl.get("precision"),
                    jaccard=pl.get("jaccard"),
                    top1=pl.get("top1_hit"),
                    overlap=pl.get("overlap_line_count"),
                    gt=pl.get("gt_source_line_count") or pl.get("gt_line_count"),
                )
            )
        recalls = [pl["recall"] for r in plan_rows if (pl := r.get("plan_localization") or {}).get("recall") is not None]
        precisions = [pl["precision"] for r in plan_rows if (pl := r.get("plan_localization") or {}).get("precision") is not None]
        jaccards = [pl["jaccard"] for r in plan_rows if (pl := r.get("plan_localization") or {}).get("jaccard") is not None]
        if recalls:
            lines.append(
                "Experiment averages: recall={:.3f}, precision={:.3f}, jaccard={:.3f} (over {} bugs)".format(
                    _mean(recalls), _mean(precisions) if precisions else 0.0,
                    _mean(jaccards) if jaccards else 0.0, len(plan_rows)
                )
            )
    else:
        lines.append("  (no plan localization data)")

    lines.append("")
    lines.append("--- Cost & time ---")
    elapsed = [r["elapsed_seconds"] for r in rows if isinstance(r.get("elapsed_seconds"), (int, float))]
    tokens = [r["total_tokens"] for r in rows if isinstance(r.get("total_tokens"), int)]
    costs = [r["cost_usd"] for r in rows if isinstance(r.get("cost_usd"), (int, float))]
    if elapsed:
        lines.append(
            "Elapsed (s): total={:.1f}, mean={:.1f}".format(sum(elapsed), _mean(elapsed))
        )
    if tokens:
        lines.append(
            "Tokens: total={}, mean={:.0f}".format(sum(tokens), _mean(tokens))
        )
    if costs:
        lines.append(
            "Cost (USD): total=${:.4f}, mean=${:.4f}".format(sum(costs), _mean(costs))
        )

    lines.append("")
    lines.append("--- Per-bug ---")
    for r in rows:
        pl = r.get("plan_localization") or {}
        lines.append(
            "  {project} {bug_index}: outcome={outcome}, spec_attempts={spec_attempts_used}, "
            "repair_cycles={repair_cycles_used}, recall={recall}, precision={precision}, "
            "jaccard={jaccard}, cost=${cost_usd}, elapsed={elapsed_seconds}s".format(
                project=r.get("project"),
                bug_index=r.get("bug_index"),
                outcome=r.get("outcome"),
                spec_attempts_used=r.get("spec_attempts_used"),
                repair_cycles_used=r.get("repair_cycles_used"),
                recall=pl.get("recall"),
                precision=pl.get("precision"),
                jaccard=pl.get("jaccard"),
                cost_usd=r.get("cost_usd", 0),
                elapsed_seconds=r.get("elapsed_seconds", 0),
            )
        )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "experiment",
        help="Experiment folder name (e.g. experiment_42) or path under experimental_setups/",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="",
        help="Optional path to write summary text file",
    )
    args = parser.parse_args()

    exp = args.experiment
    if not os.path.isdir(exp):
        exp = os.path.join("experimental_setups", exp)
    results_path = os.path.join(exp, "bug_results.jsonl")

    if not os.path.isfile(results_path):
        raise SystemExit("Not found: {}".format(results_path))

    rows = _load_bug_results(results_path)
    report = summarize(rows)
    print(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(report + "\n")
        print("\nWrote summary to {}".format(args.output))
    else:
        summary_path = os.path.join(exp, "experiment_summary.txt")
        with open(summary_path, "w", encoding="utf-8") as handle:
            handle.write(report + "\n")
        print("\nWrote summary to {}".format(summary_path))


if __name__ == "__main__":
    main()
