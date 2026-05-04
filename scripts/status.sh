#!/bin/bash
# status.sh — 查看会话状态
# 用法: ./status.sh              # 列出所有会话
#       ./status.sh {session-id} # 显示特定会话详情

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SESSIONS_DIR="$PROJECT_DIR/sessions"

if [[ $# -ge 1 && "$1" != "" ]]; then
  # 显示特定会话详情
  SESSION_ID="$1"
  SESSION_DIR="$SESSIONS_DIR/$SESSION_ID"

  if [[ ! -d "$SESSION_DIR" ]]; then
    echo "错误: 会话 $SESSION_ID 不存在" >&2
    exit 1
  fi

  # 活跃判断
  ACTIVE="inactive"
  PID_FILE="$SESSION_DIR/pid"
  if [[ -f "$PID_FILE" ]]; then
    PID=$(head -1 "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      ACTIVE="active"
    fi
  fi

  # 统计消息数
  INPUT_LINES=0
  OUTPUT_LINES=0
  [[ -f "$SESSION_DIR/input.jsonl" ]] && INPUT_LINES=$(wc -l < "$SESSION_DIR/input.jsonl")
  [[ -f "$SESSION_DIR/output.jsonl" ]] && OUTPUT_LINES=$(wc -l < "$SESSION_DIR/output.jsonl")

  # 最后活动时间
  LAST_ACTIVITY="unknown"
  if [[ -f "$SESSION_DIR/output.jsonl" && -s "$SESSION_DIR/output.jsonl" ]]; then
    LAST_ACTIVITY=$(stat -c "%y" "$SESSION_DIR/output.jsonl" 2>/dev/null | cut -d'.' -f1 || echo "unknown")
  elif [[ -f "$SESSION_DIR/input.jsonl" && -s "$SESSION_DIR/input.jsonl" ]]; then
    LAST_ACTIVITY=$(stat -c "%y" "$SESSION_DIR/input.jsonl" 2>/dev/null | cut -d'.' -f1 || echo "unknown")
  fi

  # PID 信息
  PID_DISPLAY="N/A"
  if [[ -f "$PID_FILE" ]]; then
    PID_DISPLAY=$(head -1 "$PID_FILE")
  fi

  echo "会话: $SESSION_ID"
  echo "状态: $ACTIVE"
  echo "PID:  $PID_DISPLAY"
  echo "发送消息数: $INPUT_LINES"
  echo "接收消息数: $OUTPUT_LINES"
  echo "最后活动:   $LAST_ACTIVITY"
  echo "日志: $SESSION_DIR/log.md"

else
  # 列出所有会话
  if [[ ! -d "$SESSIONS_DIR" ]] || [[ -z "$(ls -A "$SESSIONS_DIR" 2>/dev/null)" ]]; then
    echo "无会话记录"
    exit 0
  fi

  printf "%-38s %-10s %-8s %-8s %s\n" "SESSION-ID" "STATUS" "SENT" "RECV" "LAST-ACTIVITY"
  printf "%-38s %-10s %-8s %-8s %s\n" "----------" "------" "----" "----" "-------------"

  for SESSION_DIR in "$SESSIONS_DIR"/*/; do
    [[ ! -d "$SESSION_DIR" ]] && continue
    SESSION_ID=$(basename "$SESSION_DIR")

    # 活跃判断
    ACTIVE="inactive"
    PID_FILE="$SESSION_DIR/pid"
    if [[ -f "$PID_FILE" ]]; then
      PID=$(head -1 "$PID_FILE")
      if kill -0 "$PID" 2>/dev/null; then
        ACTIVE="active"
      fi
    fi

    # 消息数
    INPUT_LINES=0
    OUTPUT_LINES=0
    [[ -f "$SESSION_DIR/input.jsonl" ]] && INPUT_LINES=$(wc -l < "$SESSION_DIR/input.jsonl")
    [[ -f "$SESSION_DIR/output.jsonl" ]] && OUTPUT_LINES=$(wc -l < "$SESSION_DIR/output.jsonl")

    # 最后活动
    LAST_ACTIVITY="unknown"
    if [[ -f "$SESSION_DIR/output.jsonl" && -s "$SESSION_DIR/output.jsonl" ]]; then
      LAST_ACTIVITY=$(stat -c "%y" "$SESSION_DIR/output.jsonl" 2>/dev/null | cut -d'.' -f1 || echo "unknown")
    elif [[ -f "$SESSION_DIR/input.jsonl" && -s "$SESSION_DIR/input.jsonl" ]]; then
      LAST_ACTIVITY=$(stat -c "%y" "$SESSION_DIR/input.jsonl" 2>/dev/null | cut -d'.' -f1 || echo "unknown")
    fi

    printf "%-38s %-10s %-8s %-8s %s\n" "$SESSION_ID" "$ACTIVE" "$INPUT_LINES" "$OUTPUT_LINES" "$LAST_ACTIVITY"
  done
fi
