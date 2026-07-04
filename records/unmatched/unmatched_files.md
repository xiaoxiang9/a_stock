# 无法直接匹配目录清单

本文件记录本次目录迁移后曾暂不纳入正式目录结构的文件或目录，以及逐项处理结果。

处理原则：

- 不强行归类。
- 先记录现状和疑问。
- 后续逐个分析：清理、归档、并入正式目录，或调整目录规范。

## 1. 本地系统文件

| 路径 | 当前判断 | 处理结果 |
| --- | --- | --- |
| `.DS_Store` | macOS 本地系统文件，不属于项目资产 | 已删除，并已由 `.gitignore` 忽略 |
| `.idea/` | 本地 IDE 配置，不属于项目资产 | 保留为本地目录，不纳入项目结构，已由 `.gitignore` 忽略 |

## 2. 临时安装和外部 skill 包

| 路径 | 当前判断 | 处理结果 |
| --- | --- | --- |
| `.miaoxiang_extract/` | 妙想 skill 解压目录，偏安装过程产物 | 已删除；候选能力说明已沉淀到 `skills/candidates/eastmoney_miaoxiang.md` |
| `.miaoxiang_pkgs/` | 妙想 skill 下载包，偏安装过程产物 | 已删除；不纳入正式项目资产 |
| `.tmp_miaoxiang.md` | 妙想安装临时文档 | 已删除；关键结论已沉淀到 `skills/candidates/eastmoney_miaoxiang.md` |

## 3. 历史经验目录

| 路径 | 当前判断 | 处理结果 |
| --- | --- | --- |
| `.learnings/` | 历史学习沉淀目录，内容与 `knowledge/` 职责接近 | 已并入 `knowledge/agent_learnings_archive.md`，原目录已删除 |

## 4. 运行缓存

| 路径 | 当前判断 | 处理结果 |
| --- | --- | --- |
| `product/jobs/__pycache__/` | Python 运行缓存 | 已删除 |
| `product/tests/__pycache__/` | Python 测试缓存 | 已删除 |
| `product/app/backend/__pycache__/` | Python 运行缓存 | 已删除 |
| `product/app/backend/app/__pycache__/` | Python 运行缓存 | 已删除 |
| `product/app/backend/app/services/__pycache__/` | Python 运行缓存 | 已删除 |

## 5. 需要后续复核的历史设计文档

| 路径 | 当前判断 | 处理结果 |
| --- | --- | --- |
| `records/plans/` | 历史建设计划，已归入构建记录，但内部仍包含旧目录路径 | 保留原貌作为历史记录，不作为当前执行依据 |
| `records/specs/` | 历史设计文档，已归入构建记录，但内部仍包含旧目录路径 | 保留原貌作为历史记录，不作为当前执行依据 |

## 6. 当前结论

- 删除：`.DS_Store`、`.miaoxiang_extract/`、`.miaoxiang_pkgs/`、`.tmp_miaoxiang.md`、运行缓存。
- 并入 `knowledge/`：`.learnings/LEARNINGS.md` 已迁移为 `knowledge/agent_learnings_archive.md`。
- 提炼进 `skills/`：东方财富妙想相关能力已作为候选外部 skill 依赖记录在 `skills/candidates/eastmoney_miaoxiang.md`。
- 保留待观察：`.idea/` 作为本地 IDE 目录保留但不纳入项目资产；`records/plans/` 和 `records/specs/` 作为历史记录保留。
