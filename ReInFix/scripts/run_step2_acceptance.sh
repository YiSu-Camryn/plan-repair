#!/usr/bin/env bash
# Step 2 acceptance: verify environment, then run one live spec smoke test.
#
# Usage:
#   ./scripts/run_step2_acceptance.sh [BUG_ID]
#
# Requires: REPAIRAGENT_SRC, defects4j assets, OPENAI_API_KEY (for smoke test).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

BUG="${1:-Chart-1}"

export REPAIRAGENT_SRC="${REPAIRAGENT_SRC:-$ROOT/../repair_agent}"
export REPAIRAGENT_ROOT="${REPAIRAGENT_ROOT:-$REPAIRAGENT_SRC}"
export PATH="$PATH:$REPAIRAGENT_SRC/defects4j/framework/bin"

if [[ -x "$REPAIRAGENT_SRC/venv/bin/python" ]]; then
  PYTHON="$REPAIRAGENT_SRC/venv/bin/python"
elif command -v python3 &>/dev/null; then
  PYTHON="python3"
else
  PYTHON="python"
fi

echo "=== Step 2 acceptance for $BUG ==="
echo "ReInFix root: $ROOT"
echo "RepairAgent:  $REPAIRAGENT_SRC"
echo ""

echo "--- 1/2 verify_spec_environment ---"
"$PYTHON" scripts/verify_spec_environment.py "$BUG"

echo ""
echo "--- 2/2 run_spec_smoke_test ---"
"$PYTHON" scripts/run_spec_smoke_test.py "$BUG"

echo ""
echo "Step 2 acceptance PASSED for $BUG"
