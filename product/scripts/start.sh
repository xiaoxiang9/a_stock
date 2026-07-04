#!/usr/bin/env bash

# A Stock 本地一键启动脚本。
#
# 职责：
# - 准备后端 Python 虚拟环境和前端 Node.js 依赖。
# - 同时启动 FastAPI 后端和 Vite 前端开发服务器。
# - 捕获退出信号并清理子进程。
#
# 边界：
# - 本脚本只服务本地开发启动，不替代正式服务器部署脚本。
# - 不写入业务数据，也不执行投研分析任务。

set -e

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/product/app/backend"
FRONTEND_DIR="$ROOT_DIR/product/app/frontend"
BACKEND_PID=""
FRONTEND_PID=""

# 本脚本用于本地一键启动，不写入部署状态；退出时会清理前后端子进程。
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

ensure_node_runtime() {
  # 前端依赖要求 Node.js 22 及以上；不要强制锁死 22，避免新版本 Node 被误判不可用。
  local node_major=""

  if command -v node >/dev/null 2>&1; then
    node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || true)"
  fi

  if [ -n "$node_major" ] && [ "$node_major" -ge 22 ] 2>/dev/null; then
    return
  fi

  if [ -s "$HOME/.nvm/nvm.sh" ]; then
    # shellcheck disable=SC1090
    . "$HOME/.nvm/nvm.sh"
    nvm use 22 >/dev/null || nvm use --lts >/dev/null
  elif [ -x "/opt/homebrew/opt/node@22/bin/node" ]; then
    export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
  elif [ -x "/usr/local/opt/node@22/bin/node" ]; then
    export PATH="/usr/local/opt/node@22/bin:$PATH"
  elif [ -x "/tmp/node22-lts/bin/node" ]; then
    export PATH="/tmp/node22-lts/bin:$PATH"
  else
    error "未找到 Node.js 22 及以上版本，请先执行 nvm install 22 或 brew install node@22。"
    exit 1
  fi

  node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || true)"
  if [ -z "$node_major" ] || [ "$node_major" -lt 22 ] 2>/dev/null; then
    error "需要 Node.js 22 及以上版本，当前版本为 $(node --version 2>/dev/null || echo 未知)。"
    exit 1
  fi
}

prepare_backend() {
  # 后端虚拟环境放在 backend/.venv，避免污染系统 Python。
  if [ ! -x "$BACKEND_DIR/.venv/bin/python" ]; then
    info "正在创建 Python 虚拟环境…"
    python3 -m venv "$BACKEND_DIR/.venv"
  fi

  # 每次启动前同步 requirements；pip 会跳过已满足依赖，避免新增依赖后旧 venv 漏装。
  info "正在校验 Python 依赖…"
  "$BACKEND_DIR/.venv/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt"
}

prepare_frontend() {
  # 仅在 node_modules 不存在时安装依赖，日常启动保持快速。
  ensure_node_runtime

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
  export PYTHONPATH="$ROOT_DIR"
  # 使用 python -m uvicorn，避免目录迁移后 .venv/bin/uvicorn shebang 仍指向旧路径。
  exec .venv/bin/python -m uvicorn product.app.backend.app.main:app --reload --host 127.0.0.1 --port 8000
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
