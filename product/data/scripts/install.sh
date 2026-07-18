#!/usr/bin/env bash

# data 子系统安装脚本。
#
# 职责：
# - 初始化 data 子系统自己的私密配置模板。
# - 保留独立安装入口，便于后续接入数据加工与数据服务依赖。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
CONFIG_DIR="$ROOT_DIR/product/data/config"
PRIVATE_CONFIG="$CONFIG_DIR/private.local.toml"
PRIVATE_CONFIG_EXAMPLE="$CONFIG_DIR/private.local.toml.example"
DATA_DIR="$ROOT_DIR/product/data"
VENV_DIR="$DATA_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"

if [ ! -f "$PRIVATE_CONFIG" ] && [ -f "$PRIVATE_CONFIG_EXAMPLE" ]; then
  cp "$PRIVATE_CONFIG_EXAMPLE" "$PRIVATE_CONFIG"
  printf '已初始化 data 私密配置模板：%s\n' "$PRIVATE_CONFIG"
else
  printf 'data 私密配置已存在：%s\n' "$PRIVATE_CONFIG"
fi

if [ ! -x "$PYTHON_BIN" ]; then
  python3 -m venv "$VENV_DIR"
fi

"$PYTHON_BIN" -m pip install -r "$DATA_DIR/requirements.txt"

printf 'data 子系统安装完成，配置目录：%s\n' "$CONFIG_DIR"
