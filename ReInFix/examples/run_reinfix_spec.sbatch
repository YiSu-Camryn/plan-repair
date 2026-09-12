#!/bin/bash
#SBATCH -A pi_juanzhai_umass_edu
#SBATCH --partition=superpod-a100
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=32
#SBATCH --mem=256G
#SBATCH --time=2-00:00:00
#SBATCH -J reinfix-spec
#SBATCH -o /project/pi_juanzhai_umass_edu/spec-repair-test/logs/%x-%j.out
#SBATCH -e /project/pi_juanzhai_umass_edu/spec-repair-test/logs/%x-%j.err

set -euo pipefail

# ══════════════════════════════════════════════════════════════════════════════
# ReInFix + verified behavioral spec (backend: reinfix+spec)
#
# First-time setup (login node, once):
#   export PROJECT_BASE=/project/pi_juanzhai_umass_edu/spec-repair-test
#   export OPENAI_API_KEY=...
#   cd "$PROJECT_BASE/ReInFix"
#   ./scripts/setup_cluster_env.sh
#
# Submit:
#   export OPENAI_API_KEY=...
#   sbatch examples/run_reinfix_spec.sbatch
#
# Optional overrides at submit time:
#   BUGS_FILE=bug_list/sf_sample.txt \
#   REPAIRAGENT_MODEL=deepseek.v3.2 \
#   sbatch examples/run_reinfix_spec.sbatch
#
# Baseline (original ReInFix, no spec):
#   REINFIX_MODE=baseline sbatch examples/run_reinfix_spec.sbatch
# ══════════════════════════════════════════════════════════════════════════════

PROJECT_BASE="/project/pi_juanzhai_umass_edu/spec-repair-test"
REINFIX_DIR="${PROJECT_BASE}/ReInFix"
REPAIRAGENT_SRC="${PROJECT_BASE}/repair_agent"
LOG_DIR="${PROJECT_BASE}/logs"

BUGS_FILE="${BUGS_FILE:-${REINFIX_DIR}/bug_list/sf_sample.txt}"
HYPERPARAMS="${HYPERPARAMS:-${REINFIX_DIR}/hyperparams.json}"
MODEL="${REPAIRAGENT_MODEL:-deepseek.v3.2}"
PREFLIGHT_BUG="${PREFLIGHT_BUG:-Chart-1}"
SKIP_SERVICES="${SKIP_SERVICES:-0}"

mkdir -p "$LOG_DIR"

export PROJECT_BASE REINFIX_DIR REPAIRAGENT_SRC
# shellcheck disable=SC1091
source "${REINFIX_DIR}/scripts/reinfix_runtime_env.sh"

: "${OPENAI_API_KEY:?Set OPENAI_API_KEY before sbatch (export in shell, do not commit)}"

# Ensure Joern client address matches running server
CONFIG="${REINFIX_DIR}/src/config.py"
if [[ ! -f "$CONFIG" ]] || ! grep -q "JOERN_ADDR=\"${REINFIX_JOERN_ADDR}\"" "$CONFIG" 2>/dev/null; then
    cat > "$CONFIG" <<EOF
OPENAI_API_KEY=""
JOERN_ADDR="${REINFIX_JOERN_ADDR}"
EOF
fi

cleanup() {
    if [[ "${SKIP_SERVICES}" != "1" ]]; then
        bash "${REINFIX_DIR}/scripts/stop_reinfix_services.sh" || true
    fi
}
trap cleanup EXIT

cd "$REINFIX_DIR"

if ! command -v defects4j &>/dev/null; then
    echo "ERROR: defects4j not in PATH (${REPAIRAGENT_SRC}/defects4j/framework/bin)" >&2
    exit 1
fi

echo "=== ReInFix+spec batch ==="
echo "Job ID:       ${SLURM_JOB_ID}"
echo "Node:         ${SLURM_NODELIST:-local}"
echo "Mode:         ${REINFIX_MODE}"
echo "Bugs file:    ${BUGS_FILE}"
echo "Hyperparams:  ${HYPERPARAMS}"
echo "Model:        ${MODEL}"
echo "defects4j:    $(command -v defects4j)"
echo

echo "--- Preflight: Step 2 environment (no LLM) ---"
python scripts/verify_spec_environment.py "$PREFLIGHT_BUG"
echo

if [[ "${SKIP_SERVICES}" != "1" ]]; then
    echo "--- Starting Joern + RAG ---"
    bash scripts/start_reinfix_services.sh
    echo
fi

chmod +x run_reinfix_batch.sh run_reinfix_spec.sh

echo "--- Running pipeline ---"
./run_reinfix_spec.sh "$BUGS_FILE" "$HYPERPARAMS" "$MODEL"

echo
echo "=== Done ==="
LATEST_EXP="$(tail -n1 experimental_setups/experiments_list.txt 2>/dev/null || true)"
if [[ -n "$LATEST_EXP" ]]; then
    echo "Results:  experimental_setups/${LATEST_EXP}/bug_results.jsonl"
    echo "Summarize: python experimental_setups/summarize_experiment.py ${LATEST_EXP}"
fi
