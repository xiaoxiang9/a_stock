#!/usr/bin/env bash

# agents 子系统安装脚本。
#
# 职责：
# - 保留独立安装入口，便于后续接入 LangGraph 和研究模型依赖。
# - 当前阶段仅做目录和配置存在性确认。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
CONFIG_DIR="$ROOT_DIR/product/agents/config"

if command -v websearch-deepseek >/dev/null 2>&1; then
    WEBSEARCH_STATUS="已安装"
else
    WEBSEARCH_STATUS="未安装，请先执行 npm install -g websearch-deepseek"
fi

if python3 -c 'import akshare' >/dev/null 2>&1; then
    AKSHARE_STATUS="已安装"
else
    AKSHARE_STATUS="未安装"
fi

printf 'agents 子系统安装完成，配置目录：%s\n' "$CONFIG_DIR"
printf 'AkShare 状态：%s\n' "$AKSHARE_STATUS"
printf 'websearch-deepseek 状态：%s\n' "$WEBSEARCH_STATUS"
