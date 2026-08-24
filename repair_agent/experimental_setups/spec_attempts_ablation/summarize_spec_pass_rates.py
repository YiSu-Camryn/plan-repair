#!/usr/bin/env python3
"""Summarize spec pass@k rates from a RepairAgent spec-only experiment."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


def load_bug_results(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _pct(n: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{100.0 * n / total:.1f}%"


def pass_at_k(rows: list[dict[str, Any]], k: int) -> tuple[int, int]:
    total = len(rows)
    passed = 0
    for row in rows:
        if not row.get("spec_success"):
            continue
        attempts = row.get("spec_attempts_used")
        if attempts is None:
            continue
        if int(attempts) <= k:
            passed += 1
    return passed, total


def summarize_rows(
    rows: list[dict[str, Any]],
    ks: Iterable[int] = (2, 3, 4, 5),
) -> dict[str, Any]:
    total = len(rows)
    if total == 0:
        return {"total_bugs": 0, "pass_rates": [], "error": "no rows"}

    max_attempts_values = {
        int(r["spec_max_attempts"])
        for r in rows
        if r.get("spec_max_attempts") is not None
    }
    spec_max_attempts = max(max_attempts_values) if max_attempts_values else None

    pass_rates = []
    prev_passed = 0
    for k in ks:
        passed, _ = pass_at_k(rows, k)
        pass_rates.append(
            {
                "k": k,
                "passed": passed,
                "total": total,
                "rate": passed / total if total else 0.0,
                "rate_pct": _pct(passed, total),
                "delta_from_prev": passed - prev_passed,
                "delta_from_prev_pct": _pct(passed - prev_passed, total),
            }
        )
        prev_passed = passed

    final_success = sum(1 for r in rows if r.get("spec_success"))
    attempt_histogram = Counter(
        int(r["spec_attempts_used"])
        for r in rows
        if r.get("spec_success") and r.get("spec_attempts_used") is not None
    )
    failure_reasons = Counter(
        r.get("spec_failure_reason") or "unknown"
        for r in rows
        if not r.get("spec_success")
    )

    successful_attempts = [
        int(r["spec_attempts_used"])
        for r in rows
        if r.get("spec_success") and r.get("spec_attempts_used") is not None
    ]
    attempt_stats = {}
    if successful_attempts:
        attempt_stats = {
            "min": min(successful_attempts),
            "max": max(successful_attempts),
            "mean": round(statistics.mean(successful_attempts), 2),
        }

    by_batch: dict[str, dict[str, Any]] = {}
    for row in rows:
        batch = str(row.get("batch", "unknown"))
        bucket = by_batch.setdefault(
            batch,
            {"total": 0, "pass_at_5": 0, "pass_at_4": 0, "pass_at_3": 0, "pass_at_2": 0},
        )
        bucket["total"] += 1
        if row.get("spec_success"):
            attempts = int(row.get("spec_attempts_used") or 999)
            if attempts <= 5:
                bucket["pass_at_5"] += 1
            if attempts <= 4:
                bucket["pass_at_4"] += 1
            if attempts <= 3:
                bucket["pass_at_3"] += 1
            if attempts <= 2:
                bucket["pass_at_2"] += 1

    return {
        "total_bugs": total,
        "spec_max_attempts": spec_max_attempts,
        "final_spec_success": final_success,
        "final_spec_success_pct": _pct(final_success, total),
        "pass_rates": pass_rates,
        "attempt_histogram": dict(sorted(attempt_histogram.items())),
        "attempt_stats_successful": attempt_stats,
        "failure_reasons": dict(failure_reasons.most_common()),
        "by_batch": by_batch,
    }


def summarize_file(results_path: Path, ks: Iterable[int] = (2, 3, 4, 5)) -> dict[str, Any]:
    rows = load_bug_results(results_path)
    summary = summarize_rows(rows, ks=ks)
    summary["bug_results_path"] = str(results_path.resolve())
    return summary


def write_summary(output_dir: Path, summary: dict[str, Any]) -> None:
    json_path = output_dir / "spec_pass_rates.json"
    txt_path = output_dir / "spec_pass_rates.txt"

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    lines = [
        "=" * 60,
        "Spec pass@k summary ({} bugs)".format(summary.get("total_bugs", 0)),
        "=" * 60,
        "Source: {}".format(summary.get("bug_results_path", "")),
        "Run max_attempts: {}".format(summary.get("spec_max_attempts", "?")),
        "",
        "pass@k (bug passes if spec_success and attempts_used <= k):",
    ]
    for row in summary.get("pass_rates", []):
        delta = row.get("delta_from_prev", 0)
        delta_str = f" (+{delta}, +{row.get('delta_from_prev_pct', '0.0%')})" if delta else ""
        lines.append(
            "  pass@{k}: {passed}/{total} ({rate_pct}){delta}".format(
                k=row["k"],
                passed=row["passed"],
                total=row["total"],
                rate_pct=row["rate_pct"],
                delta=delta_str,
            )
        )

    lines.append("")
    lines.append(
        "Final spec success (pass@{}): {} ({})".format(
            summary.get("spec_max_attempts", 5),
            summary.get("final_spec_success", 0),
            summary.get("final_spec_success_pct", "0.0%"),
        )
    )

    hist = summary.get("attempt_histogram") or {}
    if hist:
        lines.append("")
        lines.append("Successful bugs by attempt_used:")
        for attempt, count in sorted(hist.items()):
            lines.append(f"  attempt {attempt}: {count}")

    reasons = summary.get("failure_reasons") or {}
    if reasons:
        lines.append("")
        lines.append("Failure reasons:")
        for reason, count in reasons.items():
            lines.append(f"  {reason}: {count}")

    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(summary: dict[str, Any]) -> None:
    print("=" * 60)
    print("Spec pass@k summary ({} bugs)".format(summary.get("total_bugs", 0)))
    print("=" * 60)
    for row in summary.get("pass_rates", []):
        delta = row.get("delta_from_prev", 0)
        extra = f"  (+{delta})" if delta else ""
        print(
            "pass@{k}: {passed}/{total} ({rate_pct}){extra}".format(
                k=row["k"],
                passed=row["passed"],
                total=row["total"],
                rate_pct=row["rate_pct"],
                extra=extra,
            )
        )
    print(
        "final: {}/{} ({})".format(
            summary.get("final_spec_success", 0),
            summary.get("total_bugs", 0),
            summary.get("final_spec_success_pct", "0.0%"),
        )
    )


def merge_batch_labels(
    summary: dict[str, Any],
    sample_json: Path | None,
) -> dict[str, Any]:
    if not sample_json or not sample_json.is_file():
        return summary

    with open(sample_json, encoding="utf-8") as handle:
        sample = json.load(handle)

    batch_by_key = {b["bug_key"]: b["batch"] for b in sample.get("bugs", [])}
    results_path = Path(summary.get("bug_results_path", ""))
    if not results_path.is_file():
        return summary

    rows = load_bug_results(results_path)
    for row in rows:
        key = row.get("bug_key") or f"{row.get('project')}-{row.get('bug_index')}"
        if key in batch_by_key:
            row["batch"] = batch_by_key[key]

    return summarize_rows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        help="bug_results.jsonl or experiment output directory",
    )
    parser.add_argument(
        "--sample-json",
        default="",
        help="sample_40.json for per-batch breakdown",
    )
    parser.add_argument(
        "--ks",
        default="2,3,4,5",
        help="Comma-separated k values for pass@k (default: 2,3,4,5)",
    )
    return parser


def resolve_results_path(path_arg: str) -> Path:
    path = Path(path_arg)
    if path.is_dir():
        candidate = path / "bug_results.jsonl"
        if not candidate.is_file():
            raise SystemExit(f"No bug_results.jsonl in {path}")
        return candidate
    if not path.is_file():
        raise SystemExit(f"Not found: {path}")
    return path


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    ablation_dir = Path(__file__).resolve().parent
    if not args.path:
        runs = ablation_dir / "runs"
        if not runs.is_dir():
            parser.error("Provide path to bug_results.jsonl or run directory")
        candidates = sorted(runs.glob("*/bug_results.jsonl"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            parser.error("No runs found under {}".format(runs))
        results_path = candidates[-1]
        output_dir = results_path.parent
        print(f"Using latest run: {results_path}")
    else:
        results_path = resolve_results_path(args.path)
        output_dir = results_path.parent

    ks = tuple(int(x.strip()) for x in args.ks.split(",") if x.strip())
    summary = summarize_file(results_path, ks=ks)

    sample_json = Path(args.sample_json) if args.sample_json else ablation_dir / "sample_40.json"
    if sample_json.is_file():
        summary = merge_batch_labels(summary, sample_json)
        summary["bug_results_path"] = str(results_path.resolve())

    write_summary(output_dir, summary)
    print_summary(summary)
    print(f"\nWrote {output_dir / 'spec_pass_rates.json'}")
    print(f"Wrote {output_dir / 'spec_pass_rates.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
