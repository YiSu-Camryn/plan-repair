"""Step 2 environment checks for ReInFix spec adapter (no LLM calls)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

from spec_integration.bootstrap import setup_environment
from spec_integration.paths import (
    dataset_sf_path,
    hyperparams_path,
    reinfix_root,
    repairagent_src,
)
from spec_integration.spec_adapter import (
    build_spec_inputs,
    has_spec_checkout,
    joern_checkout_link,
    joern_project_name,
    load_dataset_entry,
    parse_bug_id,
    spec_checkout_dir,
)

OPTIONAL_CHECK_NAMES = frozenset({"api_key"})


def _status(ok: bool, message: str) -> dict[str, Any]:
    return {"ok": ok, "message": message}


def check_repairagent_root() -> dict[str, Any]:
    repair = repairagent_src()
    if not repair.is_dir():
        return _status(
            False,
            "RepairAgent not found at {} (set REPAIRAGENT_SRC)".format(repair),
        )
    d4j = repair / "defects4j"
    if not d4j.is_dir():
        return _status(False, "Missing defects4j under {}".format(repair))
    return _status(True, "RepairAgent root: {}".format(repair))


def check_dataset(bug_name: str = "Chart-1") -> dict[str, Any]:
    path = dataset_sf_path()
    if not path.is_file():
        return _status(False, "Dataset missing: {}".format(path))
    try:
        entry = load_dataset_entry(bug_name)
    except KeyError:
        return _status(False, "Bug {} not in {}".format(bug_name, path))
    except OSError as exc:
        return _status(False, "Cannot read dataset: {}".format(exc))
    if not entry.get("buggy_fl") and not entry.get("buggy"):
        return _status(False, "Dataset entry {} has no buggy code".format(bug_name))
    return _status(True, "Dataset OK for {} ({} fields)".format(bug_name, len(entry)))


def check_hyperparams() -> dict[str, Any]:
    path = hyperparams_path()
    if not path.is_file():
        return _status(False, "Missing {}".format(path))
    return _status(True, "hyperparams: {}".format(path))


def check_bootstrap() -> dict[str, Any]:
    try:
        setup_environment(verify=True)
        sample = reinfix_root() / "defects4j" / "buggy-lines" / "Chart-1.buggy.lines"
        return _status(
            True,
            "Symlinks OK; sample GT: {} ({} bytes)".format(
                sample, sample.stat().st_size if sample.is_file() else 0
            ),
        )
    except Exception as exc:
        return _status(False, str(exc))


def check_defects4j_cli() -> dict[str, Any]:
    """Run after bootstrap so framework/bin is on PATH."""
    cmd = shutil.which("defects4j")
    if cmd:
        return _status(True, "defects4j on PATH: {}".format(cmd))

    root = reinfix_root()
    for base in (root / "defects4j", repairagent_src() / "defects4j"):
        for name in ("defects4j", "defects4j.bat"):
            candidate = base / "framework" / "bin" / name
            if candidate.is_file():
                return _status(
                    False,
                    "defects4j found at {} but not on PATH; bootstrap should add it".format(
                        candidate
                    ),
                )
    return _status(False, "defects4j not found on PATH or under ReInFix/RepairAgent")


def check_adapter_exports() -> dict[str, Any]:
    try:
        import spec_integration

        missing = [name for name in spec_integration.__all__ if not hasattr(spec_integration, name)]
        if missing:
            return _status(False, "Missing spec_integration exports: {}".format(", ".join(missing)))
        return _status(True, "{} public adapter exports importable".format(len(spec_integration.__all__)))
    except Exception as exc:
        return _status(False, str(exc))


def check_adapter_inputs(bug_name: str = "Chart-1") -> dict[str, Any]:
    """Dry-run dataset -> generate_spec kwargs mapping (no LLM)."""
    try:
        entry = load_dataset_entry(bug_name)
        inputs = build_spec_inputs(
            bug_name,
            entry,
            model="gpt-4o-mini",
            run_tests=False,
            use_d4j_info=False,
        )
        required = (
            "project_name",
            "bug_index",
            "localization_info",
            "test_results",
            "model",
            "workspace",
            "max_attempts",
        )
        missing = [key for key in required if key not in inputs]
        if missing:
            return _status(False, "build_spec_inputs missing keys: {}".format(", ".join(missing)))
        if not str(inputs["localization_info"]).strip():
            return _status(False, "build_spec_inputs produced empty localization_info")
        if not str(inputs["test_results"]).strip():
            return _status(False, "build_spec_inputs produced empty test_results")
        return _status(
            True,
            "build_spec_inputs OK (localization={} chars, test_results={} chars)".format(
                len(str(inputs["localization_info"])),
                len(str(inputs["test_results"])),
            ),
        )
    except Exception as exc:
        return _status(False, str(exc))


def check_checkout_layout(bug_name: str = "Chart-1") -> dict[str, Any]:
    project, bug_index = parse_bug_id(bug_name)
    checkout = spec_checkout_dir(project, bug_index)
    joern_link = joern_checkout_link(project, bug_index)
    joern_id = joern_project_name(project, bug_index)
    lines = [
        "spec checkout: {}".format(checkout),
        "joern project id: {}".format(joern_id),
        "joern link path: {}".format(joern_link),
    ]
    if has_spec_checkout(project, bug_index):
        lines.append("existing spec checkout found")
    else:
        lines.append("spec checkout not present (smoke test will create)")
    return _status(True, "; ".join(lines))


def check_joern_link(bug_name: str = "Chart-1") -> dict[str, Any]:
    project, bug_index = parse_bug_id(bug_name)
    spec_path = spec_checkout_dir(project, bug_index)
    link_path = joern_checkout_link(project, bug_index)

    if not link_path.exists() and not link_path.is_symlink():
        return _status(True, "Joern link not created yet (expected before ReAct)")

    try:
        resolved = link_path.resolve()
    except OSError as exc:
        return _status(False, "Broken Joern link at {}: {}".format(link_path, exc))

    if not has_spec_checkout(project, bug_index):
        return _status(True, "Joern path exists -> {} (spec checkout not present yet)".format(resolved))

    if resolved != spec_path.resolve():
        return _status(
            False,
            "Joern link {} points to {}, expected spec checkout {}".format(
                link_path, resolved, spec_path.resolve()
            ),
        )
    return _status(True, "Joern link aligned with spec checkout ({})".format(resolved))


def check_api_key() -> dict[str, Any]:
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return _status(True, "OPENAI_API_KEY is set")
    try:
        from config import OPENAI_API_KEY

        if OPENAI_API_KEY.strip():
            return _status(True, "OPENAI_API_KEY in src/config.py")
    except ImportError:
        pass
    return _status(False, "OPENAI_API_KEY not set (export or src/config.py)")


def run_all_checks(bug_name: str = "Chart-1") -> list[dict[str, Any]]:
    return [
        {"name": "repairagent", **check_repairagent_root()},
        {"name": "dataset", **check_dataset(bug_name)},
        {"name": "hyperparams", **check_hyperparams()},
        {"name": "bootstrap", **check_bootstrap()},
        {"name": "defects4j_cli", **check_defects4j_cli()},
        {"name": "adapter_exports", **check_adapter_exports()},
        {"name": "adapter_inputs", **check_adapter_inputs(bug_name)},
        {"name": "checkout_layout", **check_checkout_layout(bug_name)},
        {"name": "joern_link", **check_joern_link(bug_name)},
        {"name": "api_key", **check_api_key()},
    ]


def run_preflight_checks(
    bug_name: str = "Chart-1",
    include_optional: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    """Return (results, failure_count). Optional checks are skipped unless requested."""
    results = run_all_checks(bug_name)
    failed = 0
    for item in results:
        if not include_optional and item["name"] in OPTIONAL_CHECK_NAMES:
            continue
        if not item["ok"]:
            failed += 1
    return results, failed


def format_check_line(item: dict[str, Any], include_optional: bool = False) -> str | None:
    name = item["name"]
    if not include_optional and name in OPTIONAL_CHECK_NAMES:
        return None
    mark = "OK" if item["ok"] else "FAIL"
    return "[{}] {}: {}".format(mark, name, item["message"])


def main(argv: list[str] | None = None) -> int:
    bug = (argv or sys.argv[1:2] or ["Chart-1"])[0]
    root = reinfix_root()
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    print("ReInFix spec adapter environment check (Step 2)")
    print("Root: {}".format(root))
    print("Bug: {}".format(bug))
    print("")

    results, failed = run_preflight_checks(bug, include_optional=True)
    for item in results:
        line = format_check_line(item, include_optional=True)
        if line is None:
            continue
        if item["name"] in OPTIONAL_CHECK_NAMES and not item["ok"]:
            print(line.replace("[FAIL]", "[SKIP]"))
            continue
        print(line)

    print("")
    required_failed = sum(
        1 for item in results if item["name"] not in OPTIONAL_CHECK_NAMES and not item["ok"]
    )
    if required_failed:
        print("{} required check(s) failed.".format(required_failed))
        return 1
    print("All required checks passed. Run scripts/run_spec_smoke_test.py for a live spec call.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
