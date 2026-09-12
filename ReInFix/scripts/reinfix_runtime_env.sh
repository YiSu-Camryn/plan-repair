#!/usr/bin/env bash
# Shared runtime environment for ReInFix+spec (login node, interactive, or Slurm).
#
# Usage (source, do not exec):
#   export PROJECT_BASE=/project/pi_juanzhai_umass_edu/spec-repair-test
#   source scripts/reinfix_runtime_env.sh
#
# Optional overrides before sourcing:
#   PROJECT_BASE, REPAIRAGENT_SRC, REINFIX_DIR

set -euo pipefail

: "${PROJECT_BASE:?Set PROJECT_BASE to the cluster project root}"

REINFIX_DIR="${REINFIX_DIR:-${PROJECT_BASE}/ReInFix}"
REPAIRAGENT_SRC="${REPAIRAGENT_SRC:-${PROJECT_BASE}/repair_agent}"

export PROJECT_BASE REINFIX_DIR REPAIRAGENT_SRC
export REPAIRAGENT_ROOT="${REPAIRAGENT_ROOT:-$REPAIRAGENT_SRC}"
export REPAIRAGENT_SKIP_DEPS="${REPAIRAGENT_SKIP_DEPS:-1}"

export PATH="${PATH}:${REPAIRAGENT_SRC}/defects4j/framework/bin"
export PATH="${PATH}:${REINFIX_DIR}/defects4j/framework/bin"

# ReInFix+spec defaults (override at submit time if needed)
export REINFIX_MODE="${REINFIX_MODE:-spec}"
export REINFIX_SPEC_RUN_TESTS="${REINFIX_SPEC_RUN_TESTS:-1}"
export REINFIX_SPEC_USE_D4J_INFO="${REINFIX_SPEC_USE_D4J_INFO:-1}"
export REINFIX_SPEC_RESTORE_AFTER_TEST="${REINFIX_SPEC_RESTORE_AFTER_TEST:-0}"

# LLM API — export before sbatch; do not commit keys
export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-https://bedrock-mantle.us-east-2.api.aws/v1}"
export OPENAI_API_BASE="${OPENAI_API_BASE:-$OPENAI_API_BASE_URL}"

# Joern client endpoint (must match src/joern.sh port)
export REINFIX_JOERN_ADDR="${REINFIX_JOERN_ADDR:-localhost:8081}"

# Perl / locale (same as repair_agent/run_on_defects4j.sh)
if command -v cpanm &>/dev/null; then
    cpanm --local-lib="${HOME}/perl5" local::lib 2>/dev/null || true
    eval "$(perl -I "${HOME}/perl5/lib/perl5/" -Mlocal::lib 2>/dev/null)" || true
fi
export PERL5LIB="${HOME}/perl5/lib/perl5${PERL5LIB:+:$PERL5LIB}"
for LANG in en_AU.UTF-8 en_GB.UTF-8 C.UTF-8 C; do
    if locale -a 2>/dev/null | grep -q "$LANG"; then
        export LANG
        break
    fi
done
export LC_COLLATE=C

if [[ -f "${REPAIRAGENT_SRC}/venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "${REPAIRAGENT_SRC}/venv/bin/activate"
fi
