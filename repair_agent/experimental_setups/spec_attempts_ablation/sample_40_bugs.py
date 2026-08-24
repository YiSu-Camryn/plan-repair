#!/usr/bin/env python3
"""Stratified random sample: 8 bugs from each of batches 0-4 (40 total)."""

from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BATCH_DIR = ROOT / "experimental_setups" / "batches"
SF_PATH = ROOT.parent / "ReInFix" / "D4J_dataset" / "defects4j-sf.json"
OUT_DIR = Path(__file__).resolve().parent
OUT_TXT = OUT_DIR / "sample_40.txt"
OUT_JSON = OUT_DIR / "sample_40.json"

SEED = 42
PER_BATCH = 8


def load_batch(batch_id: int) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in (BATCH_DIR / str(batch_id)).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        project, bug_index = parts[0], parts[1]
        rows.append((project, bug_index, f"{project}-{bug_index}"))
    return rows


def main() -> None:
    with open(SF_PATH, encoding="utf-8") as handle:
        sf_keys = set(json.load(handle).keys())

    random.seed(SEED)
    selected: list[dict] = []

    for batch_id in range(5):
        bugs = load_batch(batch_id)
        in_sf = [b for b in bugs if b[2] in sf_keys]
        pool = in_sf if len(in_sf) >= PER_BATCH else bugs
        if len(pool) < PER_BATCH:
            raise SystemExit(
                f"batch {batch_id}: only {len(pool)} bugs available, need {PER_BATCH}"
            )
        pick = random.sample(pool, PER_BATCH)
        for project, bug_index, bug_key in pick:
            selected.append(
                {
                    "batch": batch_id,
                    "project": project,
                    "bug_index": bug_index,
                    "bug_key": bug_key,
                    "in_sf_dataset": bug_key in sf_keys,
                }
            )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_TXT, "w", encoding="utf-8") as handle:
        for row in selected:
            handle.write(f"{row['project']} {row['bug_index']}\n")

    with open(OUT_JSON, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "seed": SEED,
                "per_batch": PER_BATCH,
                "total": len(selected),
                "bugs": selected,
            },
            handle,
            indent=2,
        )
        handle.write("\n")

    print(f"Wrote {len(selected)} bugs to {OUT_TXT}")
    for row in selected:
        sf = "Y" if row["in_sf_dataset"] else "N"
        print(f"  batch {row['batch']}: {row['bug_key']} (sf={sf})")


if __name__ == "__main__":
    main()
