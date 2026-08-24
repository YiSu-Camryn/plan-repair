#!/bin/bash
# Spec-only pass@k experiment (RepairAgent generate_spec + verifier, no repair loop).
# Environment matches run_on_defects4j.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [[ -x "$SCRIPT_DIR/venv/bin/python" ]]; then
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

export PATH="$PATH:$SCRIPT_DIR/defects4j/framework/bin"
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

if ! command -v defects4j &>/dev/null; then
    echo "ERROR: defects4j not in PATH. Expected: $SCRIPT_DIR/defects4j/framework/bin" >&2
    exit 1
fi

ABLATION="experimental_setups/spec_attempts_ablation"
exec "$PYTHON_CMD" "$ABLATION/run_spec_attempts_experiment.py" \
    --bugs-file "$ABLATION/sample_40.txt" \
    --max-attempts 5 \
    --model "${REPAIRAGENT_MODEL:-deepseek.v3.2}" \
    --summarize \
    "$@"
