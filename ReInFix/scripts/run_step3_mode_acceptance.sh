#!/usr/bin/env bash
# Step 3 mode acceptance: baseline vs spec wiring (no LLM, no Joern).
#
# Usage:
#   ./scripts/run_step3_mode_acceptance.sh [BUG_ID]

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

echo "=== Step 3 mode acceptance (bug=$BUG) ==="
echo ""

echo "--- pipeline mode resolution ---"
"$PYTHON" scripts/verify_pipeline_mode.py
echo ""

echo "--- baseline prompts (no spec) ---"
"$PYTHON" scripts/verify_baseline_prompts.py
echo ""

echo "--- checkout layout (baseline vs spec paths) ---"
"$PYTHON" scripts/verify_checkout_strategy.py "$BUG"
echo ""

echo "--- pipeline wiring (reinfix_pipeline branches) ---"
"$PYTHON" scripts/verify_pipeline_mode_wiring.py
echo ""

echo "--- spec injection (ReAct + patch, spec mode) ---"
"$PYTHON" scripts/verify_spec_injection.py "$BUG"
echo ""

echo "Step 3 mode acceptance PASSED."
