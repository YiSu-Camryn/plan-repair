#!/usr/bin/env python3
"""Classify Defects4J bugs as single-line, multi-line, or multi-file.

Uses the official developer source patch:
  defects4j/framework/projects/<Project>/patches/<id>.src.patch

Classification (per bug, based on src patch only):
  - multi-file   : patch touches >= 2 source files
  - single-line  : exactly 1 file, max(added_lines, removed_lines) <= 1
  - multi-line   : exactly 1 file, max(added_lines, removed_lines) > 1

This matches the common APR paper convention:
  a one-line modification counts as single-line even though the diff
  shows one '-' and one '+' line.

Usage (from repair_agent/ with defects4j checkout present):
  python experimental_setups/classify_defects4j_patch_size.py
  python experimental_setups/classify_defects4j_patch_size.py --output data/d4j_patch_size.csv
  python experimental_setups/classify_defects4j_patch_size.py --list multi-file
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
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

PROJECT_ORDER = list(N_BUGS.keys())


def parse_patch_stats(patch_path: Path) -> dict:
    """Return file/line stats from a unified diff patch."""
    text = patch_path.read_text(encoding="utf-8", errors="replace")

    try:
        import whatthepatch

        per_file = []
        for diff in whatthepatch.parse_patch(text):
            added = removed = 0
            for change in diff.changes:
                if change.old is None and change.new is not None:
                    added += 1
                elif change.old is not None and change.new is None:
                    removed += 1
                elif change.old is not None and change.new is not None:
                    added += 1
                    removed += 1
            header = getattr(diff, "header", None)
            filename = ""
            if header is not None:
                filename = getattr(header, "old_path", "") or getattr(header, "new_path", "")
            per_file.append(
                {
                    "file": filename,
                    "added": added,
                    "removed": removed,
                    "changed": max(added, removed),
                }
            )
    except Exception:
        # Fallback: line-based parsing without whatthepatch
        per_file = _parse_patch_fallback(text)

    num_files = len(per_file)
    total_added = sum(f["added"] for f in per_file)
    total_removed = sum(f["removed"] for f in per_file)
    max_changed = max((f["changed"] for f in per_file), default=0)

    if num_files >= 2:
        category = "multi-file"
    elif num_files == 1 and max_changed <= 1:
        category = "single-line"
    elif num_files == 1:
        category = "multi-line"
    else:
        category = "unknown"

    return {
        "num_files": num_files,
        "added": total_added,
        "removed": total_removed,
        "max_changed_per_file": max_changed,
        "category": category,
        "files": per_file,
    }


def _parse_patch_fallback(text: str) -> list[dict]:
    files = []
    current = None
    added = removed = 0

    def flush():
        nonlocal current, added, removed
        if current is not None:
            files.append(
                {
                    "file": current,
                    "added": added,
                    "removed": removed,
                    "changed": max(added, removed),
                }
            )
        current = None
        added = removed = 0

    for line in text.splitlines():
        if line.startswith("diff --git"):
            flush()
            parts = line.split()
            if len(parts) >= 3:
                current = parts[2].lstrip("a/").lstrip("b/")
            continue
        if current is None:
            continue
        if line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1

    flush()
    return files


def iter_bugs(projects_root: Path):
    for project in PROJECT_ORDER:
        for bug_id in range(1, N_BUGS[project] + 1):
            patch = projects_root / project / "patches" / f"{bug_id}.src.patch"
            yield project, bug_id, patch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--defects4j-root",
        default="defects4j/framework/projects",
        help="Path to defects4j/framework/projects (default: defects4j/framework/projects)",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional CSV output path",
    )
    parser.add_argument(
        "--list",
        choices=["single-line", "multi-line", "multi-file", "unknown"],
        help="Print only bugs in one category",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parents[1]
    os.chdir(script_dir)

    projects_root = Path(args.defects4j_root)
    if not projects_root.is_dir():
        print(
            "ERROR: defects4j projects dir not found: {}\n"
            "Run from repair_agent/ after checking out defects4j, e.g.:\n"
            "  cd repair_agent && git clone https://github.com/rjust/defects4j.git\n"
            "  cd defects4j && ./init.sh".format(projects_root.resolve()),
            file=sys.stderr,
        )
        return 1

    rows = []
    missing = []
    by_category = Counter()
    by_project = defaultdict(lambda: Counter())

    for project, bug_id, patch_path in iter_bugs(projects_root):
        bug_name = f"{project} {bug_id}"
        if not patch_path.is_file():
            missing.append(bug_name)
            continue

        stats = parse_patch_stats(patch_path)
        row = {
            "project": project,
            "bug_id": bug_id,
            "bug": bug_name,
            "category": stats["category"],
            "num_files": stats["num_files"],
            "added": stats["added"],
            "removed": stats["removed"],
            "max_changed_per_file": stats["max_changed_per_file"],
        }
        rows.append(row)
        by_category[stats["category"]] += 1
        by_project[project][stats["category"]] += 1

    total = len(rows)
    print("Defects4J patch-size classification")
    print("Source: {}/*.src.patch".format(projects_root))
    print("Total classified: {} / {}".format(total, sum(N_BUGS.values())))
    if missing:
        print("Missing patches: {}".format(len(missing)))
    print()

    print("Overall")
    print("-" * 40)
    for cat in ("single-line", "multi-line", "multi-file", "unknown"):
        n = by_category[cat]
        pct = 100.0 * n / total if total else 0.0
        print("{:12s} {:4d}  ({:5.1f}%)".format(cat, n, pct))
    print()

    print("By project")
    print("-" * 72)
    print(
        "{:<16} {:>5} {:>12} {:>11} {:>11}".format(
            "Project", "Total", "single-line", "multi-line", "multi-file"
        )
    )
    for project in PROJECT_ORDER:
        c = by_project[project]
        n = sum(c.values())
        if n == 0:
            continue
        print(
            "{:<16} {:5d} {:12d} {:11d} {:11d}".format(
                project,
                n,
                c["single-line"],
                c["multi-line"],
                c["multi-file"],
            )
        )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(
                fp,
                fieldnames=[
                    "project",
                    "bug_id",
                    "bug",
                    "category",
                    "num_files",
                    "added",
                    "removed",
                    "max_changed_per_file",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)
        print()
        print("Wrote CSV: {}".format(out_path.resolve()))

    if args.list:
        print()
        print("Bugs in category: {}".format(args.list))
        for row in rows:
            if row["category"] == args.list:
                print(row["bug"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
