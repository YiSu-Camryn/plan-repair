#!/bin/bash
#SBATCH -A pi_juanzhai_umass_edu
#SBATCH --partition=superpod-a100
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=32
#SBATCH --mem=256G
#SBATCH --time=2-00:00:00
#SBATCH -o logs/%x-%j.out
#SBATCH -e logs/%x-%j.err

set -euo pipefail

REPAIRAGENT_SRC="$HOME/spec-repair-test/repair_agent"
REPAIRAGENT_RUN_DIR="$HOME/spec-repair-test/runs/job_${SLURM_JOB_ID}"
BATCH_ID="${BATCH_ID:-0}"

mkdir -p "$HOME/logs" "$HOME/spec-repair-test/runs"

export REPAIRAGENT_SRC
export REPAIRAGENT_RUN_DIR
export REPAIRAGENT_SKIP_DEPS=1
export PATH="$PATH:$REPAIRAGENT_SRC/defects4j/framework/bin"
export OPENAI_API_KEY=""
export OPENAI_API_BASE_URL="https://bedrock-mantle.us-east-2.api.aws/v1"
export OPENAI_API_BASE="https://bedrock-mantle.us-east-2.api.aws/v1"

cd "$REPAIRAGENT_SRC"
source venv/bin/activate

yes "" | ./run_isolated_job.sh "experimental_setups/batches/${BATCH_ID}" hyperparams.json deepseek.v3.2
