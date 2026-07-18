#!/usr/bin/env bash

# data 子系统刷新脚本。
#
# 职责：
# - 作为月度 PE/PB 初始化和保鲜任务入口。
# - 直接调用 data 子系统的服务层命令，不依赖 app 子系统。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
PYTHON_BIN="$ROOT_DIR/product/data/.venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  printf '错误：未找到 data 子系统 Python 运行环境：%s\n' "$PYTHON_BIN" >&2
  exit 1
fi

case "${1:-}" in
  --bootstrap-all)
    shift
    exec "$PYTHON_BIN" -m product.data.services.stock_valuation_monthly bootstrap-all "$@"
    ;;
  --refresh-all)
    shift
    exec "$PYTHON_BIN" -m product.data.services.stock_valuation_monthly refresh-all "$@"
    ;;
  *)
    exec "$PYTHON_BIN" -m product.data.services.stock_valuation_monthly "$@"
    ;;
esac
