# 全局待办清单

## 记录规则

每个 todo 需要记录提出背景、目标、优先级、状态和归属模块。

## 当前待办

| ID | 状态 | 优先级 | 归属 | 提出背景 | 目标 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- |
| TODO-20260630-001 | 已完成 | 高 | 项目目录治理 | 项目需要避免目录爆炸，新增文件需要按固定目录检查确认 | 固化项目目录规范与新增文件检查规则 | 已写入 `records/project_structure.md`、`records/project_conventions.md` 和 `AGENTS.md` |
| TODO-20260630-002 | 已完成 | 高 | 项目目录迁移 | 需要基于新目录结构对项目进行改造，并单列无法匹配的文档 | 迁移明确归属的目录，生成无法匹配清单 | 已迁移到 `product/`、`records/`、`knowledge/`、`skills/`，清单见 `records/unmatched/unmatched_files.md` |
| TODO-20260630-003 | 已完成 | 中 | 目录治理 | 需要逐项分析无法匹配清单，决定删除、并入 knowledge 或提炼进 skills | 清理临时产物，归档历史经验，记录候选外部 skill | 已更新 `records/unmatched/unmatched_files.md`、`knowledge/agent_learnings_archive.md`、`skills/candidates/eastmoney_miaoxiang.md` |
| TODO-20260630-004 | 已完成 | 中 | skill 管理 | 需要在 `skills/` 下说明项目引用了哪些 skill，比如妙想系列、Tushare 等 | 建立项目引用 skill 清单 | 已新增 `skills/referenced_skills.md`，并更新 `skills/README.md` |
| TODO-20260630-005 | 已完成 | 低 | 代码可维护性 | 需要给代码加上中文注释，便于后续持续迭代和迁移复用 | 给关键生产代码补充中文注释，说明模块职责、数据流和模型边界 | 已补充 `product/core/`、`product/app/`、`product/jobs/`、`product/scripts/` 关键代码注释 |
| TODO-20260630-006 | 已完成 | 中 | 代码规范 | 需要先对齐代码注释规范，后续涉及代码变更都按规范补充注释 | 沉淀代码注释规范，明确中文注释、文件级说明、方法注释、复杂逻辑和更新规则 | 已更新 `records/project_conventions.md` 和 `AGENTS.md` |
| TODO-20260630-007 | 已完成 | 中 | 代码可维护性 | 需要对现有代码按新注释规范补充一轮注释 | 为现有 Python、JavaScript、Vue、Shell 代码补齐文件级说明、方法说明和复杂逻辑注释 | 已完成 `product/` 下现有代码注释补齐，并通过测试验证 |
| TODO-20260630-008 | 已完成 | 高 | 部署脚本 | 一键启动脚本受 Node 版本和迁移后 uvicorn shebang 影响，无法稳定启动 | 修复本地一键启动脚本，使前后端可通过一个命令稳定启动 | 已放宽 Node engines 到 `>=22`，脚本改用 `python -m uvicorn`，并完成启动验证 |
| TODO-20260630-009 | 已完成 | 高 | 定时任务 | 需要执行 21:00 定时任务并发送日报，验证完整功能链路 | 跑通牧原股份日报生成、模型分析、HTML 邮件发送和依赖环境 | 已发送 2026-06-30 日报到 `376597874@qq.com`，并修复任务 Python 环境与依赖配置 |
| TODO-20260630-010 | 已完成 | 中 | 模型配置 | 需要将 DeepSeek 运行模型从 flash 切换为 pro | 更新全局模型配置、公共层默认模型和相关测试文档 | 已将 `deepseek-v4-flash` 全部替换为 `deepseek-v4-pro` 并完成验证 |
| TODO-20260630-011 | 已完成 | 高 | 数据层标准化 | 需要标准化数据层，确保分析依赖的数据可置信，且数据能力不绑定具体标的 | 建立通用数据能力清单，明确查询参数、来源优先级、校验来源、时间和单位口径 | 已新增 `product/data/catalog/data_capabilities.md`，并同步更新数据层入口和项目约定 |
| TODO-20260630-012 | 已完成 | 高 | 数据层标准化 | 需要将数据获取统一在数据层实现，并生成对应测试脚本 | 把日报、猪周期和市场指标取数从任务层/表达层迁入 `product/data/fetchers/`，任务层只编排 | 已新增通用 fetcher 与 `product/tests/test_data_layer.py`，并完成相关测试验证 |
