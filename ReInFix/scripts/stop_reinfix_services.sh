#!/usr/bin/env bash
# Stop Joern + RAG started by start_reinfix_services.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REINFIX_DIR="${REINFIX_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
REINFIX_SERVICE_DIR="${REINFIX_SERVICE_DIR:-${REINFIX_DIR}/.service_pids}"

stop_pidfile() {
    local label="$1" file="$2"
    if [[ -f "$file" ]]; then
        local pid
        pid="$(cat "$file")"
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            echo "Stopped ${label} (pid ${pid})"
        fi
        rm -f "$file"
    fi
}

stop_pidfile "Joern" "${REINFIX_SERVICE_DIR}/joern.pid"
stop_pidfile "RAG" "${REINFIX_SERVICE_DIR}/rag.pid"
