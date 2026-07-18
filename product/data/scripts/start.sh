#!/usr/bin/env bash

# data 子系统启动脚本。
#
# 职责：
# - 启动 data 子系统独立 HTTP API。
# - 仅承载数据查询和刷新，不依赖 app 子系统。
# - 本地启动时优先使用 data 自己的虚拟环境；如果该环境缺少依赖，则回退到 backend 已安装依赖的虚拟环境。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
DATA_PYTHON_BIN="$ROOT_DIR/product/data/.venv/bin/python"
BACKEND_PYTHON_BIN="$ROOT_DIR/product/app/backend/.venv/bin/python"

select_python_bin() {
  if [ -x "$DATA_PYTHON_BIN" ] && "$DATA_PYTHON_BIN" -m uvicorn --version >/dev/null 2>&1; then
    printf '%s' "$DATA_PYTHON_BIN"
    return 0
  fi

  if [ -x "$BACKEND_PYTHON_BIN" ] && "$BACKEND_PYTHON_BIN" -m uvicorn --version >/dev/null 2>&1; then
    printf '%s' "$BACKEND_PYTHON_BIN"
    return 0
  fi

  return 1
}

PYTHON_BIN="$(select_python_bin || true)"

if [ -z "$PYTHON_BIN" ]; then
  printf '错误：未找到 data 子系统 Python 运行环境：%s\n' "$PYTHON_BIN" >&2
  exit 1
fi

exec "$PYTHON_BIN" -m uvicorn product.data.api.main:app --host 0.0.0.0 --port 8010
