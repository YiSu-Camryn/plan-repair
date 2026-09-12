#!/usr/bin/env bash
# ReInFix MF + verified behavioral spec (generate+verify → ReAct → multi-function patch).
#
# Usage:
#   ./run_reinfix_mf_spec.sh <bugs_file> [hyperparams.json] [model]

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export REINFIX_MODE=spec
exec "$SCRIPT_DIR/run_reinfix_mf_batch.sh" "$@"
