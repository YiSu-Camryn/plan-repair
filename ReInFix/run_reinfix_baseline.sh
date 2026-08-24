#!/usr/bin/env bash
# ReInFix baseline (original, no behavioral spec).
#
# Usage:
#   ./run_reinfix_baseline.sh <bugs_file> [hyperparams.json] [model]

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export REINFIX_MODE=baseline
exec "$SCRIPT_DIR/run_reinfix_batch.sh" "$@"
