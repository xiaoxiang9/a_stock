#!/usr/bin/env bash

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PID=""
FRONTEND_PID=""

info() {
  printf '\033[1;32m%s\033[0m\n' "$1"
}

error() {
  printf '\033[1;31m错误：%s\033[0m\n' "$1" >&2
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
  info "前后端服务已停止。"
}

use_node_22() {
  local node_major=""

  if command -v node >/dev/null 2>&1; then
    node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || true)"
  fi

  if [ "$node_major" = "22" ]; then
    return
  fi

  if [ -s "$HOME/.nvm/nvm.sh" ]; then
    # shellcheck disable=SC1090
    . "$HOME/.nvm/nvm.sh"
    nvm use 22 >/dev/null
  elif [ -x "/opt/homebrew/opt/node@22/bin/node" ]; then
    export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
  elif [ -x "/usr/local/opt/node@22/bin/node" ]; then
    export PATH="/usr/local/opt/node@22/bin:$PATH"
  elif [ -x "/tmp/node22-lts/bin/node" ]; then
    export PATH="/tmp/node22-lts/bin:$PATH"
  else
    error "未找到 Node.js 22 LTS，请先执行 nvm install 22 或 brew install node@22。"
    exit 1
  fi

  node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || true)"
  if [ "$node_major" != "22" ]; then
    error "需要 Node.js 22 LTS，当前版本为 $(node --version 2>/dev/null || echo 未知)。"
    exit 1
  fi
}

prepare_backend() {
  if [ ! -x "$BACKEND_DIR/.venv/bin/python" ]; then
    info "正在创建 Python 虚拟环境…"
    python3 -m venv "$BACKEND_DIR/.venv"
  fi

  if [ ! -x "$BACKEND_DIR/.venv/bin/uvicorn" ]; then
    info "正在安装 Python 依赖…"
    "$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"
  fi
}

prepare_frontend() {
  use_node_22

  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    info "正在安装前端依赖…"
    (cd "$FRONTEND_DIR" && npm install)
  fi
}

trap cleanup INT TERM EXIT

prepare_backend
prepare_frontend

info "正在启动 A Stock…"

(
  cd "$BACKEND_DIR"
  exec .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

(
  cd "$FRONTEND_DIR"
  exec npm run dev -- --host 127.0.0.1
) &
FRONTEND_PID=$!

sleep 2

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  error "后端启动失败。"
  exit 1
fi

if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
  error "前端启动失败。"
  exit 1
fi

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
