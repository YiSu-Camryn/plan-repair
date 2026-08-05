#!/usr/bin/env bash
#
# Run RepairAgent in an isolated copy of this directory (parallel-safe, scheme 1).
#
# Each invocation gets its own ai_settings.yaml, auto_gpt_workspace/, and
# experimental_setups/ — no cross-job interference.
#
# Usage:
#   ./run_isolated_job.sh <bugs_file> <hyperparams.json> [model]
#   ./run_isolated_job.sh --ablation <bugs_file> <hyperparams.json> [model]
#
# Environment:
#   REPAIRAGENT_SRC          Source tree (default: directory containing this script)
#   REPAIRAGENT_RUN_DIR      Isolated run directory (default: ./runs/job_${SLURM_JOB_ID:-$$})
#   REPAIRAGENT_SHARE_VENV   If 1 (default), symlink venv from source instead of copying
#   REPAIRAGENT_SKIP_COPY    If 1, reuse existing REPAIRAGENT_RUN_DIR (no rsync/cp)
#   REPAIRAGENT_SKIP_DEPS    Passed through to run.sh / run_ablation.sh
#
# Example (Slurm):
#   export REPAIRAGENT_RUN_DIR=$HOME/spec-repair-test/runs/job_${SLURM_JOB_ID}
#   yes "" | ./run_isolated_job.sh experimental_setups/batches/0 hyperparams.json deepseek.v3.2

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${REPAIRAGENT_SRC:-$SCRIPT_DIR}"
RUN_DIR="${REPAIRAGENT_RUN_DIR:-$SCRIPT_DIR/runs/job_${SLURM_JOB_ID:-$$}}"

MODE="defects4j"
if [[ "${1:-}" == "--ablation" ]]; then
    MODE="ablation"
    shift
fi

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 [--ablation] <bugs_file> <hyperparams.json> [model]" >&2
    exit 1
fi

BUGS_FILE="$1"
EXPERIMENT_FILE="$2"
MODEL="${3:-gpt-4o-mini}"

if [[ ! -d "$SRC_DIR" ]]; then
    echo "Error: REPAIRAGENT_SRC not found: $SRC_DIR" >&2
    exit 1
fi

if [[ ! -f "$BUGS_FILE" && -f "$SRC_DIR/$BUGS_FILE" ]]; then
    BUGS_FILE="$SRC_DIR/$BUGS_FILE"
fi
if [[ ! -f "$BUGS_FILE" ]]; then
    echo "Error: bugs file not found: $BUGS_FILE" >&2
    exit 1
fi

if [[ ! -f "$EXPERIMENT_FILE" && -f "$SRC_DIR/$EXPERIMENT_FILE" ]]; then
    EXPERIMENT_FILE="$SRC_DIR/$EXPERIMENT_FILE"
fi
if [[ ! -f "$EXPERIMENT_FILE" ]]; then
    echo "Error: hyperparams file not found: $EXPERIMENT_FILE" >&2
    exit 1
fi

mkdir -p "$(dirname "$RUN_DIR")"

if [[ "${REPAIRAGENT_SKIP_COPY:-0}" != "1" ]]; then
    echo "ISOLATED RUN: copying $SRC_DIR -> $RUN_DIR"
    if command -v rsync >/dev/null 2>&1; then
        rsync -a \
            --exclude 'auto_gpt_workspace/' \
            --exclude '/logs/' \
            --exclude 'runs/' \
            --exclude '__pycache__/' \
            --exclude '*.pyc' \
            --exclude '.git/' \
            "$SRC_DIR/" "$RUN_DIR/"
    else
        rm -rf "$RUN_DIR"
        cp -a "$SRC_DIR" "$RUN_DIR"
        rm -rf "$RUN_DIR/auto_gpt_workspace" "$RUN_DIR/logs" "$RUN_DIR/runs"
    fi
    mkdir -p "$RUN_DIR/auto_gpt_workspace"
    if [[ -d "$SRC_DIR/venv" && "${REPAIRAGENT_SHARE_VENV:-1}" == "1" ]]; then
        rm -rf "$RUN_DIR/venv"
        ln -sfn "$SRC_DIR/venv" "$RUN_DIR/venv"
        echo "ISOLATED RUN: using shared venv -> $SRC_DIR/venv"
    fi
else
    echo "ISOLATED RUN: reusing existing $RUN_DIR (REPAIRAGENT_SKIP_COPY=1)"
fi

echo "ISOLATED RUN: job_id=${SLURM_JOB_ID:-local-$$} mode=$MODE bugs=$BUGS_FILE"
cd "$RUN_DIR" || exit 1

if [[ "$MODE" == "ablation" ]]; then
    exec ./run_on_ablation_defects4j.sh "$BUGS_FILE" "$EXPERIMENT_FILE" "$MODEL"
else
    exec ./run_on_defects4j.sh "$BUGS_FILE" "$EXPERIMENT_FILE" "$MODEL"
fi
