#!/usr/bin/env bash
# Start Joern + RAG servers for a ReInFix batch job, wait until ready.
#
# Usage:
#   source scripts/reinfix_runtime_env.sh
#   ./scripts/start_reinfix_services.sh
#
# Writes PIDs to ${REINFIX_SERVICE_DIR}/joern.pid and rag.pid.
# Call ./scripts/stop_reinfix_services.sh on exit (sbatch trap handles this).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REINFIX_DIR="${REINFIX_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
REINFIX_SERVICE_DIR="${REINFIX_SERVICE_DIR:-${REINFIX_DIR}/.service_pids}"
JOERN_PORT="${REINFIX_JOERN_PORT:-8081}"
RAG_PORT="${REINFIX_RAG_PORT:-5000}"
JOERN_HOST="${REINFIX_JOERN_HOST:-0.0.0.0}"
WAIT_SECS="${REINFIX_SERVICE_WAIT_SECS:-120}"

mkdir -p "$REINFIX_SERVICE_DIR"

wait_for_port() {
    local name="$1" port="$2" elapsed=0
    while ! (echo >/dev/tcp/127.0.0.1/"$port") 2>/dev/null; do
        sleep 2
        elapsed=$((elapsed + 2))
        if (( elapsed >= WAIT_SECS )); then
            echo "ERROR: ${name} not ready on port ${port} after ${WAIT_SECS}s" >&2
            return 1
        fi
    done
    echo "${name} ready on port ${port} (${elapsed}s)"
}

start_joern() {
    if [[ -f "${REINFIX_SERVICE_DIR}/joern.pid" ]] && kill -0 "$(cat "${REINFIX_SERVICE_DIR}/joern.pid")" 2>/dev/null; then
        echo "Joern already running (pid $(cat "${REINFIX_SERVICE_DIR}/joern.pid"))"
        return 0
    fi
    if ! command -v joern &>/dev/null; then
        echo "ERROR: joern not in PATH (install Joern and add to PATH)" >&2
        return 1
    fi
    nohup joern --server --server-host "$JOERN_HOST" --server-port "$JOERN_PORT" \
        > "${REINFIX_SERVICE_DIR}/joern.log" 2>&1 &
    echo $! > "${REINFIX_SERVICE_DIR}/joern.pid"
    wait_for_port "Joern" "$JOERN_PORT"
}

start_rag() {
    if [[ -f "${REINFIX_SERVICE_DIR}/rag.pid" ]] && kill -0 "$(cat "${REINFIX_SERVICE_DIR}/rag.pid")" 2>/dev/null; then
        echo "RAG server already running (pid $(cat "${REINFIX_SERVICE_DIR}/rag.pid"))"
        return 0
    fi
    local rag_data="${REINFIX_DIR}/retrieval_base/embedded_cause_97k.csv"
    if [[ ! -f "$rag_data" ]]; then
        echo "ERROR: missing RAG corpus ${rag_data}" >&2
        echo "       Place embedded_cause_97k.csv under ReInFix/retrieval_base/" >&2
        return 1
    fi
    cd "${REINFIX_DIR}/src"
    nohup python rag_search_server.py \
        > "${REINFIX_SERVICE_DIR}/rag.log" 2>&1 &
    echo $! > "${REINFIX_SERVICE_DIR}/rag.pid"
    cd "$REINFIX_DIR"
    wait_for_port "RAG" "$RAG_PORT"
}

echo "=== Starting ReInFix sidecar services ==="
start_joern
start_rag
echo "=== Services up (Joern:${JOERN_PORT}, RAG:${RAG_PORT}) ==="
