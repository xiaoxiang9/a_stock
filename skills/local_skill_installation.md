# 本机 Skill 全量清单与一键克隆说明

本文档用于把当前机器已经安装的全部本地 skill 克隆到其他机器。

本文件不再区分“核心 / 建议 / 可选”，目标是完整复刻当前机器的本地 skill 目录：

- `~/.codex/skills`
- `~/.agents/skills`

注意：本文档和克隆包不应包含真实 API Key、Token、Cookie 等密钥。目标机器需要自行配置环境变量和登录态。

## 1. 本机 Skill 根目录

| 根目录 | 当前用途 | 克隆策略 |
| --- | --- | --- |
| `~/.codex/skills` | Codex 当前可直接识别的本地 skill | 全量打包、全量恢复 |
| `~/.agents/skills` | Agent / Claude 生态下的本地 skill | 全量打包、全量恢复 |

## 2. 本机已安装 Skill 全量清单

### 2.1 `~/.codex/skills`

| 目录名 | Skill 名称 | 描述 |
| --- | --- | --- |
| `agent-reach` | `agent-reach` | 联网调研、搜索、平台内容获取路由 |
| `brainstorming` | `brainstorming` | 功能、组件和行为变更前的需求探索与设计 |
| `dispatching-parallel-agents` | `dispatching-parallel-agents` | 多个独立任务的并行 agent 调度 |
| `executing-plans` | `executing-plans` | 按已写好的实施计划执行 |
| `find-skills` | `find-skills` | 查询、发现和安装可用 skill |
| `finishing-a-development-branch` | `finishing-a-development-branch` | 开发分支完成后的合并、PR、清理流程 |
| `frontend-skill` | `frontend-skill` | 前端页面、组件和 UI 建设 |
| `mx-data` | `mx-data` | 东方财富妙想金融数据查询 |
| `mx-moni` | `mx-moni` | 东方财富妙想模拟组合管理 |
| `mx-poster` | `mx-poster` | 东方财富社区内容生成与运营 |
| `mx-search` | `mx-search` | 东方财富妙想金融资讯搜索 |
| `mx-xuangu` | `mx-xuangu` | 东方财富妙想选股和板块筛选 |
| `mx-zixuan` | `mx-zixuan` | 东方财富妙想自选股管理 |
| `receiving-code-review` | `receiving-code-review` | 接收并处理代码评审反馈 |
| `requesting-code-review` | `requesting-code-review` | 请求代码评审 |
| `subagent-driven-development` | `subagent-driven-development` | 使用 subagent 执行实施计划 |
| `sync-risk-data` | `sync-risk-data` | 资金安全风险数据标准化与同步 |
| `systematic-debugging` | `systematic-debugging` | 系统化问题定位和修复 |
| `test-driven-development` | `test-driven-development` | 测试驱动开发流程 |
| `tushare` | `tushare` | Tushare 金融数据研究 |
| `using-git-worktrees` | `using-git-worktrees` | 使用 git worktree 隔离开发 |
| `using-superpowers` | `using-superpowers` | skill 使用总入口和会话启动规范 |
| `verification-before-completion` | `verification-before-completion` | 完成前验证，证据先于结论 |
| `web-access` | `web-access` | 联网访问和网页抓取 |
| `writing-plans` | `writing-plans` | 编写实施计划 |
| `writing-skills` | `writing-skills` | 编写、修改和验证 skill |

### 2.2 `~/.agents/skills`

| 目录名 | Skill 名称 | 描述 |
| --- | --- | --- |
| `agent-reach` | `agent-reach` | 联网调研、搜索、平台内容获取路由 |
| `babysit` | `babysit` | 持续跟进 PR、Review 和 CI 状态 |
| `claude-code-plugin-release` | `claude-code-plugin-release` | Claude Code 插件版本发布流程 |
| `create-plan` | `create-plan` | 创建详细实施计划 |
| `design-is` | `design-is` | 基于 Dieter Rams 原则进行设计审查 |
| `do` | `do` | 执行分阶段实施计划 |
| `how-it-works` | `how-it-works` | 解释 claude-mem 工作机制 |
| `knowledge-agent` | `knowledge-agent` | 从记忆构建和查询知识库 |
| `lark-approval` | `lark-approval` | 飞书审批 |
| `lark-apps` | `lark-apps` | 飞书妙搭应用开发与托管 |
| `lark-attendance` | `lark-attendance` | 飞书考勤 |
| `lark-base` | `lark-base` | 飞书多维表格 |
| `lark-calendar` | `lark-calendar` | 飞书日历和会议室 |
| `lark-contact` | `lark-contact` | 飞书通讯录 |
| `lark-doc` | `lark-doc` | 飞书云文档 |
| `lark-drive` | `lark-drive` | 飞书云空间和文件管理 |
| `lark-event` | `lark-event` | 飞书事件监听 |
| `lark-im` | `lark-im` | 飞书即时通讯 |
| `lark-mail` | `lark-mail` | 飞书邮箱 |
| `lark-markdown` | `lark-markdown` | 飞书 Markdown 文件 |
| `lark-minutes` | `lark-minutes` | 飞书妙记 |
| `lark-note` | `lark-note` | 飞书会议纪要直查 |
| `lark-okr` | `lark-okr` | 飞书 OKR |
| `lark-openapi-explorer` | `lark-openapi-explorer` | 飞书原生 OpenAPI 探索 |
| `lark-shared` | `lark-shared` | 飞书 CLI 认证和共享能力 |
| `lark-sheets` | `lark-sheets` | 飞书电子表格 |
| `lark-skill-maker` | `lark-skill-maker` | 创建 lark-cli 自定义 skill |
| `lark-slides` | `lark-slides` | 飞书幻灯片 |
| `lark-task` | `lark-task` | 飞书任务 |
| `lark-vc` | `lark-vc` | 飞书视频会议历史记录和纪要 |
| `lark-vc-agent` | `lark-vc-agent` | 飞书视频会议会中能力 |
| `lark-whiteboard` | `lark-whiteboard` | 飞书白板 |
| `lark-wiki` | `lark-wiki` | 飞书知识库 |
| `lark-workflow-meeting-summary` | `lark-workflow-meeting-summary` | 会议纪要整理工作流 |
| `lark-workflow-standup-report` | `lark-workflow-standup-report` | 日程待办摘要工作流 |
| `learn-codebase` | `learn-codebase` | 阅读并理解代码库 |
| `make-plan` | `make-plan` | 创建分阶段实施计划 |
| `mem-search` | `mem-search` | 搜索 claude-mem 记忆 |
| `oh-my-issues` | `oh-my-issues` | GitHub Issue 聚类和治理 |
| `pathfinder` | `pathfinder` | 架构路径梳理和统一方案 |
| `self-improvement` | `self-improvement` | 错误、修正和经验沉淀 |
| `smart-explore` | `smart-explore` | 基于 AST 的代码结构探索 |
| `standup` | `standup` | 跨分支、PR、工作区的站会式梳理 |
| `timeline-report` | `timeline-report` | 项目历史时间线报告 |
| `weekly-digests` | `weekly-digests` | 项目周度叙事摘要 |
| `what-the` | `what-the` | 技术内容白话解释 |
| `wowerpoint` | `wowerpoint` | 将文档转为叙事幻灯片 PDF |

## 3. 源机器一键打包

在当前机器执行以下命令，生成本机 skill 全量克隆包：

```bash
cd "$HOME"

tar \
  --exclude='*/__pycache__' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  -czf local-skills-full-clone-$(date +%Y%m%d).tgz \
  .codex/skills \
  .agents/skills
```

生成文件示例：

```text
~/local-skills-full-clone-20260704.tgz
```

复制到目标机器：

```bash
scp ~/local-skills-full-clone-20260704.tgz user@target-host:~/
```

## 4. 目标机器一键恢复

以下脚本会以“镜像恢复”方式克隆 skill：

- 先备份目标机器已有的 `~/.codex/skills` 和 `~/.agents/skills`。
- 再解压当前机器的 skill 包。
- 不做筛选，不区分用途，完整恢复两套 skill 目录。
- 同时安装常见 Python 依赖，便于 Tushare、东方财富妙想、飞书等 Python skill 运行。

使用方式：

```bash
bash restore-local-skills-full.sh ~/local-skills-full-clone-20260704.tgz
```

脚本内容：

```bash
#!/usr/bin/env bash
set -euo pipefail

ARCHIVE="${1:-}"
if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
  echo "用法: bash restore-local-skills-full.sh /path/to/local-skills-full-clone-YYYYMMDD.tgz"
  exit 1
fi

BACKUP_DIR="$HOME/skill-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -d "$HOME/.codex/skills" ]; then
  mkdir -p "$BACKUP_DIR/.codex"
  mv "$HOME/.codex/skills" "$BACKUP_DIR/.codex/skills"
fi

if [ -d "$HOME/.agents/skills" ]; then
  mkdir -p "$BACKUP_DIR/.agents"
  mv "$HOME/.agents/skills" "$BACKUP_DIR/.agents/skills"
fi

mkdir -p "$HOME/.codex" "$HOME/.agents" "$HOME/.openclaw/workspace/mx_data/output"

echo "正在解压 skill 克隆包: $ARCHIVE"
tar -xzf "$ARCHIVE" -C "$HOME"

echo "正在准备 Python skill 运行环境: $HOME/.miaoxiang-venv"
python3 -m venv "$HOME/.miaoxiang-venv"
"$HOME/.miaoxiang-venv/bin/python" -m pip install --upgrade pip
"$HOME/.miaoxiang-venv/bin/python" -m pip install requests pandas openpyxl tushare pyyaml

PROFILE_FILE="$HOME/.bash_profile"
if [ -n "${ZSH_VERSION:-}" ]; then
  PROFILE_FILE="$HOME/.zshrc"
fi

if ! grep -q '### Local skills full clone env ###' "$PROFILE_FILE" 2>/dev/null; then
  {
    echo ''
    echo '### Local skills full clone env ###'
    echo 'export PATH="$HOME/.miaoxiang-venv/bin:$PATH"'
    echo 'export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"'
    echo 'export OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"'
  } >> "$PROFILE_FILE"
fi

echo "恢复完成。原 skill 目录备份在: $BACKUP_DIR"
echo "请执行: source \"$PROFILE_FILE\""
echo "如需使用金融和飞书类 skill，请在目标机器自行配置对应 Token / 登录态。"
```

## 5. 目标机器密钥和登录态配置

克隆 skill 文件不等于克隆密钥、账号登录态或远端授权。

目标机器仍需按需配置：

```bash
export TUSHARE_TOKEN="目标机器自己的 Tushare Token"
export MX_APIKEY="目标机器自己的东方财富妙想 API Key"
```

飞书类 skill 需要在目标机器重新执行对应 CLI 登录或授权流程。

## 6. 恢复后验证

### 6.1 校验 skill 文件数量

```bash
find "$HOME/.codex/skills" -maxdepth 2 -name SKILL.md | sort
find "$HOME/.agents/skills" -maxdepth 2 -name SKILL.md | sort
```

当前源机器参考数量：

```text
~/.codex/skills：26 个 SKILL.md
~/.agents/skills：47 个 SKILL.md
```

### 6.2 校验关键目录存在

```bash
test -f "$HOME/.codex/skills/tushare/SKILL.md"
test -f "$HOME/.codex/skills/mx-data/SKILL.md"
test -f "$HOME/.codex/skills/mx-search/SKILL.md"
test -f "$HOME/.agents/skills/lark-doc/SKILL.md"
test -f "$HOME/.agents/skills/mem-search/SKILL.md"
echo "Skill clone path check OK"
```

### 6.3 校验 Python 依赖

```bash
"$HOME/.miaoxiang-venv/bin/python" - <<'PY'
import pandas
import requests
import tushare
import yaml
print("Python skill dependencies OK")
PY
```

### 6.4 校验金融 skill 可运行

```bash
cd "$HOME/.codex/skills/mx-search"
"$HOME/.miaoxiang-venv/bin/python" ./mx_search.py "东方财富最新公告"
```

如果提示未配置 `MX_APIKEY`、`401` 或额度限制，说明文件恢复成功，但目标机器的账号凭证仍需配置。

## 7. 更新克隆包

源机器新增、删除或修改 skill 后，重新执行第 3 节打包命令即可生成新的克隆包。

如果需要查看当前机器最新全量清单，可执行：

```bash
find "$HOME/.codex/skills" -maxdepth 2 -name SKILL.md | sort
find "$HOME/.agents/skills" -maxdepth 2 -name SKILL.md | sort
```
