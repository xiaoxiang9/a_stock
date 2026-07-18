# 建设日志

## 2026-07-05

### 将 AkShare 接入 agents 子系统

- 背景：需要在 `product/agents` 里增加一个通用的 AkShare 数据源，直接服务估值 Agent，而不依赖 `product/data` 的实现。
- 建设内容：在 `product/agents/agents/valuation/providers.py` 中新增 `AkShareEvidenceProvider`，直接通过 `akshare` 拉取个股历史行情、个股概览以及生猪现货/期货/基差证据。
- 建设内容：将 `product/agents/agents/valuation/data_agent.py` 的默认来源顺序新增 `akshare`，并支持 `ak`、`ak-share`、`akshare` 别名。
- 建设内容：将 `product/agents/agents/valuation/prompt.py`、`product/agents/agents/valuation/__init__.py`、`product/agents/scripts/start.sh`、`product/agents/scripts/install.sh` 和 `product/agents/README.md` 同步更新，保证配置、导出、脚本和文档一致。
- 建设内容：在 `product/app/backend/tests/test_muyuan_nightly.py` 中补充 AkShare provider 注册测试，验证其作为独立数据源可被调度。
- 验证结果：后端虚拟环境内 `akshare` 可导入，且其生猪现货和期货函数可用；由于当前网络代理不稳定，真实在线请求未作为本次成功标准。
- 后续事项：后续如需要 AkShare 进一步提供更完整的估值字段，可继续在 `agents` 内扩展对应提取逻辑，但仍不依赖 `product/data`。

### 将 websearch-deepseek 接入 agents 子系统

- 背景：需要把 `websearch-deepseek` 作为 `product/agents` 里的联网搜索数据来源，而不是继续只挂在全局 Codex 配置里。
- 建设内容：在 `product/agents/config/agents.toml` 增加 `[search]` 配置段，显式声明 `websearch-deepseek` 的启用状态、命令、模型参数和超时。
- 建设内容：扩展 `product/agents/config/agents_config.py`，新增 `SearchConfig` 并让 `AgentsConfig` 统一承载联网搜索配置。
- 建设内容：在 `product/agents/agents/valuation/providers.py` 中新增 `WebSearchDeepseekEvidenceProvider`，通过本机 `websearch-deepseek` MCP server 发起联网搜索，并将结果转换为估值证据。
- 建设内容：将 `product/agents/agents/valuation/data_agent.py` 的默认取数顺序、`product/agents/agents/valuation/prompt.py` 的 `preferred_sources` 和 `product/agents/agents/valuation/__init__.py` 的导出同步更新。
- 建设内容：同步更新 `product/agents/scripts/install.sh`、`product/agents/scripts/start.sh` 和 `product/agents/README.md`，让子项目安装和启动时都能检查该数据源是否可用。
- 验证结果：`PYTHONDONTWRITEBYTECODE=1 product/app/backend/.venv/bin/python -m unittest product.app.backend.tests.test_subsystem_config_loaders product.app.backend.tests.test_muyuan_nightly -v` 通过。
- 验证结果：`bash product/agents/scripts/install.sh` 与 `bash product/agents/scripts/start.sh` 均能识别 `websearch-deepseek` 已启用。
- 验证结果：真实联网探测可返回 `websearch-deepseek` 证据项和来源链接，说明 Agent 侧搜索链路可用。
- 后续事项：如果后续要把 MCP server 切换成其他实现，只需要调整 `product/agents/config/agents.toml` 里的搜索配置和 provider 适配层。

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

## 2026-07-04

### 梳理本机 skill 与跨机器全量克隆方式

- 背景：需要梳理当前机器已安装的全部 Codex / Agent skill，并形成其他机器可一键克隆使用的文档。
- 建设内容：新增 `skills/local_skill_installation.md`，记录 `~/.codex/skills` 和 `~/.agents/skills` 两套根目录下全部已安装 skill；当前源机器分别为 26 个和 47 个。
- 建设内容：文档中补充源机器全量打包命令、目标机器镜像恢复脚本、目标机器密钥和登录态配置说明、验证命令和更新克隆包流程。
- 建设内容：更新 `skills/README.md`，增加本机 skill 安装文档入口。
- 后续事项：后续新增或更新本机 skill 时，需要同步维护该安装文档；若某项能力稳定为项目自有能力，再迁入 `skills/candidates/` 或 `skills/released/`。

### 后端内置每日 21 点复盘调度

- 背景：需要把“每天 21:00 发送复盘报告”的能力写进项目后端本身，使部署到任意服务器后只要启动后端服务就能自动执行。
- 建设内容：新增 `product/app/backend/app/services/report_scheduler.py`，实现每日执行时间计算、跨进程文件锁和后台调度循环。
- 建设内容：在 `product/app/backend/app/main.py` 的 FastAPI 生命周期里挂载调度器，服务启动时自动启动后台任务，关闭时自动释放锁和任务。
- 建设内容：调度器复用 `product/jobs/muyuan_nightly.py` 的日报生成、HTML 渲染和邮件发送逻辑，不再依赖宿主机 `launchd` / `cron` / `systemd timer`。
- 建设内容：新增 `product/app/backend/tests/test_report_scheduler.py`，覆盖时间计算、锁竞争和生命周期挂载，确保自动发送链路可回归验证。
- 建设内容：同步更新 `README.md`、`product/jobs/README.md`、`product/config/project.toml` 和 `product/core/project_config.py` 的说明口径，强调后端进程自带调度。
- 验证结果：`product/app/backend/.venv/bin/python -m unittest product.app.backend.tests.test_app_config product.app.backend.tests.test_report_scheduler product.tests.test_muyuan_nightly product.tests.test_project_config -v` 通过。
- 后续事项：如后续需要多实例部署，需要进一步评估锁文件放置位置与幂等发送策略。

### 修复邮件凭据加载链路

- 背景：夜间调度任务已经触发，但发信阶段报 `SMTP_PASS not set`，说明邮件凭据没有进入进程环境。
- 建设内容：扩展 `product/jobs/muyuan_nightly.py` 的运行时环境加载逻辑，自动读取 `~/.config/a_stock/mail.env`、`~/.bash_profile`、`~/.zshrc` 和 `~/.profile` 中的简单环境变量定义。
- 建设内容：在 `send_email()` 和夜间任务入口前主动加载这些本地环境变量，避免不同启动方式导致 SMTP 凭据丢失。
- 建设内容：新增 `product/config/mail.env.example`，为 SMTP_HOST、SMTP_PORT、SMTP_USER、SMTP_PASS、SMTP_FROM 提供本地配置模板。
- 建设内容：更新 `README.md` 和 `product/jobs/README.md`，明确邮件环境变量的加载位置和部署方式。
- 验证结果：相关 Python 单测通过，且 `load_env_from_bash_profile()` 能从本地邮件环境文件补充 `SMTP_PASS`。
- 后续事项：如果运行环境仍未配置 SMTP_PASS，邮件仍无法发送，需要在本地环境文件或 shell 配置中补上真实凭据。

### 私密配置统一收口

- 背景：项目后续还会持续增加 SMTP 密码、模型和数据源等私密项，单独靠 shell 环境变量会让独立部署和排障都变复杂。
- 建设内容：公开 SMTP 参数迁入 `product/config/project.toml`，私密文件 `product/config/private.local.toml` 只保留 SMTP 密码、DeepSeek API key 和 Tushare token。
- 建设内容：新增 `product/core/private_config.py`，由邮件发送、模型调用和 Tushare 取数直接读取这份私密配置，不再依赖 shell 环境变量。
- 建设内容：更新 `product/jobs/muyuan_nightly.py`、`product/core/model_service.py`、`product/data/fetchers/stock.py`、`README.md` 和 `product/jobs/README.md`，把说明口径切到公开/私密双配置中心。
- 建设内容：补充 `product/config/private.local.toml.example` 作为本地配置模板，并将真实配置文件加入 `.gitignore`。
- 验证结果：`python3 -m unittest product.tests.test_model_service product.tests.test_muyuan_nightly product.tests.test_project_config` 通过；随后直接执行 `python3 product/jobs/muyuan_nightly.py --date 2026-07-05 --send-email --force` 成功生成日报并发送邮件。
- 后续事项：后续如新增更多敏感配置，继续往 `product/config/private.local.toml` 收口，公开参数优先保留在 `product/config/project.toml`。

### 安装与启动脚本收口

- 背景：独立部署需要把“检测、初始化、安装、启动、阻断”拆成明确流程，不能继续依赖手工环境或沙箱状态。
- 建设内容：新增 `product/tools/deployment_checks.py` 作为统一检查入口，负责公开配置、私密配置、后端依赖和前端依赖校验。
- 建设内容：新增 `product/scripts/install.sh`，在用户确认后安装缺失依赖，并初始化 `product/config/private.local.toml` 模板，但不自动填写敏感值。
- 建设内容：重写 `product/scripts/start.sh`，启动前先做配置和依赖检查，任一项失败都直接退出并返回原因。
- 建设内容：新增 `product/docs/deployment.md`，补齐依赖清单、配置清单、安装步骤、启动步骤和常见失败原因。
- 建设内容：更新 `README.md`、`product/scripts/README.md`、`product/docs/README.md`、`product/config/README.md` 和 `product/jobs/README.md`，统一安装/启动口径。
- 验证结果：`bash -n product/scripts/install.sh`、`bash -n product/scripts/start.sh`、`python3 -m unittest product.tests.test_deployment_checks product.tests.test_muyuan_nightly product.tests.test_project_config product.tests.test_model_service` 通过；`python3 product/tools/deployment_checks.py private-config --config product/config/private.local.toml` 和 `python3 product/tools/deployment_checks.py startup` 均返回 `OK`。
- 后续事项：后续如新增依赖，优先同步更新 `product/tools/deployment_checks.py` 和 `product/docs/deployment.md`，保证安装与启动口径一致。

### 固化 app / agents / data 三套子系统目录树

- 背景：多 Agent 研究体系、产品功能系统和数据系统需要保持相对独立，配置、脚本和启动入口也要各自收口，避免后续重新耦合成一个大后端。
- 建设内容：更新 `records/project_structure.md`，正式写入 `product/app/`、`product/agents/`、`product/data/` 的三套目录树，并明确 `product/scripts/` 只保留顶层统一安装与启动入口。
- 建设内容：实际创建 `product/app/config/`、`product/app/scripts/`、`product/agents/`、`product/agents/config/`、`product/agents/scripts/`、`product/data/config/`、`product/data/scripts/` 及其推荐子目录，作为后续文件迁移的落点。
- 建设内容：为 `product/app/backend/` 保留 DDD 分层目录，为 `product/agents/` 保留 LangGraph 工作流、Agent、prompt、schema 和 memory 目录，为 `product/data/` 保留 catalog、fetchers、adapters、processors、validators、snapshots 和 api 目录。
- 后续事项：继续把现有代码和文档迁移到对应子系统目录，并逐步补齐各子系统自己的配置加载与脚本入口。

### 完成子系统迁移、配置收口与启动验证

- 背景：用户要求先完成整体迁移，再补齐配置，最后做启动验证，因此需要把 `app / agents / data` 三套目录真正落地，并让顶层脚本能够稳定启动。
- 建设内容：将后端能力从旧的 `core`、`jobs`、`modules`、`tools` 收拢到新的 `product/app/backend/application`、`product/app/backend/domain`、`product/app/backend/infrastructure` 三层目录中，保留表达层、配置层、核心层和测试层的边界。
- 建设内容：将 `product/scripts/` 收敛为顶层安装与启动入口，分别下发到 `product/app/scripts/`、`product/agents/scripts/` 和 `product/data/scripts/`，并为三套子系统补齐各自的配置目录和模板。
- 建设内容：修复直接执行脚本的导入方式，保证 `deployment_checks.py`、`generate_muyuan_review_stub.py` 和 `muyuan_nightly.py` 都能在仓库根路径下独立运行。
- 验证结果：`python3 product/app/backend/infrastructure/deployment_checks.py install` 通过；`bash -n product/scripts/start.sh` 和 `bash -n product/app/scripts/start.sh` 通过；`bash product/scripts/start.sh` 成功拉起后端和前端，`curl -sS http://127.0.0.1:8000/api/health` 返回 `{"status":"ok"}`，端口 `8000` 处于监听状态。
- 后续事项：后续继续补齐 `product/agents/` 的真实多 Agent 工作流和 `product/data/` 的数据 API，再逐步把业务调用从后端迁移到统一的数据层与 Agent 层。

### 解耦三套子系统的配置与加载器

- 背景：`app`、`data`、`agents` 三套子系统需要真正独立，不能再出现 `data` 读取 `app` 配置、或者三套目录共用同一个配置加载器的情况。
- 建设内容：新增 `product/data/config/data_config.py` 与 `product/data/config/private_config.py`，让 `data` 子系统只读取自己的配置目录；新增 `product/agents/config/agents_config.py` 与 `product/agents/config/private_config.py`，让 `agents` 子系统只读取自己的配置目录。
- 建设内容：将 `product/data/fetchers/market_data.py` 改为只依赖 `data` 子系统自己的配置加载器；将 `product/data/fetchers/stock.py` 改为显式接收 Tushare token、标的和时间范围，不再自己读 `app` 配置。
- 建设内容：将 `product/app/backend/application/reports/muyuan_nightly.py` 改为由 `app` 自己读取 Tushare token，再显式传给 `data` 层取数函数，避免应用层和数据层共享配置读取逻辑。
- 建设内容：补充 `product/app/backend/tests/test_subsystem_config_loaders.py`，验证 `app`、`data`、`agents` 三套配置加载器都只读自己的目录。
- 验证结果：`product/app/backend/.venv/bin/python -m unittest product.app.backend.tests.test_project_config product.app.backend.tests.test_model_service product.app.backend.tests.test_deployment_checks product.app.backend.tests.test_report_scheduler product.app.backend.tests.test_muyuan_nightly product.app.backend.tests.test_data_layer product.app.backend.tests.test_subsystem_config_loaders -v` 通过；`bash product/scripts/start.sh` 成功拉起 `agents`、`data`、`app` 三段启动链路，`curl -sS http://127.0.0.1:8000/api/health` 返回 `{"status":"ok"}`。
- 后续事项：如果后续 `agents` 或 `data` 需要真实运行守护进程，再在各自目录内继续扩展自己的配置和启动脚本，不要把配置回流到 `app`。
