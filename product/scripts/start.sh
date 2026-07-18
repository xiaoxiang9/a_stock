#!/usr/bin/env bash

# 顶层启动入口。
#
# 职责：
# - 只做子系统启动编排，不承载具体服务启动细节。
# - 依次调用 agents 启动脚本，再并行托管 data 和 app 子系统。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

"$ROOT_DIR/product/agents/scripts/start.sh"
"$ROOT_DIR/product/data/scripts/start.sh" &
DATA_PID=$!
"$ROOT_DIR/product/app/scripts/start.sh" &
APP_PID=$!

cleanup() {
  if kill -0 "$APP_PID" 2>/dev/null; then
    kill "$APP_PID" 2>/dev/null || true
  fi
  if kill -0 "$DATA_PID" 2>/dev/null; then
    kill "$DATA_PID" 2>/dev/null || true
  fi
}

trap cleanup INT TERM EXIT

while true; do
  if ! kill -0 "$APP_PID" 2>/dev/null; then
    wait "$APP_PID" || true
    cleanup
    exit 1
  fi
  if ! kill -0 "$DATA_PID" 2>/dev/null; then
    wait "$DATA_PID" || true
    cleanup
    exit 1
  fi
  sleep 1
done
