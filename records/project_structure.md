# 项目目录规范

本文件定义本项目的长期目录结构和新增文件归属规则。

## 1. 总体定位

本项目分为四类资产：

1. 项目产物：可独立部署、独立运行的投资复盘系统。
2. 项目构建记录：记录建设路径、待办事项、优先级和完成情况。
3. 项目构建经验沉淀：记录可复用经验、踩坑、模式和重要决策。
4. 项目构建 skill：沉淀未来可迁移复用的原子能力。

根目录只保留项目入口和上述四类资产目录。新增文件必须先确认归属，再创建。

## 2. 一级目录

```text
a_stock/
├── product/              # 项目产物，可独立部署运行
├── records/              # 项目构建记录
├── knowledge/            # 项目构建经验沉淀
├── skills/               # 项目构建 skill
└── README.md             # 项目总入口
```

当前仓库已经按本规范进行初步迁移。若出现无法匹配的文件，先单列到 `records/unmatched/`，再逐个评估目录是否需要调整。

## 3. 项目产物目录

`product/` 是最终系统本体，必须支持独立部署到服务器运行。

```text
product/
├── app/                  # 表达层：前端页面、后端接口、邮件渲染
│   ├── backend/          # 功能 API DDD 领域驱动实现
│   ├── config/           # app 子系统配置
│   ├── frontend/         # 展示层
│   └── scripts/          # app 子系统安装、启动脚本
├── agents/               # 多 Agent 研究体系，基于 LangGraph 实现
│   ├── config/           # agents 子系统配置
│   └── scripts/          # agents 子系统安装、启动脚本
├── data/                 # 数据层：数据获取、加工、校验、标准字段、对外数据 API
│   ├── config/           # data 子系统配置
│   └── scripts/          # data 子系统安装、启动脚本
├── reports/              # 报告产物：日报、周报、月报、专题报告
├── scripts/              # 顶层统一安装、启动脚本
└── docs/                 # 产物文档：部署文档、依赖清单、配置清单、运行说明
```

### 3.1 表达层

`product/app/` 只负责展示和触达，包括前端页面、后端接口和邮件正文渲染。

不要在表达层写死投资判断逻辑。

`product/app/backend/` 是功能 API 的实现中心，采用 DDD 风格组织内部代码。
建议内部保留以下职责分区：

```text
product/app/backend/
├── app/                  # 接口层：FastAPI、路由、启动装配
├── domain/               # 领域层：实体、值对象、领域规则
├── application/          # 应用层：用例编排、服务、任务入口
├── infrastructure/       # 基础设施层：外部依赖、适配器、工具、任务
└── tests/                # 后端测试
```

后端只负责功能落地和服务编排，不承载多 Agent 研究编排逻辑。

`product/app/` 的正式目录树如下：

```text
product/app/
├── backend/
│   ├── app/
│   ├── application/
│   ├── domain/
│   ├── infrastructure/
│   └── tests/
├── config/
│   ├── app.toml
│   ├── private.local.toml
│   └── private.local.toml.example
├── frontend/
└── scripts/
    ├── install.sh
    ├── start.sh
    └── stop.sh
```

### 3.2 配置层

`product/app/config/`、`product/agents/config/`、`product/data/config/` 分别存放三套子系统的运行配置。

不要在业务代码中硬编码可变配置。

当前阶段，`app`、`agents`、`data` 三套子系统各自维护一套独立配置文件和配置加载实现。
公共或跨系统默认值可以保留在各子系统自己的 `config/` 目录中，但子系统自身的运行参数应优先由本子系统目录下的配置读取。

### 3.3 多 Agent 体系

`product/agents/` 是独立的研究体系，不与后端功能实现混写。
该目录用于承载：

- 宏观分析 Agent
- 行业分析 Agent
- 个股分析 Agent
- 估值分析 Agent
- 复盘汇总 Agent
- 研究框架和消息传递协议

多 Agent 体系负责分析、判断和证据整合，最终向后端输出结构化结果。

`product/agents/` 的正式目录树如下：

```text
product/agents/
├── workflows/            # LangGraph 工作流定义
├── agents/               # 各个研究 Agent 定义
│   ├── macro/
│   ├── industry/
│   ├── company/
│   ├── valuation/
│   └── review/
├── prompts/              # Agent prompt 模板与版本化文档
├── schemas/              # Agent 输入输出结构定义
├── memory/               # 研究记忆、上下文、会话记录
├── config/
│   ├── agents.toml
│   ├── private.local.toml
│   └── private.local.toml.example
└── scripts/
    ├── install.sh
    ├── start.sh
    └── run_research.sh
```

### 3.4 数据层

`product/data/` 是股票分析的数据基础。数据层负责数据来源、获取、加工、校验、标准字段和对外数据 API。

`product/data/` 也作为独立子系统维护自己的配置、安装脚本和启动脚本，便于后续单独演进数据加工和数据服务能力。

推荐结构：

```text
product/data/
├── catalog/              # 关键数据获取清单
├── fetchers/             # 已代码固化的数据获取逻辑
├── adapters/             # 数据源适配：代码接口、Tushare、东方财富、权威网页、搜索
├── database/             # 数据库表结构、读写、迁移
├── raw/                  # 原始数据
├── validated/            # 校验后的可信数据
├── derived/              # 衍生指标
└── snapshots/            # 每日、每周快照
```

数据获取优先级：

1. 固化数据集 / 本地可信快照
2. 已代码固化的数据接口或 fetcher
3. Tushare
4. 东方财富 skill
5. 官方、交易所、监管、公司公告等权威公开来源
6. 权威财经网站，例如同花顺、新浪财经、Yahoo Finance 等
7. 互联网搜索，多信源验证

关键数据必须进入 `product/data/catalog/` 的数据获取清单，并尽量通过代码固化执行路径。

`product/data/` 的正式目录树如下：

```text
product/data/
├── catalog/              # 数据获取清单、字段字典、来源优先级
├── fetchers/             # 已代码固化的数据获取逻辑
├── adapters/             # 外部数据源适配
├── processors/           # 数据清洗、归一化、指标加工
├── services/             # 数据服务编排、数据库读写、任务入口
├── validators/           # 数据校验、双源验证、口径检查
├── snapshots/            # 日快照、周快照、月快照
├── api/                  # 对外数据 API 或导出接口
├── config/
│   ├── data.toml
│   ├── private.local.toml
│   └── private.local.toml.example
└── scripts/
    ├── install.sh
    ├── start.sh
    └── refresh.sh
```

### 3.5 报告产物

`product/reports/` 存放最终产出的日报、周报、月报和专题报告。

报告是结果，不是业务规则源头。

### 3.6 脚本层

`product/scripts/` 只保留顶层统一安装和启动脚本。

项目必须维护安装脚本，支持快速独立部署。

### 3.7 产物文档

`product/docs/` 存放可部署系统的文档，至少包括：

- 部署文档
- 依赖清单
- 配置清单
- 启动说明
- 定时任务说明

### 3.8 目录合并原则

当前阶段，`product/core/`、`product/jobs/`、`product/modules/`、`product/tools/` 不再作为顶层长期目录单独维护。
相关能力应分别并入：

- `product/app/backend/` 的领域、应用、基础设施分层
- `product/agents/` 的研究编排体系
- `product/data/` 的数据加工体系

如果后续确有独立复用价值，再评估是否重新拆分为长期目录。

### 3.9 统一脚本入口

`product/scripts/` 只保留最外层统一入口脚本，原则上只做编排，不承载业务逻辑。

建议最外层至少保留：

```text
product/scripts/
├── install.sh            # 顺序调用 app / agents / data 的安装脚本
└── start.sh              # 顺序或并行调用 app / agents / data 的启动脚本
```

各子系统的安装和启动逻辑应分别放在自身目录下，由最外层脚本直接调用。

## 4. 项目构建记录

`records/` 记录项目怎么建设出来。

```text
records/
├── todo.md               # 全局待办清单
├── build_log.md          # 建设日志
└── roadmap.md            # 阶段路线图
```

新增 todo 时必须记录：

- 提出时间
- 提出背景
- 目标
- 优先级
- 当前状态
- 归属模块

todo 完成后，必须在 `records/build_log.md` 记录建设结果，再更新 todo 状态。

## 5. 项目构建经验沉淀

`knowledge/` 记录建设过程中验证有效的经验。

```text
knowledge/
├── lessons.md            # 有效经验
├── mistakes.md           # 踩坑记录
├── patterns.md           # 可复用模式
└── decisions/            # 重要设计决策
```

这里沉淀的是方法和经验，不是临时任务。

## 6. 项目构建 skill

`skills/` 用于管理未来可迁移复用的原子能力。

```text
skills/
├── README.md             # skill 抽取原则
├── candidates/           # 候选 skill
└── released/             # 已稳定抽取的 skill
```

当前阶段先记录候选能力，不急于抽取。只有当能力稳定、边界清晰、跨项目复用价值高时，才进入正式 skill 化。

## 7. 新增文件检查清单

每次新增文件前，必须先完成以下检查：

1. 这个文件属于项目产物、构建记录、经验沉淀还是 skill？
2. 如果属于项目产物，它对应哪一层：表达层、配置层、数据层、报告产物、脚本层还是产物文档？
3. 是否已有同类目录或文件可以复用？
4. 是否会造成根目录新增一级目录？如会，默认不允许，除非先更新本规范。
5. 是否涉及数据获取？如涉及，必须同步检查数据获取优先级和关键数据清单。
6. 是否涉及分析、判断、决策？如涉及，业务逻辑应保持模型驱动，代码只做确定性流转。
7. 文件完成后，是否需要更新 `records/todo.md` 或 `records/build_log.md`？

## 8. 禁止事项

- 不随意新增一级目录。
- 不把临时脚本散落在根目录。
- 不把研究结论放进数据目录。
- 不把数据抓取逻辑放进表达层。
- 不把模型供应商逻辑写死在业务模块中。
- 不把 todo 和经验沉淀混在项目产物里。
