#!/usr/bin/env python3
"""Classify bugs using data/buggy-lines/*.buggy.lines (fault localization metadata).

This measures LOCALIZATION SPREAD, not developer patch size.
See docstring in main() for caveats vs *.src.patch classification.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

N_BUGS = {
    "Chart": 26,
    "Cli": 40,
    "Closure": 176,
    "Codec": 18,
    "Collections": 28,
    "Compress": 47,
    "Csv": 16,
    "Gson": 18,
    "JacksonCore": 26,
    "JacksonDatabind": 112,
    "JacksonXml": 6,
    "Jsoup": 93,
    "JxPath": 22,
    "Lang": 65,
    "Math": 106,
    "Mockito": 38,
    "Time": 27,
}

MARKERS = {"FAULT_OF_OMISSION", "MISSING_RANKING_STATEMENT"}


def parse_buggy_lines(path: Path) -> dict[str, list[tuple[str, str]]]:
    files: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split("#", 2)
        if len(parts) < 3:
            continue
        files[parts[0]].append((parts[1], parts[2].strip()))
    return files


def count_code_lines(files: dict, count_markers: bool) -> int:
    n = 0
    for entries in files.values():
        for _lno, content in entries:
            if content in MARKERS:
                if count_markers:
                    n += 1
            else:
                n += 1
    return n


def classify(files: dict, count_markers: bool) -> tuple[str, int, int]:
    n_files = len(files)
    n_lines = count_code_lines(files, count_markers)
    if n_files >= 2:
        return "multi-file", n_files, n_lines
    if n_lines <= 1:
        return "single-line", n_files, n_lines
    return "multi-line", n_files, n_lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--buggy-lines-dir",
        default="../data/buggy-lines",
        help="Directory containing Project-N.buggy.lines files",
    )
    parser.add_argument("--count-markers", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    buggy_dir = (script_dir / args.buggy_lines_dir).resolve()

    rows = []
    missing = []
    for project, max_id in N_BUGS.items():
        for bug_id in range(1, max_id + 1):
            path = buggy_dir / f"{project}-{bug_id}.buggy.lines"
            if not path.is_file():
                missing.append(f"{project} {bug_id}")
                continue
            files = parse_buggy_lines(path)
            category, n_files, n_lines = classify(files, args.count_markers)
            rows.append(
                {
                    "project": project,
                    "bug_id": bug_id,
                    "bug": f"{project} {bug_id}",
                    "category": category,
                    "num_files": n_files,
                    "num_lines": n_lines,
                }
            )

    total = len(rows)
    by_cat = Counter(r["category"] for r in rows)
    print("buggy-lines localization classification")
    print("Directory:", buggy_dir)
    print("Bugs classified:", total, "/ 864")
    print("Missing files:", len(missing))
    print("Count FAULT_OF_OMISSION as line:", args.count_markers)
    print()
    for cat in ("single-line", "multi-line", "multi-file"):
        n = by_cat[cat]
        pct = 100.0 * n / total if total else 0.0
        print(f"  {cat:12s} {n:4d}  ({pct:5.1f}%)")

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(
                fp,
                fieldnames=["project", "bug_id", "bug", "category", "num_files", "num_lines"],
            )
            writer.writeheader()
            writer.writerows(rows)
        print("\nWrote", out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
