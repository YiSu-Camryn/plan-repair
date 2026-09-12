#!/bin/bash
#SBATCH -A pi_juanzhai_umass_edu
#SBATCH --partition=superpod-a100
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=32
#SBATCH --mem=256G
#SBATCH --time=2-00:00:00
#SBATCH -J spec-pass-k
#SBATCH -o /project/pi_juanzhai_umass_edu/spec-repair-test/logs/%x-%j.out
#SBATCH -e /project/pi_juanzhai_umass_edu/spec-repair-test/logs/%x-%j.err

set -euo pipefail

# ── 项目根目录（以后只改这一行）──
PROJECT_BASE="/project/pi_juanzhai_umass_edu/spec-repair-test"

REPAIRAGENT_SRC="${PROJECT_BASE}/repair_agent"
LOG_DIR="${PROJECT_BASE}/logs"
ABLATION_DIR="${REPAIRAGENT_SRC}/experimental_setups/spec_attempts_ablation"
OUTPUT_DIR="${OUTPUT_DIR:-${PROJECT_BASE}/runs/spec_attempts_${SLURM_JOB_ID}}"

BUGS_FILE="${BUGS_FILE:-${ABLATION_DIR}/sample_40.txt}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-5}"
MODEL="${REPAIRAGENT_MODEL:-deepseek.v3.2}"

mkdir -p "$LOG_DIR" "${PROJECT_BASE}/runs" "$OUTPUT_DIR"

export REPAIRAGENT_SKIP_DEPS=1
export PATH="${PATH}:${REPAIRAGENT_SRC}/defects4j/framework/bin"

# API：提交前在 shell 里 export，或写进 ~/.bashrc / 集群 secret，不要 commit 明文 key
: "${OPENAI_API_KEY:?Set OPENAI_API_KEY before sbatch}"
export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-https://bedrock-mantle.us-east-2.api.aws/v1}"
export OPENAI_API_BASE="${OPENAI_API_BASE:-$OPENAI_API_BASE_URL}"

# Perl / locale（与 run_on_defects4j.sh 一致）
if command -v cpanm &>/dev/null; then
    cpanm --local-lib=~/perl5 local::lib 2>/dev/null || true
    eval "$(perl -I ~/perl5/lib/perl5/ -Mlocal::lib 2>/dev/null)" || true
fi
export PERL5LIB="${HOME}/perl5/lib/perl5${PERL5LIB:+:$PERL5LIB}"
for LANG in en_AU.UTF-8 en_GB.UTF-8 C.UTF-8 C; do
    if locale -a 2>/dev/null | grep -q "$LANG"; then
        export LANG
        break
    fi
done
export LC_COLLATE=C

cd "$REPAIRAGENT_SRC"
source venv/bin/activate

if ! command -v defects4j &>/dev/null; then
    echo "ERROR: defects4j not in PATH: ${REPAIRAGENT_SRC}/defects4j/framework/bin" >&2
    exit 1
fi

echo "=== Spec pass@k experiment ==="
echo "Job ID:       ${SLURM_JOB_ID}"
echo "Bugs file:    ${BUGS_FILE}"
echo "Max attempts: ${MAX_ATTEMPTS}"
echo "Model:        ${MODEL}"
echo "Output dir:   ${OUTPUT_DIR}"
echo "defects4j:    $(command -v defects4j)"
echo

python experimental_setups/spec_attempts_ablation/run_spec_attempts_experiment.py \
    --bugs-file "$BUGS_FILE" \
    --output-dir "$OUTPUT_DIR" \
    --max-attempts "$MAX_ATTEMPTS" \
    --model "$MODEL" \
    --summarize \
    ${RESUME:+--resume} \
    "$@"

echo
echo "=== Done ==="
echo "Results:  ${OUTPUT_DIR}/bug_results.jsonl"
echo "Summary:  ${OUTPUT_DIR}/spec_pass_rates.txt"
echo "Summarize again:"
echo "  cd ${REPAIRAGENT_SRC} && source venv/bin/activate"
echo "  python experimental_setups/spec_attempts_ablation/summarize_spec_pass_rates.py ${OUTPUT_DIR}"
