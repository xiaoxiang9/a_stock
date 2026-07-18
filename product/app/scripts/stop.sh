#!/usr/bin/env bash

# app 子系统停止脚本。
#
# 职责：
# - 停止由 start.sh 拉起的后端和前端进程。
# - 清理 PID 文件。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
RUN_DIR="$ROOT_DIR/product/scripts/.run"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"

is_running_pid() {
  local pid="$1"
  case "$pid" in
    ''|*[!0-9]*)
      return 1
      ;;
  esac
  kill -0 "$pid" 2>/dev/null
}

stop_pid_file() {
  local pid_file="$1"
  local pid=""

  if [ ! -f "$pid_file" ]; then
    return 0
  fi

  pid="$(tr -d '[:space:]' <"$pid_file")"
  if [ -n "$pid" ] && is_running_pid "$pid"; then
    kill "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
}

stop_pid_file "$BACKEND_PID_FILE"
stop_pid_file "$FRONTEND_PID_FILE"
printf 'app 子系统已停止。\n'
