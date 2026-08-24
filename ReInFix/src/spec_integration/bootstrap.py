"""Wire ReInFix spec runtime: cwd, PYTHONPATH, Defects4J assets from RepairAgent."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from spec_integration.paths import reinfix_root, repairagent_src

logger = logging.getLogger(__name__)

REQUIRED_D4J_ASSETS = ("buggy-lines", "buggy-methods", "framework")
SAMPLE_GT_FILE = Path("buggy-lines") / "Chart-1.buggy.lines"


def setup_environment(verify: bool = False) -> tuple[Path, Path]:
    """Prepare ReInFix cwd, ``src`` on sys.path, and shared Defects4J assets."""
    root = reinfix_root()
    repair = repairagent_src()
    if not repair.is_dir():
        raise RuntimeError(
            "RepairAgent tree not found at {} (set REPAIRAGENT_SRC for checkout, "
            "buggy-lines, and framework/bin).".format(repair)
        )

    os.chdir(root)
    src_dir = str(root / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    link_errors = _ensure_defects4j_assets(root, repair)
    _ensure_defects4j_framework_on_path(root, repair)

    if link_errors:
        msg = "Defects4J asset linking issues:\n" + "\n".join(link_errors)
        if verify:
            raise RuntimeError(msg)
        logger.warning(msg)

    if verify:
        asset_errors = verify_defects4j_assets(root, repair)
        if asset_errors:
            raise RuntimeError(
                "Defects4J asset verification failed:\n" + "\n".join(asset_errors)
            )

    return root, repair


def verify_defects4j_assets(
    reinfix: Path | None = None,
    repair: Path | None = None,
) -> list[str]:
    """Return human-readable errors; empty list means assets look usable."""
    root = reinfix or reinfix_root()
    repair_root = repair or repairagent_src()
    errors: list[str] = []
    d4j = root / "defects4j"
    repair_d4j = repair_root / "defects4j"

    for sub in REQUIRED_D4J_ASSETS:
        path = d4j / sub
        expected_source = repair_d4j / sub

        if not path.exists():
            errors.append("Missing ReInFix/defects4j/{}".format(sub))
            continue
        if path.is_symlink() and not path.exists():
            errors.append("Broken symlink: {}".format(path))
            continue
        if not path.is_dir():
            errors.append("Expected directory: {}".format(path))
            continue
        if expected_source.is_dir() and not _paths_same_tree(path, expected_source):
            errors.append(
                "ReInFix/defects4j/{} is not linked to RepairAgent ({})".format(
                    sub, expected_source
                )
            )

    sample = d4j / SAMPLE_GT_FILE
    if not sample.is_file():
        errors.append("Missing sample GT file: {}".format(sample))
    elif sample.stat().st_size == 0:
        errors.append("Empty sample GT file: {}".format(sample))

    if not _defects4j_cli_on_path():
        reinfix_cli = _defects4j_cli_available(d4j)
        repair_cli = _defects4j_cli_available(repair_d4j)
        if not reinfix_cli and not repair_cli:
            errors.append(
                "defects4j CLI not found on PATH and not under "
                "ReInFix/defects4j/framework/bin or RepairAgent"
            )

    return errors


def link_directory(source: Path, target: Path) -> None:
    """Create ``target`` -> ``source`` (symlink, or directory junction on Windows)."""
    source = source.resolve()
    if not source.exists():
        raise FileNotFoundError("Link source does not exist: {}".format(source))

    if target.exists() or target.is_symlink():
        if _paths_same_tree(target, source):
            return
        if target.is_symlink():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        os.symlink(source, target, target_is_directory=source.is_dir())
        return
    except OSError as exc:
        logger.debug("symlink failed (%s -> %s): %s", source, target, exc)

    if os.name == "nt" and source.is_dir():
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(source)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and target.exists():
            return
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            "Failed to link {} -> {} (symlink and junction failed: {})".format(
                target, source, detail or "unknown error"
            )
        ) from exc

    raise RuntimeError(
        "Failed to link {} -> {}: {}".format(target, source, exc)
    ) from exc


def _paths_same_tree(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def _defects4j_cli_available(d4j_root: Path) -> bool:
    bin_dir = d4j_root / "framework" / "bin"
    for name in ("defects4j", "defects4j.bat"):
        if (bin_dir / name).is_file():
            return True
    return False


def _defects4j_cli_on_path() -> bool:
    return shutil.which("defects4j") is not None


def _ensure_defects4j_assets(reinfix: Path, repair: Path) -> list[str]:
    """Symlink buggy-lines, buggy-methods, and framework from RepairAgent."""
    errors: list[str] = []
    src_d4j = repair / "defects4j"
    if not src_d4j.is_dir():
        errors.append("RepairAgent defects4j tree missing: {}".format(src_d4j))
        return errors

    reinfix_d4j = reinfix / "defects4j"
    reinfix_d4j.mkdir(parents=True, exist_ok=True)

    for sub in REQUIRED_D4J_ASSETS:
        source = src_d4j / sub
        target = reinfix_d4j / sub
        if not source.is_dir():
            errors.append("RepairAgent missing defects4j/{}".format(sub))
            continue

        if target.exists() or target.is_symlink():
            if _paths_same_tree(target, source):
                continue
            if target.is_symlink():
                target.unlink()
            elif target.is_dir():
                if any(target.iterdir()):
                    errors.append(
                        "ReInFix/defects4j/{} exists and is not linked to {}; "
                        "remove or rename it so bootstrap can link RepairAgent assets".format(
                            sub, source
                        )
                    )
                    continue
                shutil.rmtree(target)
            else:
                target.unlink()

        try:
            link_directory(source, target)
        except (OSError, RuntimeError, FileNotFoundError) as exc:
            errors.append(
                "Could not link {} -> {}: {}".format(target, source, exc)
            )
    return errors


def _ensure_defects4j_framework_on_path(reinfix: Path, repair: Path) -> None:
    """Prefer linked ReInFix framework/bin, then RepairAgent framework/bin."""
    candidates = [
        reinfix / "defects4j" / "framework" / "bin",
        repair / "defects4j" / "framework" / "bin",
    ]
    path_env = os.environ.get("PATH", "")
    for framework_bin in candidates:
        if not framework_bin.is_dir():
            continue
        bin_str = str(framework_bin)
        if bin_str not in path_env:
            os.environ["PATH"] = bin_str + os.pathsep + path_env
            path_env = os.environ["PATH"]
            logger.info("Added defects4j to PATH: %s", bin_str)
