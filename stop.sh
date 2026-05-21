#!/bin/bash
set -euo pipefail

PID_FILE="/tmp/mcp-server.pid"

if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping MCP Server (PID $PID)..."
        kill "$PID"
        for i in $(seq 1 10); do
            if ! kill -0 "$PID" 2>/dev/null; then
                echo "Stopped."
                rm -f "$PID_FILE"
                exit 0
            fi
            sleep 0.5
        done
        echo "Force killing (PID $PID)..."
        kill -9 "$PID" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo "Force stopped."
    else
        echo "PID $PID not running, cleaning up."
        rm -f "$PID_FILE"
    fi
else
    PID=$(pgrep -f "server.py.*--port" 2>/dev/null || true)
    if [[ -n "$PID" ]]; then
        echo "Found MCP Server (PID $PID), stopping..."
        kill "$PID"
        sleep 1
        echo "Stopped."
    else
        echo "MCP Server is not running."
    fi
fi
