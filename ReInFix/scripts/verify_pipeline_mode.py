#!/usr/bin/env python3
"""Verify pipeline mode resolution (Step 0)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from spec_integration.pipeline_mode import (  # noqa: E402
    backend_name,
    is_spec_enabled,
    mode_label,
    resolve_pipeline_mode,
)


def main() -> int:
    cases = [
        ("default", {}, None, None, "spec"),
        ("cli baseline", {}, "baseline", None, "baseline"),
        ("cli spec", {}, "spec", None, "spec"),
        ("env baseline", {"REINFIX_MODE": "baseline"}, None, None, "baseline"),
        ("hyperparams", {}, None, {"pipeline_mode": "baseline"}, "baseline"),
        ("cli beats env", {"REINFIX_MODE": "spec"}, "baseline", None, "baseline"),
        ("alias no_spec", {}, "no_spec", None, "baseline"),
    ]

    failed = 0
    print("Step 0 pipeline mode resolution")
    prev_env = os.environ.get("REINFIX_MODE")
    try:
        for label, env_patch, cli_mode, hyperparams, expected in cases:
            os.environ.pop("REINFIX_MODE", None)
            for key, value in env_patch.items():
                os.environ[key] = value
            mode = resolve_pipeline_mode(cli_mode=cli_mode, hyperparams=hyperparams)
            ok = mode == expected
            mark = "OK" if ok else "FAIL"
            print(
                "[{}] {} -> mode={} backend={} spec_enabled={} ({})".format(
                    mark,
                    label,
                    mode,
                    backend_name(mode),
                    is_spec_enabled(mode),
                    mode_label(mode),
                )
            )
            if not ok:
                print("       expected mode={}".format(expected))
                failed += 1
    finally:
        if prev_env is not None:
            os.environ["REINFIX_MODE"] = prev_env
        else:
            os.environ.pop("REINFIX_MODE", None)

    if failed:
        print("\n{} case(s) failed.".format(failed))
        return 1
    print("\nAll pipeline mode checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
