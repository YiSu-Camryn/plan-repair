#!/usr/bin/env bash
# One-time / pre-batch setup for ReInFix+spec on the UMass cluster.
#
# Run on the login node (or an interactive session) before the first sbatch:
#   export PROJECT_BASE=/project/pi_juanzhai_umass_edu/spec-repair-test
#   export OPENAI_API_KEY=...          # for smoke test only
#   cd "$PROJECT_BASE/ReInFix"
#   chmod +x scripts/*.sh run_reinfix_*.sh
#   ./scripts/setup_cluster_env.sh
#
# What this script checks or prepares:
#   1. Directory layout (repair_agent + ReInFix under PROJECT_BASE)
#   2. System tools: Java 11, Perl/cpanm, Python 3.10+, joern, defects4j
#   3. RepairAgent venv + Python deps
#   4. Defects4J init + buggy-lines/methods symlinks into ReInFix
#   5. ReInFix src/config.py (JOERN_ADDR only; API key stays in env)
#   6. RAG retrieval corpus
#   7. Step 2 environment verification (+ optional live smoke test)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REINFIX_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_BASE="${PROJECT_BASE:-$(cd "$REINFIX_DIR/.." && pwd)}"
REPAIRAGENT_SRC="${REPAIRAGENT_SRC:-${PROJECT_BASE}/repair_agent}"

export PROJECT_BASE REINFIX_DIR REPAIRAGENT_SRC
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/reinfix_runtime_env.sh"

PYTHON="${PYTHON:-python}"
if [[ -x "${REPAIRAGENT_SRC}/venv/bin/python" ]]; then
    PYTHON="${REPAIRAGENT_SRC}/venv/bin/python"
fi

pass=0
fail=0

check() {
    local label="$1"
    shift
    if "$@"; then
        echo "[OK]   ${label}"
        pass=$((pass + 1))
    else
        echo "[FAIL] ${label}" >&2
        fail=$((fail + 1))
    fi
}

echo "=== ReInFix+spec cluster setup ==="
echo "PROJECT_BASE:    ${PROJECT_BASE}"
echo "REPAIRAGENT_SRC: ${REPAIRAGENT_SRC}"
echo "REINFIX_DIR:     ${REINFIX_DIR}"
echo

# ── 1. Layout ────────────────────────────────────────────────────────────────
check "repair_agent directory exists" test -d "$REPAIRAGENT_SRC"
check "ReInFix directory exists" test -d "$REINFIX_DIR"
check "D4J dataset present" test -f "${REINFIX_DIR}/D4J_dataset/defects4j-sf.json"
check "hyperparams.json present" test -f "${REINFIX_DIR}/hyperparams.json"

# ── 2. System tools ──────────────────────────────────────────────────────────
check "java available" command -v java
check "perl available" command -v perl
check "python available" command -v "$PYTHON"
check "joern available" command -v joern

# ── 3. RepairAgent Python env ────────────────────────────────────────────────
if [[ ! -d "${REPAIRAGENT_SRC}/venv" ]]; then
    echo "Creating venv at ${REPAIRAGENT_SRC}/venv ..."
    python3 -m venv "${REPAIRAGENT_SRC}/venv"
    # shellcheck disable=SC1091
    source "${REPAIRAGENT_SRC}/venv/bin/activate"
    pip install -U pip
    pip install -r "${REPAIRAGENT_SRC}/requirements.txt"
else
    echo "[OK]   repair_agent venv exists"
    pass=$((pass + 1))
fi

# ── 4. Defects4J ─────────────────────────────────────────────────────────────
D4J="${REPAIRAGENT_SRC}/defects4j"
if [[ ! -d "${D4J}/framework" ]]; then
    echo "Defects4J not initialized — run manually on the cluster:"
    echo "  cd ${REPAIRAGENT_SRC}"
    echo "  git clone https://github.com/rjust/defects4j.git"
    echo "  cp -r ${PROJECT_BASE}/data/buggy-lines ${D4J}/"
    echo "  cp -r ${PROJECT_BASE}/data/buggy-methods ${D4J}/"
    echo "  cd defects4j && ./init.sh"
    fail=$((fail + 1))
else
    echo "[OK]   defects4j framework present"
    pass=$((pass + 1))
fi

# Bootstrap ReInFix symlinks (buggy-lines, framework/bin on PATH)
cd "$REINFIX_DIR"
PYTHONPATH="${REINFIX_DIR}/src" "$PYTHON" -c \
    "from spec_integration.bootstrap import setup_environment; setup_environment(verify=True)"

# ── 5. config.py (Joern endpoint; API key via env at job time) ───────────────
CONFIG="${REINFIX_DIR}/src/config.py"
JOERN_ADDR="${REINFIX_JOERN_ADDR:-localhost:8081}"
if [[ ! -f "$CONFIG" ]] || ! grep -q "JOERN_ADDR=\"${JOERN_ADDR}\"" "$CONFIG" 2>/dev/null; then
    cat > "$CONFIG" <<EOF
OPENAI_API_KEY=""
JOERN_ADDR="${JOERN_ADDR}"
EOF
    echo "[OK]   wrote ${CONFIG} (JOERN_ADDR=${JOERN_ADDR})"
    pass=$((pass + 1))
else
    echo "[OK]   ${CONFIG} already configured"
    pass=$((pass + 1))
fi

# ── 6. RAG corpus ────────────────────────────────────────────────────────────
RAG_CSV="${REINFIX_DIR}/retrieval_base/embedded_cause_97k.csv"
if [[ -f "$RAG_CSV" ]]; then
    echo "[OK]   RAG corpus present"
    pass=$((pass + 1))
else
    echo "[FAIL] missing ${RAG_CSV}" >&2
    echo "       Copy the ReInFix retrieval_base/embedded_cause_97k.csv into place." >&2
    fail=$((fail + 1))
fi

# ── 7. Preflight (no LLM) ────────────────────────────────────────────────────
echo
echo "--- Step 2 environment check (no LLM) ---"
if "$PYTHON" scripts/verify_spec_environment.py Chart-1; then
    echo "[OK]   verify_spec_environment.py"
    pass=$((pass + 1))
else
    echo "[FAIL] verify_spec_environment.py" >&2
    fail=$((fail + 1))
fi

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    echo
    echo "--- Optional live spec smoke test (Chart-1) ---"
    if "$PYTHON" scripts/run_spec_smoke_test.py Chart-1; then
        echo "[OK]   run_spec_smoke_test.py"
        pass=$((pass + 1))
    else
        echo "[FAIL] run_spec_smoke_test.py" >&2
        fail=$((fail + 1))
    fi
else
    echo
    echo "[SKIP] OPENAI_API_KEY not set — skipping live smoke test"
    echo "       Export OPENAI_API_KEY and re-run, or run:"
    echo "         ./scripts/run_step2_acceptance.sh Chart-1"
fi

echo
echo "=== Setup summary: ${pass} passed, ${fail} failed ==="
if (( fail > 0 )); then
    echo "Fix the failures above before submitting sbatch." >&2
    exit 1
fi

echo
echo "Next steps:"
echo "  1. export OPENAI_API_KEY=...   # in your shell, not in git"
echo "  2. sbatch examples/run_reinfix_spec.sbatch"
echo "  3. tail -f ${PROJECT_BASE}/logs/reinfix-spec-*.out"
