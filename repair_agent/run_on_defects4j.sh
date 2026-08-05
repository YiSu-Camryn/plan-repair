#!/bin/bash
# For parallel Slurm jobs, use ./run_isolated_job.sh instead (one copy per job).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [[ -x "$SCRIPT_DIR/venv/bin/python" ]]; then
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

export PATH=$PATH:"$SCRIPT_DIR/defects4j/framework/bin"
cpanm --local-lib=~/perl5 local::lib && eval $(perl -I ~/perl5/lib/perl5/ -Mlocal::lib)
export PERL5LIB="${HOME}/perl5/lib/perl5${PERL5LIB:+:$PERL5LIB}"
for LANG in en_AU.UTF-8 en_GB.UTF-8 C.UTF-8 C; do
  if locale -a 2>/dev/null | grep -q "$LANG"; then
    export LANG
    break
  fi
done
export LC_COLLATE=C

"$PYTHON_CMD" experimental_setups/increment_experiment.py
"$PYTHON_CMD" construct_commands_descriptions.py

CURRENT_EXP=$("$PYTHON_CMD" -c "print(open('experimental_setups/experiments_list.txt').read().splitlines()[-1])")

input="$1"
experiment_file="$2"
model="${3:-gpt-4o-mini}"  # Use $3 if given, otherwise default to gpt-4o-mini
commands_limit=$("$PYTHON_CMD" -c "from autogpt.config.hyperparams_loader import load_hyperparams; print(load_hyperparams('${experiment_file}')['commands_limit'])")
spec_max_attempts=$("$PYTHON_CMD" -c "from autogpt.config.hyperparams_loader import load_hyperparams; print(load_hyperparams('${experiment_file}')['spec_control']['max_attempts'])")
if [[ -z "$commands_limit" ]]; then
    echo "ERROR: failed to read commands_limit from ${experiment_file} (use venv: ${PYTHON_CMD})" >&2
    exit 1
fi

dos2unix "$input"  # Convert file to Unix line endings (if needed)

while IFS= read -r line || [ -n "$line" ]
do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" ]] && continue

    tuple=($line)
    if [[ ${#tuple[@]} -lt 2 ]]; then
        echo "Skipping invalid bugs_list line: $line" >&2
        continue
    fi

    echo ${tuple[0]}, ${tuple[1]}
    "$PYTHON_CMD" prepare_ai_settings.py "${tuple[0]}" "${tuple[1]}"
    if ! "$PYTHON_CMD" checkout_py.py "${tuple[0]}" "${tuple[1]}"; then
        echo "Skipping ${tuple[0]} ${tuple[1]}: checkout failed" >&2
        continue
    fi
    if ! ./run.sh --ai-settings ai_settings.yaml --model "$model" -c -l "$commands_limit" -m json_file --experiment-file "$experiment_file" --spec-max-attempts "$spec_max_attempts"; then
        exit_code=$?
        echo "Run failed for ${tuple[0]} ${tuple[1]} (exit ${exit_code})" >&2
        if [[ "$exit_code" -eq 4 ]]; then
            echo "${tuple[0]} ${tuple[1]}" >> "experimental_setups/${CURRENT_EXP}/spec_failed_bugs.txt"
        fi
        continue
    fi
done < "$input"
