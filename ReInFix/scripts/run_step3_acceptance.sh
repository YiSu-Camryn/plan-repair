#!/usr/bin/env bash
# Step 3 acceptance: verify spec appears in ReAct + patch prompts (no LLM, no Joern).
#
# Usage:
#   ./scripts/run_step3_acceptance.sh [BUG_ID]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

BUG="${1:-Chart-1}"

if [[ -x "${REPAIRAGENT_SRC:-$ROOT/../repair_agent}/venv/bin/python" ]]; then
  PYTHON="${REPAIRAGENT_SRC:-$ROOT/../repair_agent}/venv/bin/python"
elif command -v python3 &>/dev/null; then
  PYTHON="python3"
else
  PYTHON="python"
fi

echo "=== Step 3 acceptance for $BUG ==="
"$PYTHON" scripts/verify_spec_injection.py "$BUG"
echo ""
echo "Step 3 acceptance PASSED (both injection points verified)."
