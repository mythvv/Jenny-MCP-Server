#!/bin/bash
# start.sh — 启动 droid stream-jsonrpc 会话
# 用法: ./start.sh                    # 新建会话，输出 session-id
#       ./start.sh {session-id}       # 恢复已有会话
#
# JSON-RPC 协议流程:
# 1. droid exec 启动后自动处理 initialize_session
# 2. 用户通过 send.sh 追加消息到 input.jsonl
# 3. tail -f 将 input.jsonl 中的 JSON-RPC 消息转发到 droid stdin
# 4. droid 输出 JSON-RPC 响应到 output.jsonl

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SESSIONS_DIR="$PROJECT_DIR/sessions"
WORKSPACE="$PROJECT_DIR/workspace"
CONFIG="$PROJECT_DIR/config/defaults.json"

mkdir -p "$SESSIONS_DIR" "$WORKSPACE"

# 读取默认配置
MODEL=$(jq -r '.model // "claude-sonnet-4-6"' "$CONFIG")
AUTO_LEVEL=$(jq -r '.auto_level // "high"' "$CONFIG")
REASONING=$(jq -r '.reasoning_effort // ""' "$CONFIG")
CWD=$(jq -r '.cwd // "'"$WORKSPACE"'"' "$CONFIG")

# 确定会话 ID
if [[ $# -ge 1 && -n "$1" ]]; then
  SESSION_ID="$1"
  SESSION_DIR="$SESSIONS_DIR/$SESSION_ID"
  if [[ ! -d "$SESSION_DIR" ]]; then
    echo "错误: 会话 $SESSION_ID 不存在" >&2
    exit 1
  fi
  # 幂等：如果进程仍在运行，不重复启动
  PID_FILE="$SESSION_DIR/pid"
  if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(head -1 "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
      echo "$SESSION_ID"
      exit 0
    fi
  fi
else
  SESSION_ID=$(cat /proc/sys/kernel/random/uuid)
  SESSION_DIR="$SESSIONS_DIR/$SESSION_ID"
fi

mkdir -p "$SESSION_DIR"
touch "$SESSION_DIR/input.jsonl" "$SESSION_DIR/output.jsonl"

# 初始化 log.md（新会话才写头部）
LOG_FILE="$SESSION_DIR/log.md"
if [[ ! -f "$LOG_FILE" || ! -s "$LOG_FILE" ]]; then
  cat > "$LOG_FILE" <<EOF
# Jenny-Droid Session: ${SESSION_ID}

**Started:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")
**Model:** ${MODEL}
**Auto Level:** ${AUTO_LEVEL}

---

EOF
fi

MACHINE_ID="jenny-droid-$(hostname)"

# 构建 droid exec 命令
DROID_CMD=(droid exec)
DROID_CMD+=(--input-format stream-jsonrpc)
DROID_CMD+=(--output-format stream-jsonrpc)
DROID_CMD+=(--auto "$AUTO_LEVEL")
DROID_CMD+=(--model "$MODEL")
DROID_CMD+=(--cwd "$CWD")

[[ -n "$REASONING" && "$REASONING" != "null" && "$REASONING" != "none" ]] && DROID_CMD+=(--reasoning-effort "$REASONING")

# 写入初始 initialize_session 消息到 input.jsonl（仅新会话）
INIT_FILE="$SESSION_DIR/.initialized"
if [[ ! -f "$INIT_FILE" ]]; then
  cat > "$SESSION_DIR/input.jsonl" <<EOF
{"type":"request","jsonrpc":"2.0","factoryApiVersion":"1.0.0","factoryProtocolVersion":"1.28.0","id":"init-1","method":"droid.initialize_session","params":{"machineId":"${MACHINE_ID}","cwd":"${CWD}","sessionId":"${SESSION_ID}","autonomyLevel":"${AUTO_LEVEL}","modelId":"${MODEL}"}}
EOF
  touch "$INIT_FILE"
fi

# 后台启动：tail -f input.jsonl 管道到 droid exec
# 关键：stdout/stderr 重定向到 /dev/null 避免干扰主进程 stdout
(
  tail -n +1 -f "$SESSION_DIR/input.jsonl" 2>/dev/null | \
  "${DROID_CMD[@]}" 2>> "$SESSION_DIR/stderr.log" | \
  while IFS= read -r line; do
    # 追加原始行到 output.jsonl
    echo "$line" >> "$SESSION_DIR/output.jsonl"

    # 解析并格式化到 log.md
    ts=$(date +"%H:%M")
    msg_type=$(echo "$line" | jq -r '.type // "unknown"' 2>/dev/null || echo "unknown")
    method=$(echo "$line" | jq -r '.method // ""' 2>/dev/null || echo "")

    case "$msg_type" in
      response)
        # 检查是否是错误响应
        has_error=$(echo "$line" | jq 'has("error")' 2>/dev/null || echo "false")
        if [[ "$has_error" == "true" ]]; then
          err_msg=$(echo "$line" | jq -r '.error.message // "unknown error"' 2>/dev/null || echo "unknown error")
          echo "**[${ts}] ❌ error:** ${err_msg}" >> "$LOG_FILE"
        else
          result_keys=$(echo "$line" | jq -r '.result | keys[]' 2>/dev/null || echo "")
          if echo "$result_keys" | grep -q 'finalText'; then
            final_text=$(echo "$line" | jq -r '.result.finalText // ""' 2>/dev/null || echo "")
            if [[ -n "$final_text" ]]; then
              echo "**[${ts}] 🤖 →** ${final_text}" >> "$LOG_FILE"
            fi
          fi
        fi
        ;;
      notification)
        notif_type=$(echo "$line" | jq -r '.params.notification.type // .method // "notification"' 2>/dev/null || echo "notification")
        case "$notif_type" in
          mcp_status_changed|settings_updated|session_token_usage_changed|droid_working_state_changed|session_title_updated)
            # 静默通知，不记录到日志
            ;;
          assistant_text_delta)
            # 流式文本增量 - 拼接到当前行
            delta=$(echo "$line" | jq -r '.params.notification.textDelta // ""' 2>/dev/null || echo "")
            if [[ -n "$delta" ]]; then
              # 追加到助手消息缓冲区
              echo -n "$delta" >> "$SESSION_DIR/.assistant_buffer"
            fi
            ;;
          create_message)
            # 新消息创建 - 如果之前有助手文本，先落盘
            role=$(echo "$line" | jq -r '.params.notification.role // .params.notification.message.role // ""' 2>/dev/null || echo "")
            if [[ -f "$SESSION_DIR/.assistant_buffer" && -s "$SESSION_DIR/.assistant_buffer" ]]; then
              echo "**[${ts}] 🤖 →** $(cat "$SESSION_DIR/.assistant_buffer")" >> "$LOG_FILE"
              rm -f "$SESSION_DIR/.assistant_buffer"
            fi
            ;;
          *)
            echo "**[${ts}] 📦 ${notif_type}**" >> "$LOG_FILE"
            ;;
        esac
        ;;
      *)
        echo "**[${ts}] 📦 ${msg_type}**" >> "$LOG_FILE"
        ;;
    esac
  done

  # droid 退出后记录
  echo "" >> "$LOG_FILE"
  echo "---" >> "$LOG_FILE"
  echo "**Session ended:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$LOG_FILE"
) >/dev/null 2>&1 &

DROID_PID=$!
echo "$DROID_PID" > "$SESSION_DIR/pid"

# 等待短暂时间确保进程启动
sleep 0.5

# 检查进程是否仍在运行
if ! kill -0 "$DROID_PID" 2>/dev/null; then
  echo "错误: droid 进程启动失败，查看 $SESSION_DIR/stderr.log" >&2
  cat "$SESSION_DIR/stderr.log" 2>/dev/null >&2
  exit 1
fi

echo "$SESSION_ID"
