# 建设日志

## 2026-06-30

### 固化项目目录规范

- 背景：项目需要区分项目产物、项目构建记录、项目构建经验沉淀和项目构建 skill，避免目录随着功能增长而失控。
- 建设内容：新增 `records/project_structure.md`，明确一级目录、项目产物分层、数据层优先级和新增文件检查清单。
- 建设内容：新增 `product/`、`records/`、`knowledge/`、`skills/` 的说明文件，先沉淀目录语义，不迁移已有代码链路。
- 建设内容：更新 `records/project_conventions.md` 和 `AGENTS.md`，要求后续新增文件先按目录规范检查确认。
- 后续事项：再讨论 `product/modules/` 的业务模块边界，以及历史目录迁移清单。

### 按新目录结构迁移项目

- 背景：需要基于新目录结构对项目进行改造，并把无法匹配的文档或文件单列出来逐个分析。
- 建设内容：将前后端迁入 `product/app/`，配置迁入 `product/config/`，核心公共能力迁入 `product/core/`。
- 建设内容：将任务迁入 `product/jobs/`，报告产物迁入 `product/reports/`，业务研究资料迁入 `product/modules/`。
- 建设内容：将项目约定、历史计划和设计文档迁入 `records/`。
- 建设内容：生成 `records/unmatched/unmatched_files.md`，单列临时包、缓存、系统文件等无法直接匹配正式目录的项目。
- 后续事项：继续评估 `records/unmatched/unmatched_files.md` 中的项目，决定清理、归档或纳入正式目录。

### 处理无法直接匹配文件

- 背景：需要逐项分析 `records/unmatched/unmatched_files.md`，决定删除、并入 `knowledge/` 或提炼进 `skills/`。
- 建设内容：删除 `.DS_Store`、妙想临时解压目录、妙想下载包、妙想临时安装文档和 Python 运行缓存。
- 建设内容：将 `.learnings/LEARNINGS.md` 并入 `knowledge/agent_learnings_archive.md`。
- 建设内容：新增 `skills/candidates/eastmoney_miaoxiang.md`，记录东方财富妙想能力作为候选外部 skill 依赖，而不是纳入本项目自有 skill。
- 建设内容：更新 `records/unmatched/unmatched_files.md`，逐项标明处理结果。
- 后续事项：部署文档中需要补充东方财富妙想 skill 依赖、`MX_APIKEY` 配置方式和缺失时的降级策略。

### 补充项目引用 skill 清单

- 背景：需要在 `skills/` 下说明项目引用了哪些 skill，例如 Tushare 和东方财富妙想系列。
- 建设内容：新增 `skills/referenced_skills.md`，记录 Tushare、`mx-data`、`mx-search`、`mx-xuangu`、`mx-zixuan`、`mx-moni`、`mx-poster` 的用途、状态和依赖配置。
- 建设内容：更新 `skills/README.md`，增加引用 skill 清单入口。
- 后续事项：部署文档中需要引用该清单，明确 `TUSHARE_TOKEN` 和 `MX_APIKEY` 的配置要求。

### 补充关键代码中文注释

- 背景：需要给代码补充中文注释，降低后续维护、迁移和模块化沉淀成本。
- 建设内容：为 `product/core/project_config.py`、`product/core/model_service.py` 补充公共配置和模型调用边界说明。
- 建设内容：为后端 ETF 决策服务、猪周期数据服务、牧原日报任务和 HTML 邮件渲染链路补充模块职责、数据流和模型边界注释。
- 建设内容：为前端配置注入、指标卡片、折线图组件、页面数据加载和一键启动脚本补充中文注释。
- 建设内容：修正 ETF 决策服务中 Nasdaq Referer 使用未定义变量的问题，改为读取全局配置。
- 后续事项：后续新增代码继续按“解释意图和边界，不做逐行噪音注释”的原则维护中文注释。

### 沉淀代码注释规范

- 背景：需要先对齐代码注释规范，后续涉及代码变更时统一遵从，避免注释缺失、风格不一致或变成噪音。
- 建设内容：在 `records/project_conventions.md` 中补充完整代码注释规范，明确中文注释、文件级注释、方法级注释、代码块与参数注释、禁止事项和注释更新规则。
- 建设内容：在 `AGENTS.md` 中补充执行侧规则，要求后续代码新增或修改时同步新增或更新注释。
- 建设内容：明确投资分析系统特有边界：确定性代码负责获取、清洗、校验、转换、渲染、调度；分析判断由模型驱动。
- 后续事项：后续每次代码变更都需要检查文件级说明、方法注释和关键逻辑注释是否同步更新。

### 按注释规范补齐现有代码说明

- 背景：注释规范已经沉淀，需要对现有代码补充一轮，避免规范只约束新增代码而历史代码仍难维护。
- 建设内容：为 `product/` 下 Python 生产代码补齐文件级 docstring、类说明、方法说明和复杂逻辑说明。
- 建设内容：为 Python 测试文件补充文件职责、测试类职责和测试方法说明，明确每组测试保护的行为边界。
- 建设内容：为前端 JavaScript、Vue 组件和本地启动脚本补充文件级职责说明，并为关键计算、路由、配置注入和图表交互逻辑补充中文注释。
- 验证结果：Python docstring 静态检查通过，Python 单测、Python 编译检查、前端测试和前端构建均通过。
- 后续事项：后续代码变更继续遵守“先同步注释，再完成验证”的执行节奏。

### 修复一键启动部署脚本

- 背景：本地部署验证时发现 `product/scripts/start.sh` 存在两个稳定性问题：Node 版本只接受 22，且后端 `uvicorn` 可执行脚本因目录迁移保留旧 shebang。
- 建设内容：将前端 `package.json` 的 `engines.node` 从 `>=22 <23` 放宽为 `>=22`，与当前可验证运行环境兼容。
- 建设内容：将启动脚本的 Node 检查改为 `>=22`，不再把 Node 26 误判为不可用。
- 建设内容：将后端启动方式改为 `.venv/bin/python -m uvicorn product.app.backend.app.main:app`，避免依赖 `.venv/bin/uvicorn` 中的绝对路径 shebang。
- 验证结果：通过 `bash product/scripts/start.sh` 成功启动前后端；前端首页返回 HTTP 200；后端 `/api/health` 返回 `{"status":"ok"}`；ETF 决策接口返回有效 JSON。
- 验证结果：前端测试、前端构建、Python 单测均通过。
- 后续事项：部署文档中需要补充 Node `>=22`、后端虚拟环境和启动脚本说明。

### 验证 21:00 日报定时任务发送链路

- 背景：需要执行 21:00 的牧原股份日报任务，生成完整报告并发送到 `376597874@qq.com`，验证真实运行链路。
- 执行内容：运行 `product/jobs/muyuan_nightly.py --date 2026-06-30 --force --send-email --recipient 376597874@qq.com`。
- 发现问题：任务脚本原先在 `runtime.python_path` 为空时默认切换到 `~/.miaoxiang-venv/bin/python`，导致项目后端 venv 已安装的 AkShare/Tushare 在任务运行时不可用。
- 建设内容：将配置层 `runtime.python_path` 空值默认保留为空，由任务层按“显式配置的 Python → 项目后端 venv → 妙想 venv → 当前解释器”的顺序选择解释器。
- 建设内容：将 `tushare==1.4.29` 固化到 `product/app/backend/requirements.txt`，并将启动脚本改为每次启动前同步后端 requirements，避免旧 venv 漏装新增依赖。
- 验证结果：报告已生成到 `product/reports/daily/2026-06-30-muyuan.md`，邮件已发送到 `376597874@qq.com`。
- 验证结果：Python 编译检查、Python 单测、前端测试和前端构建均通过。
- 后续事项：东方财富 `mx-data` 校验本次未获取成功，后续需要单独增强外部 skill 调用和失败观测。

### 切换 DeepSeek 默认运行模型为 Pro

- 背景：需要将运行阶段默认 DeepSeek 模型从 flash 切换为 pro。
- 建设内容：将 `product/config/project.toml` 中的 `model.name` 从 `deepseek-v4-flash` 更新为 `deepseek-v4-pro`。
- 建设内容：同步更新 `product/core/model_service.py` 和 `product/core/project_config.py` 中的默认模型兜底值，避免配置缺失时回退到旧 flash 模型。
- 建设内容：同步更新模型相关测试和 `product/jobs/README.md`，保持配置、代码、测试和文档口径一致。
- 验证结果：Python 编译检查、模型配置相关测试、全量 Python 单测、前端测试和前端构建均通过。

### 建立通用数据能力清单

- 背景：开始标准化数据层，要求分析依赖的数据可置信，并明确数据层不绑定具体标的；牧原股份日报只是当前调用场景。
- 建设内容：新增 `product/data/catalog/data_capabilities.md`，按通用数据能力维护当前日报已使用的数据，包括 A 股行情、估值、交易热度、公告、月度经营数据、生猪价格、期货、基差、VIX、CNN Fear & Greed 和 ETF RSI。
- 建设内容：每个数据能力均补充适用范围、查询参数、固化数据集优先路径、主来源、校验来源、更新频率、时间口径、单位口径、当前状态和当前代码位置。
- 建设内容：将 `product/data/catalog/key_data_sources.md` 调整为入口文件，指向通用数据能力清单，避免历史引用失效。
- 建设内容：同步更新 `product/data/README.md`、`records/project_conventions.md`、`records/project_structure.md` 和 `AGENTS.md`，统一数据获取优先级为“固化数据集 / 本地可信快照 > 已代码固化接口或 fetcher > Tushare > 东方财富 skill > 官方权威来源 > 权威财经网站 > 互联网搜索”。
- 后续事项：下一步应定义可信数据对象 schema，并逐步把日报中的直接取数逻辑迁入数据层 fetcher / validator。

### 统一数据获取到数据层

- 背景：需要将数据获取统一在数据层实现，避免任务层、表达层直接承载外部取数逻辑，便于后续抽取为数据供给 skill。
- 建设内容：新增 `product/data/fetchers/stock.py`，统一承载 A 股行情、估值、交易热度、Tushare 主取数和东方财富校验解析能力；查询参数通过配置传入，不绑定牧原股份。
- 建设内容：新增 `product/data/fetchers/signals.py`，统一承载公告、经营简报、个股异动候选信源的本地缓存读取与摘要能力。
- 建设内容：新增 `product/data/fetchers/hog_cycle.py`，统一承载生猪现货、期货、基差及趋势卡片构造；后端猪周期服务改为兼容导出。
- 建设内容：新增 `product/data/fetchers/market_data.py`，统一承载 VIX、CNN Fear & Greed、QQQ RSI 等海外市场指标取数与确定性计算；后端市场数据服务改为兼容导出。
- 建设内容：新增 `product/tests/test_data_layer.py`，覆盖通用个股快照、趋势指标、东方财富解析、信号摘要、猪周期趋势卡片和市场指标计算，保护数据层边界。
- 建设内容：同步更新 `product/data/catalog/data_capabilities.md` 中当前代码位置和迁移状态。
- 验证结果：数据层测试、后端兼容测试、任务层测试和 Python 编译检查均通过。
