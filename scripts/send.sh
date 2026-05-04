#!/bin/bash
# send.sh — 向会话发送消息
# 用法: ./send.sh {session-id} "消息内容"
#
# 消息以 JSON-RPC request 格式追加到 input.jsonl
# droid 进程通过 tail -f 读取并处理

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SESSIONS_DIR="$PROJECT_DIR/sessions"

if [[ $# -lt 2 ]]; then
  echo "用法: $0 {session-id} \"消息内容\"" >&2
  exit 1
fi

SESSION_ID="$1"
MESSAGE="$2"
SESSION_DIR="$SESSIONS_DIR/$SESSION_ID"

if [[ ! -d "$SESSION_DIR" ]]; then
  echo "错误: 会话 $SESSION_ID 不存在" >&2
  exit 1
fi

# 检查 droid 进程是否在运行
PID_FILE="$SESSION_DIR/pid"
if [[ -f "$PID_FILE" ]]; then
  PID=$(head -1 "$PID_FILE")
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "警告: droid 进程 (PID $PID) 已退出" >&2
  fi
fi

INPUT_FILE="$SESSION_DIR/input.jsonl"
LOG_FILE="$SESSION_DIR/log.md"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TS_DISPLAY=$(date +"%H:%M")

# 生成唯一请求 ID
REQ_ID="msg-$(date +%s)-$$"

# 以 JSON-RPC request 格式追加到 input.jsonl
ESCAPED_MSG=$(echo "$MESSAGE" | jq -Rs '.')
cat >> "$INPUT_FILE" <<ENDMSG
{"type":"request","jsonrpc":"2.0","factoryApiVersion":"1.0.0","factoryProtocolVersion":"1.28.0","id":"${REQ_ID}","method":"droid.add_user_message","params":{"text":${ESCAPED_MSG}}}
ENDMSG

# 同时追加到 log.md
echo "**[${TS_DISPLAY}] 🧑 →** ${MESSAGE}" >> "$LOG_FILE"
