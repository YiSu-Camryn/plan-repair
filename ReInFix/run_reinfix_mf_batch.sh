#!/usr/bin/env bash
# ReInFix multi-function batch runner — baseline or spec-enabled mode.
#
# Usage:
#   ./run_reinfix_mf_batch.sh <bugs_file> [hyperparams.json] [model] [--mode baseline|spec]
#
# Environment:
#   REPAIRAGENT_SRC              Path to repair_agent (default: ../repair_agent)
#   REINFIX_MODE                 baseline | spec (default: spec; overridden by --mode)
#   OPENAI_API_KEY               LLM API key
#   REINFIX_SPEC_RUN_TESTS       1 = live defects4j test for spec (default: 1)
#   REINFIX_SPEC_USE_D4J_INFO    1 = append defects4j info to localization (default: 1)
#   REINFIX_SPEC_RESTORE_AFTER_TEST  1 = re-checkout after test (default: 0)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export REPAIRAGENT_SRC="${REPAIRAGENT_SRC:-$SCRIPT_DIR/../repair_agent}"
export REPAIRAGENT_ROOT="${REPAIRAGENT_ROOT:-$REPAIRAGENT_SRC}"
export PATH="$PATH:$REPAIRAGENT_SRC/defects4j/framework/bin"

export REINFIX_MODE="${REINFIX_MODE:-spec}"
export REINFIX_SPEC_RUN_TESTS="${REINFIX_SPEC_RUN_TESTS:-1}"
export REINFIX_SPEC_USE_D4J_INFO="${REINFIX_SPEC_USE_D4J_INFO:-1}"
export REINFIX_SPEC_RESTORE_AFTER_TEST="${REINFIX_SPEC_RESTORE_AFTER_TEST:-0}"

export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-${OPENAI_API_BASE:-}}"
export OPENAI_API_BASE="${OPENAI_API_BASE:-${OPENAI_API_BASE_URL:-}}"

BUGS_FILE="${1:?Usage: $0 <bugs_file> [hyperparams.json] [model] [--mode baseline|spec]}"
HYPERPARAMS="${2:-hyperparams.json}"
MODEL="${3:-gpt-4o-mini}"
shift $(( $# >= 3 ? 3 : $# )) || true

if [[ ! -f "$BUGS_FILE" && -f "$SCRIPT_DIR/$BUGS_FILE" ]]; then
  BUGS_FILE="$SCRIPT_DIR/$BUGS_FILE"
fi
if [[ ! -f "$HYPERPARAMS" && -f "$SCRIPT_DIR/$HYPERPARAMS" ]]; then
  HYPERPARAMS="$SCRIPT_DIR/$HYPERPARAMS"
fi

if [[ -x "$REPAIRAGENT_SRC/venv/bin/python" ]]; then
  PYTHON_CMD="$REPAIRAGENT_SRC/venv/bin/python"
elif command -v python3 &>/dev/null; then
  PYTHON_CMD="python3"
else
  PYTHON_CMD="python"
fi

MODE_ARGS=()
if [[ -n "${REINFIX_MODE:-}" ]]; then
  has_mode_flag=0
  for arg in "$@"; do
    if [[ "$arg" == "--mode" ]]; then
      has_mode_flag=1
      break
    fi
  done
  if [[ "$has_mode_flag" -eq 0 ]]; then
    MODE_ARGS=(--mode "$REINFIX_MODE")
  fi
fi

exec "$PYTHON_CMD" src/reinfix_mf_pipeline.py "$BUGS_FILE" "$HYPERPARAMS" "$MODEL" "${MODE_ARGS[@]}" "$@"
