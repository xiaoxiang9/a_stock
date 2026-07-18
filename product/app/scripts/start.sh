#!/usr/bin/env bash

# app 子系统启动脚本。
#
# 职责：
# - 检查公开配置、私密配置和运行依赖。
# - 启动后端和前端。
# - 通过 PID 文件和端口检查进行基础管理。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/product/app/backend"
FRONTEND_DIR="$ROOT_DIR/product/app/frontend"
BACKEND_PYTHON="$BACKEND_DIR/.venv/bin/python"
PRIVATE_CONFIG="$ROOT_DIR/product/app/config/private.local.toml"
CHECKER="$ROOT_DIR/product/app/backend/infrastructure/deployment_checks.py"
MYSQL_COMPOSE_DIR="$ROOT_DIR/product/app/config/mysql"
MYSQL_COMPOSE_FILE="$MYSQL_COMPOSE_DIR/docker-compose.yml"
BACKEND_RELOAD="${ASTOCK_BACKEND_RELOAD:-0}"
RUN_DIR="$ROOT_DIR/product/scripts/.run"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_PID=""
FRONTEND_PID=""

mkdir -p "$RUN_DIR"

info() {
  printf '\033[1;32m%s\033[0m\n' "$1"
}

error() {
  printf '\033[1;31m错误：%s\033[0m\n' "$1" >&2
}

is_running_pid() {
  local pid="$1"
  case "$pid" in
    ''|*[!0-9]*)
      return 1
      ;;
  esac
  kill -0 "$pid" 2>/dev/null
}

read_pid_file() {
  local pid_file="$1"
  if [ ! -f "$pid_file" ]; then
    return 0
  fi
  tr -d '[:space:]' <"$pid_file"
}

kill_process_tree() {
  local pid="$1"
  local child=""

  if ! is_running_pid "$pid"; then
    return 0
  fi

  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    kill_process_tree "$child"
  done

  kill "$pid" 2>/dev/null || true

  for _ in 1 2 3 4 5; do
    if ! is_running_pid "$pid"; then
      return 0
    fi
    sleep 1
  done

  kill -9 "$pid" 2>/dev/null || true
}

stop_pid_file() {
  local label="$1"
  local pid_file="$2"
  local pid=""

  pid="$(read_pid_file "$pid_file")"
  if [ -z "$pid" ]; then
    rm -f "$pid_file"
    return 0
  fi

  if is_running_pid "$pid"; then
    info "检测到已有${label}进程（PID ${pid}），正在停止…"
    kill_process_tree "$pid"
  else
    info "${label} pid 文件已过期，正在清理…"
  fi

  rm -f "$pid_file"
}

command_matches_backend() {
  case "$1" in
    *"$ROOT_DIR"*uvicorn*|*uvicorn*"$ROOT_DIR"*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

command_matches_frontend() {
  case "$1" in
    *"$FRONTEND_DIR"*vite*|*vite*"$FRONTEND_DIR"*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

mysql_is_listening() {
  lsof -nP -iTCP:3306 -sTCP:LISTEN -t >/dev/null 2>&1
}

wait_for_mysql() {
  for _ in 1 2 3 4 5 6; do
    if mysql_is_listening; then
      return 0
    fi
    sleep 2
  done
  return 1
}

ensure_mysql_runtime() {
  info "正在准备 MySQL 运行环境…"

  if mysql_is_listening; then
    info "MySQL 监听已就绪。"
    return 0
  fi

  if command_exists brew; then
    if brew list mysql@8.0 >/dev/null 2>&1; then
      info "检测到 Homebrew 的 mysql@8.0，正在启动服务…"
      brew services start mysql@8.0
    elif brew list mysql >/dev/null 2>&1; then
      info "检测到 Homebrew 的 mysql，正在启动服务…"
      brew services start mysql
    elif command_exists docker && docker info >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 && [ -f "$MYSQL_COMPOSE_FILE" ]; then
      info "检测到 Docker Compose，正在启动本地 MySQL 容器…"
      (cd "$MYSQL_COMPOSE_DIR" && docker compose up -d mysql)
    else
      error "未找到可用的 MySQL Runtime。请先安装 Docker Compose 或 Homebrew MySQL。"
      exit 1
    fi
  else
    error "未找到 Docker Compose、mysql.server 或 Homebrew MySQL。无法启动本地数据库。"
    exit 1
  fi

  if ! wait_for_mysql; then
    error "MySQL 启动后仍不可连接。请检查容器/服务日志。"
    exit 1
  fi

  info "MySQL 连接已就绪。"
}

stop_listening_processes() {
  local label="$1"
  local port="$2"
  local matcher="$3"
  local pid=""
  local cmd=""

  for pid in $(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true); do
    cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    if [ -n "$cmd" ] && "$matcher" "$cmd"; then
      info "检测到占用端口 ${port} 的已有${label}进程（PID ${pid}），正在停止…"
      kill_process_tree "$pid"
    fi
  done
}

pause_existing_project() {
  stop_pid_file "后端" "$BACKEND_PID_FILE"
  stop_pid_file "前端" "$FRONTEND_PID_FILE"
  stop_listening_processes "后端" 8000 command_matches_backend
  stop_listening_processes "前端" 5173 command_matches_frontend
}

collect_errors() {
  local label="$1"
  shift
  local output=""
  if ! output="$("$@" 2>&1)"; then
    error "$label"
    printf '%s\n' "$output" >&2
    exit 1
  fi
}

cleanup() {
  trap - INT TERM EXIT

  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi

  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi

  wait 2>/dev/null || true
  rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"
  info "前后端服务已停止。"
}

check_preflight() {
  info "正在检查启动条件…"

  collect_errors "公开配置检查失败" python3 "$CHECKER" public-config --config "$ROOT_DIR/product/app/config/app.toml"
  collect_errors "私密配置检查失败" python3 "$CHECKER" private-config --config "$PRIVATE_CONFIG"
  collect_errors "后端依赖检查失败" "$BACKEND_PYTHON" "$CHECKER" backend-deps --python "$BACKEND_PYTHON"
  collect_errors "前端依赖检查失败" python3 "$CHECKER" frontend-deps --frontend-dir "$FRONTEND_DIR"
}

start_backend() {
  (
    cd "$ROOT_DIR"
    if [ "$BACKEND_RELOAD" = "1" ]; then
      # 默认关闭自动重载，避免在受限环境里触发文件监听权限问题；
      # 开发调试时可通过 ASTOCK_BACKEND_RELOAD=1 手动打开。
      exec "$BACKEND_PYTHON" -m uvicorn --app-dir "$ROOT_DIR" product.app.backend.app.main:app --reload --host 0.0.0.0 --port 8000
    fi
    exec "$BACKEND_PYTHON" -m uvicorn --app-dir "$ROOT_DIR" product.app.backend.app.main:app --host 0.0.0.0 --port 8000
  ) &
  BACKEND_PID=$!
  printf '%s\n' "$BACKEND_PID" > "$BACKEND_PID_FILE"
}

start_frontend() {
  (
    cd "$FRONTEND_DIR"
    exec npm run dev -- --host 0.0.0.0
  ) &
  FRONTEND_PID=$!
  printf '%s\n' "$FRONTEND_PID" > "$FRONTEND_PID_FILE"
}

wait_until_ready() {
  sleep 2

  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    error "后端启动失败。"
    exit 1
  fi

  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    error "前端启动失败。"
    exit 1
  fi
}

trap cleanup INT TERM EXIT

check_preflight
ensure_mysql_runtime
pause_existing_project
start_backend
start_frontend
wait_until_ready

printf '\n'
info "启动成功："
printf '  前端页面：\033[4mhttp://127.0.0.1:5173\033[0m\n'
printf '  API 文档：\033[4mhttp://127.0.0.1:8000/docs\033[0m\n'
printf '  按 Ctrl+C 同时停止前后端。\n\n'

while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

error "有一个服务意外退出，正在关闭另一个服务。"
exit 1
