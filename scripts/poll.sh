#!/bin/bash
# poll.sh — 轮询会话输出
# 用法: ./poll.sh {session-id} [last_line]
# 如果传了 last_line（行号），只返回该行之后的新内容
# 如果没有新内容，输出空
# 最后一行始终是 total_lines=N 供下次使用

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SESSIONS_DIR="$PROJECT_DIR/sessions"

if [[ $# -lt 1 ]]; then
  echo "用法: $0 {session-id} [last_line]" >&2
  exit 1
fi

SESSION_ID="$1"
SESSION_DIR="$SESSIONS_DIR/$SESSION_ID"

if [[ ! -d "$SESSION_DIR" ]]; then
  echo "错误: 会话 $SESSION_ID 不存在" >&2
  exit 1
fi

OUTPUT_FILE="$SESSION_DIR/output.jsonl"

if [[ ! -f "$OUTPUT_FILE" ]]; then
  echo "total_lines=0"
  exit 0
fi

TOTAL_LINES=$(wc -l < "$OUTPUT_FILE")

if [[ $# -ge 2 ]]; then
  LAST_LINE="$2"
  if [[ "$TOTAL_LINES" -le "$LAST_LINE" ]]; then
    # 没有新内容
    echo "total_lines=$TOTAL_LINES"
    exit 0
  fi
  START=$((LAST_LINE + 1))
  sed -n "${START},${TOTAL_LINES}p" "$OUTPUT_FILE"
fi

echo "total_lines=$TOTAL_LINES"
