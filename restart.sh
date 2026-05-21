#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Restarting MCP Server..."
bash "$SCRIPT_DIR/stop.sh"
sleep 1
bash "$SCRIPT_DIR/start.sh"
