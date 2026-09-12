"""Run behavioral spec (generate + verify) for multi-function D4J entries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spec_integration.mf_localization import (
    DEFAULT_WORKSPACE,
    MF_DATASET_NAME,
    build_spec_inputs_mf,
)
from spec_integration.spec_adapter import (
    checkout_for_spec,
    ensure_spec_runtime,
    get_spec_prompt_section,
    joern_checkout_link,
    joern_project_name,
    link_joern_checkout,
    load_dataset_entry,
    normalize_bug_name,
    parse_bug_id,
    spec_checkout_dir,
    spec_workspace_dir,
)


def run_spec_for_mf_dataset_bug(
    bug_name: str,
    dataset_entry: dict[str, Any],
    model: str,
    max_attempts: int | None = None,
    exp_dir: str | None = None,
    hyperparams_file: str | Path | None = None,
    workspace: str = DEFAULT_WORKSPACE,
    checkout: bool = True,
    run_tests: bool | None = None,
    use_d4j_info: bool | None = None,
) -> dict[str, Any]:
    """Checkout buggy project and run generate+verify spec for an MF dataset row."""
    bug_key = normalize_bug_name(bug_name)
    project_name, bug_index = parse_bug_id(bug_key)
    ensure_spec_runtime(exp_dir)

    if checkout:
        checkout_for_spec(
            project_name,
            bug_index,
            workspace=spec_workspace_dir(workspace),
            link_joern=True,
        )
    elif (spec_checkout_dir(project_name, bug_index, workspace) / ".defects4j.config").is_file():
        link_joern_checkout(project_name, bug_index, workspace)

    spec_inputs = build_spec_inputs_mf(
        bug_key,
        dataset_entry,
        model=model,
        max_attempts=max_attempts,
        hyperparams_file=hyperparams_file,
        workspace=workspace,
        run_tests=run_tests,
        use_d4j_info=use_d4j_info,
    )

    from spec.spec_generator import generate_spec

    result = generate_spec(**spec_inputs)
    result.setdefault("project_name", project_name)
    result.setdefault("bug_index", bug_index)
    result["joern_project_name"] = joern_project_name(project_name, bug_index)
    result["spec_checkout_dir"] = str(spec_checkout_dir(project_name, bug_index, workspace))
    result["joern_checkout_link"] = str(joern_checkout_link(project_name, bug_index))
    result["repair_scenario"] = "MF"
    result["dataset"] = MF_DATASET_NAME
    return result


def run_spec_for_mf_bug_name(
    bug_name: str,
    model: str,
    max_attempts: int | None = None,
    exp_dir: str | None = None,
    dataset_path: str | Path | None = None,
    hyperparams_file: str | Path | None = None,
    run_tests: bool | None = None,
    use_d4j_info: bool | None = None,
) -> dict[str, Any]:
    """Load MF dataset entry by bug id and run the spec pipeline."""
    entry = load_dataset_entry(bug_name, path=dataset_path, variant="mf")
    return run_spec_for_mf_dataset_bug(
        bug_name,
        entry,
        model=model,
        max_attempts=max_attempts,
        exp_dir=exp_dir,
        hyperparams_file=hyperparams_file,
        run_tests=run_tests,
        use_d4j_info=use_d4j_info,
    )


__all__ = [
    "get_spec_prompt_section",
    "run_spec_for_mf_bug_name",
    "run_spec_for_mf_dataset_bug",
]
