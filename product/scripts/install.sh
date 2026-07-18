#!/usr/bin/env bash

# 顶层安装入口。
#
# 职责：
# - 只做子系统安装编排，不承载具体安装细节。
# - 依次调用 app、agents、data 三套子系统的安装脚本。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

"$ROOT_DIR/product/app/scripts/install.sh"
"$ROOT_DIR/product/agents/scripts/install.sh"
"$ROOT_DIR/product/data/scripts/install.sh"
