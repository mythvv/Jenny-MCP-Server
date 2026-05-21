#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

if [[ ! -d "$VENV" ]]; then
    echo "venv not found, installing dependencies..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

HOST="${MCP_HOST:-0.0.0.0}"
PORT="${MCP_PORT:-31415}"
PID_FILE="/tmp/mcp-server.pid"

if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "MCP Server already running (PID $OLD_PID), stopping..."
        kill "$OLD_PID"
        sleep 1
    fi
    rm -f "$PID_FILE"
fi

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/server.log"

echo "Starting Jenny MCP Server on ${HOST}:${PORT}/mcp"
nohup "$VENV/bin/python" "$SCRIPT_DIR/server.py" --host "$HOST" --port "$PORT" >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "Started PID: $(cat "$PID_FILE")"
