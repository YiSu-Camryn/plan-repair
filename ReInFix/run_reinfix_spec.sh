#!/usr/bin/env bash
# ReInFix + verified behavioral spec (generate+verify → ReAct → patch).
#
# Usage:
#   ./run_reinfix_spec.sh <bugs_file> [hyperparams.json] [model]

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export REINFIX_MODE=spec
exec "$SCRIPT_DIR/run_reinfix_batch.sh" "$@"
