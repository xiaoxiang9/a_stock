# Errors

## [ERR-20260630-001] local_start_script_node_version

**Logged**: 2026-06-30T18:45:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
本地一键启动脚本严格要求 Node.js 22，当前机器默认 Node.js 为 26，导致 `product/scripts/start.sh` 直接退出。

### Error
```text
错误：未找到 Node.js 22 LTS，请先执行 nvm install 22 或 brew install node@22。
```

### Context
- Command/operation attempted: `bash product/scripts/start.sh`
- Environment: `/opt/homebrew/bin/node v26.3.1`
- Project frontend tests/build can run under current Node，但启动脚本的 `use_node_22` 逻辑只接受主版本 22。

### Suggested Fix
评估部署策略：要么安装/固定 Node 22，要么把启动脚本改为读取配置中的允许版本范围，并与 `package.json` engines 保持一致。

### Metadata
- Reproducible: yes
- Related Files: product/scripts/start.sh, product/app/frontend/package.json

### Resolution
- **Resolved**: 2026-06-30T22:40:00+08:00
- **Commit/PR**: local workspace change
- **Notes**: `package.json` engines 放宽为 `>=22`，启动脚本改为接受 Node.js 22 及以上版本。

---

## [ERR-20260630-002] migrated_venv_uvicorn_shebang

**Logged**: 2026-06-30T18:45:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary
项目目录迁移后，后端虚拟环境中的 `uvicorn` 可执行脚本仍指向旧目录，直接执行会报 bad interpreter。

### Error
```text
/bin/bash: product/app/backend/.venv/bin/uvicorn: /Users/bytedance/Documents/codex_projeck/a_stock/backend/.venv/bin/python3: bad interpreter: No such file or directory
```

### Context
- Command/operation attempted: `product/app/backend/.venv/bin/uvicorn ...`
- Workaround used: `product/app/backend/.venv/bin/python -m uvicorn ...`
- Cause: `.venv/bin/uvicorn` shebang 保留迁移前的绝对路径。

### Suggested Fix
重建后端虚拟环境，或在启动脚本中优先使用 `python -m uvicorn`，避免依赖可执行脚本 shebang 的绝对路径。

### Metadata
- Reproducible: yes
- Related Files: product/scripts/start.sh, product/app/backend/.venv/bin/uvicorn

### Resolution
- **Resolved**: 2026-06-30T22:40:00+08:00
- **Commit/PR**: local workspace change
- **Notes**: 启动脚本改用 `.venv/bin/python -m uvicorn product.app.backend.app.main:app`，不再依赖迁移后可能失效的 `uvicorn` shebang。

---

## [ERR-20260630-003] nightly_task_wrong_python_runtime

**Logged**: 2026-06-30T23:00:00+08:00
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
21:00 日报任务在 `runtime.python_path` 为空时默认切换到 `~/.miaoxiang-venv/bin/python`，导致项目后端 venv 中已安装的 AkShare/Tushare 依赖不可用。

### Error
```text
ModuleNotFoundError: No module named 'akshare'
```

### Context
- Command/operation attempted: `product/jobs/muyuan_nightly.py --date 2026-06-30 --force --send-email`
- 项目后端 venv 中 `akshare==1.18.64` 和 `tushare==1.4.29` 可导入。
- 任务脚本重启逻辑选中了妙想 venv，造成实际运行环境和项目依赖环境不一致。

### Suggested Fix
定时任务应优先使用项目自己的后端 venv；外部 skill 专用 venv 只能作为兼容兜底，不能作为项目默认运行环境。

### Metadata
- Reproducible: yes
- Related Files: product/jobs/muyuan_nightly.py, product/core/project_config.py, product/app/backend/requirements.txt

### Resolution
- **Resolved**: 2026-06-30T23:00:00+08:00
- **Commit/PR**: local workspace change
- **Notes**: 配置层不再把空 `runtime.python_path` 默认成妙想 venv；任务层改为优先选择项目后端 venv，并将 Tushare 固化到后端 requirements。

---
