"""Plan localization: fix_targets vs Defects4J buggy-lines ground truth."""

from __future__ import annotations

import os
import re
from typing import Any, Optional

from autogpt.bug_log_metrics import _resolve_spec_json


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def load_gt_buggy_lines(project: str, bug_index: str) -> dict[str, Any]:
    """Load ground-truth buggy lines from defects4j/buggy-lines."""
    path = os.path.join(
        "defects4j", "buggy-lines", "{}-{}.buggy.lines".format(project, bug_index)
    )
    gt_by_file: dict[str, set[int]] = {}
    if not os.path.isfile(path):
        return {
            "gt_line_count": 0,
            "gt_files": [],
            "gt_lines_by_file": {},
            "gt_lines": [],
        }

    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            parts = raw.split("#")
            if len(parts) < 2:
                continue
            file_path = _normalize_path(parts[0])
            try:
                line_num = int(parts[1])
            except ValueError:
                continue
            gt_by_file.setdefault(file_path, set()).add(line_num)

    all_lines = sorted({(f, ln) for f, lines in gt_by_file.items() for ln in lines})
    return {
        "gt_line_count": len(all_lines),
        "gt_files": sorted(gt_by_file.keys()),
        "gt_lines_by_file": {f: sorted(lines) for f, lines in gt_by_file.items()},
        "gt_lines": ["{}:{}".format(f, ln) for f, ln in all_lines],
    }


def _parse_line_value(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"\d+", text)
    if not match:
        return None
    try:
        return int(match.group())
    except ValueError:
        return None


def extract_pred_lines(spec_json: Optional[dict[str, Any]]) -> set[int]:
    """Extract predicted fix target line numbers from spec JSON."""
    if not spec_json or not isinstance(spec_json, dict):
        return set()

    lines: set[int] = set()
    top = _parse_line_value(spec_json.get("fix_target_line"))
    if top is not None:
        lines.add(top)

    for target in spec_json.get("fix_targets") or []:
        if not isinstance(target, dict):
            continue
        line = _parse_line_value(target.get("line"))
        if line is not None:
            lines.add(line)

    return lines


def _gt_line_number_set(gt_by_file: dict[str, set[int]]) -> set[int]:
    result: set[int] = set()
    for file_lines in gt_by_file.values():
        result.update(file_lines)
    return result


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def compute_plan_localization_overlap(
    project: str,
    bug_index: str,
    spec_json: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Compute overlap between plan fix_targets and GT buggy-lines.

    Metrics (line-level, source files from GT only):
    - recall: |GT ∩ Pred| / |GT|
    - precision: |GT ∩ Pred| / |Pred|
    - jaccard: |GT ∩ Pred| / |GT ∪ Pred|
    - top1_hit: fix_target_line matches a GT line on a GT source file
    """
    gt_data = load_gt_buggy_lines(project, bug_index)
    gt_by_file = {
        f: set(lines) for f, lines in (gt_data.get("gt_lines_by_file") or {}).items()
    }
    gt_tuples = {(f, ln) for f, lines in gt_by_file.items() for ln in lines}
    gt_line_nums = _gt_line_number_set(gt_by_file)

    pred_lines = extract_pred_lines(spec_json)
    if not gt_tuples:
        return {
            "available": False,
            "reason": "no_ground_truth",
            "gt_line_count": 0,
            "pred_line_count": len(pred_lines),
            "overlap_line_count": 0,
            "recall": None,
            "precision": None,
            "jaccard": None,
            "top1_hit": None,
            "matched_lines": [],
            "missed_gt_lines": [],
            "extra_pred_lines": sorted(pred_lines),
            "invalid_pred_line_count": len(pred_lines),
        }

    if not pred_lines:
        return {
            "available": True,
            "reason": None,
            "gt_line_count": len(gt_tuples),
            "pred_line_count": 0,
            "overlap_line_count": 0,
            "recall": 0.0 if gt_tuples else None,
            "precision": None,
            "jaccard": 0.0 if gt_tuples else None,
            "top1_hit": False,
            "matched_lines": [],
            "missed_gt_lines": gt_data.get("gt_lines", []),
            "extra_pred_lines": [],
            "invalid_pred_line_count": 0,
        }

    # Pred line matches GT if that line number appears on any GT source file.
    overlap_line_nums = {ln for ln in pred_lines if ln in gt_line_nums}
    invalid_pred_lines = sorted(pred_lines - overlap_line_nums)

    matched_gt = sorted(
        (f, ln) for f, ln in gt_tuples if ln in overlap_line_nums
    )
    missed_gt = sorted((f, ln) for f, ln in gt_tuples if ln not in overlap_line_nums)

    overlap_count = len(overlap_line_nums)
    recall = _ratio(overlap_count, len(gt_line_nums))
    precision = _ratio(overlap_count, len(pred_lines))
    union_size = len(gt_line_nums | pred_lines)
    jaccard = _ratio(overlap_count, union_size)

    top1 = _parse_line_value(spec_json.get("fix_target_line") if spec_json else None)
    top1_hit = top1 in gt_line_nums if top1 is not None else False

    return {
        "available": True,
        "reason": None,
        "gt_line_count": len(gt_tuples),
        "gt_source_line_count": len(gt_line_nums),
        "pred_line_count": len(pred_lines),
        "overlap_line_count": overlap_count,
        "recall": recall,
        "precision": precision,
        "jaccard": jaccard,
        "top1_hit": top1_hit,
        "matched_lines": ["{}:{}".format(f, ln) for f, ln in matched_gt],
        "missed_gt_lines": ["{}:{}".format(f, ln) for f, ln in missed_gt],
        "extra_pred_lines": invalid_pred_lines,
        "invalid_pred_line_count": len(invalid_pred_lines),
    }


def extract_plan_localization_metrics(
    exp_dir: Optional[str],
    project: str,
    bug_index: str,
    spec_result: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Load spec JSON and compute plan vs GT overlap for bug_results."""
    spec_json = _resolve_spec_json(exp_dir, project, bug_index, spec_result)
    if not spec_json:
        return {
            "available": False,
            "reason": "no_spec_json",
            "gt_line_count": load_gt_buggy_lines(project, bug_index)["gt_line_count"],
            "pred_line_count": 0,
            "overlap_line_count": 0,
            "recall": None,
            "precision": None,
            "jaccard": None,
            "top1_hit": None,
            "matched_lines": [],
            "missed_gt_lines": load_gt_buggy_lines(project, bug_index).get("gt_lines", []),
            "extra_pred_lines": [],
            "invalid_pred_line_count": 0,
        }
    return compute_plan_localization_overlap(project, bug_index, spec_json)
