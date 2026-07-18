#!/usr/bin/env bash

# agents 子系统启动脚本。
#
# 职责：
# - 保留独立启动入口，便于后续接入多 Agent 研究工作流。
# - 当前阶段仅做占位提示，不阻塞整体系统启动。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
export ROOT_DIR

python3 - <<'PY'
import os
import sys
from pathlib import Path

root_dir = Path(os.environ["ROOT_DIR"])
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from product.agents.config.agents_config import load_agents_config
from product.agents.agents.valuation.providers import AkShareEvidenceProvider
from product.agents.agents.valuation.providers import WebSearchDeepseekEvidenceProvider

config = load_agents_config()
print(f"agents 子系统配置已加载：{config.workflow.default_graph}")
akshare_provider = AkShareEvidenceProvider.from_environment()
print(f"akshare 数据源：{'已启用' if akshare_provider else '未启用'}")
provider = WebSearchDeepseekEvidenceProvider.from_environment()
print(f"websearch-deepseek 数据源：{'已启用' if provider else '未启用'}")
PY

printf 'agents 子系统当前为研究占位层，尚未接入独立守护进程。\n'
