# Investment Framework MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the first usable repository structure, templates, and Muyuan sample documents for a research-first value-investing workflow.

**Architecture:** Add a research-first directory structure alongside the existing app code, then create markdown-first templates for the good-company framework, Muyuan sample, signal definitions, and 21:00 nightly review. Keep the implementation narrow and file-based so the workflow can be proven manually before automation work begins.

**Tech Stack:** Markdown, repository file structure, existing git workspace

## Global Constraints

- `tushare` is the primary data source.
- Eastmoney skills are the secondary validation source.
- If both fail, use official websites, exchange announcements, regulator disclosures, and other authoritative public webpages first.
- Avoid unknown channels when stronger sources exist.
- The fixed five-state action layer is `观察` / `持有` / `加仓观察` / `减仓观察` / `卖出复核`.
- Good-company scoring must exclude valuation, short-term risk/reward, and short-term heat.
- The first implementation target is a single-stock MVP using `牧原股份 (002714.SZ)`.

---

### Task 1: Create Research-First Directory Structure

**Files:**
- Create: `framework/good_companies/`
- Create: `signals/definitions/`
- Create: `signals/snapshots/`
- Create: `signals/evaluations/`
- Create: `universe/muyuan/profile/`
- Create: `universe/muyuan/thesis/`
- Create: `universe/muyuan/tracking/`
- Create: `universe/muyuan/valuation/`
- Create: `universe/muyuan/decision/`
- Create: `universe/muyuan/review/daily/`
- Create: `universe/muyuan/review/weekly/`
- Create: `data/raw/muyuan/`
- Create: `data/validated/muyuan/`
- Create: `data/derived/muyuan/`
- Create: `review/daily/`
- Create: `review/weekly/`
- Create: `review/monthly/`
- Create: `jobs/`
- Create: `app/backend/`
- Create: `app/frontend/`

**Interfaces:**
- Consumes: existing repository root
- Produces: stable directory targets for all later markdown templates

- [ ] **Step 1: Create the directory tree**

Run:

```bash
mkdir -p framework/good_companies signals/definitions signals/snapshots signals/evaluations universe/muyuan/profile universe/muyuan/thesis universe/muyuan/tracking universe/muyuan/valuation universe/muyuan/decision universe/muyuan/review/daily universe/muyuan/review/weekly data/raw/muyuan data/validated/muyuan data/derived/muyuan review/daily review/weekly review/monthly jobs app/backend app/frontend
```

- [ ] **Step 2: Verify the directories exist**

Run:

```bash
find framework signals universe data review jobs app -maxdepth 3 -type d | sort
```

Expected: directories listed for the paths above

### Task 2: Add Good Company Framework Documents

**Files:**
- Create: `framework/good_companies/good_company_criteria.md`
- Create: `framework/good_companies/good_companies_list.md`

**Interfaces:**
- Consumes: `framework/good_companies/`
- Produces: scoring standard and master company table used by single-stock files and future app views

- [ ] **Step 1: Create the criteria document**

Document content must include:

```md
# Good Company Criteria

## Purpose

This document defines how the repository judges whether a company belongs in the long-term good-company list.

This framework evaluates only company quality and long-term investability.
It does not include valuation, short-term risk/reward, or market heat.

## Five-Dimension Radar

1. 商业模式 - 25%
2. 行业与竞争格局 - 20%
3. 财务质量 - 25%
4. 管理层与治理 - 15%
5. 周期与确定性 - 15%

Each dimension is scored on a 10-point scale and converted into a weighted 100-point score.

## Dimension Standards

### 1. 商业模式
- 业务是否容易理解
- 盈利模式是否清晰
- 需求是否长期存在
- 是否具备可持续护城河

### 2. 行业与竞争格局
- 行业空间是否足够大
- 格局是否稳定
- 公司是否具备龙头或强竞争地位
- 是否处于长期过度内卷行业

### 3. 财务质量
- 收入与利润质量
- 毛利率、净利率、ROE
- 经营现金流
- 负债与资本结构
- 周期波动中的抗压能力

### 4. 管理层与治理
- 管理层是否可信
- 资本配置是否合理
- 信息披露是否透明
- 是否尊重股东利益

### 5. 周期与确定性
- 盈利是否强周期
- 周期是否可跟踪
- 未来 2-3 年确定性如何
- 外部变量是否过多

## Score Bands

- 85-100: 高质量好公司
- 70-84: 可纳入好公司池
- 60-69: 有一定吸引力，但仍需重点观察
- 60 以下: 暂不纳入好公司核心列表
```

- [ ] **Step 2: Create the master company list**

Document content must include:

```md
# Good Companies List

| 公司名称 | 股票代码 | 行业 | 是否纳入好公司列表 | 当前状态 | 综合评分 | 商业模式 | 行业格局 | 财务质量 | 管理层治理 | 周期确定性 | 核心投资逻辑 | 当前主要风险 | 当前交易依据 | 最近复核日期 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 牧原股份 | 002714.SZ | 生猪养殖 | 待评估 | 观察 | 待评估 | 待评估 | 待评估 | 待评估 | 待评估 | 待评估 | 待补充 | 待补充 | 待补充 | 待补充 |
```

- [ ] **Step 3: Verify both files exist and are readable**

Run:

```bash
sed -n '1,200p' framework/good_companies/good_company_criteria.md
sed -n '1,80p' framework/good_companies/good_companies_list.md
```

Expected: both documents print with the required sections and table

### Task 3: Add Muyuan Detail Documents

**Files:**
- Create: `universe/muyuan/profile/company.md`
- Create: `universe/muyuan/thesis/investment_thesis.md`
- Create: `universe/muyuan/tracking/daily_checklist.md`
- Create: `universe/muyuan/tracking/key_indicators.md`
- Create: `universe/muyuan/valuation/valuation_framework.md`
- Create: `universe/muyuan/decision/decision_rules.md`
- Create: `universe/muyuan/decision/current_view.md`

**Interfaces:**
- Consumes: `universe/muyuan/` directories and good-company framework
- Produces: first single-stock working documents for future updates and reviews

- [ ] **Step 1: Create the Muyuan company profile file**

Document content must include:

```md
# 牧原股份（002714.SZ）公司档案

## 基础信息
- 公司名称：牧原股份
- 股票代码：002714.SZ
- 所属行业：生猪养殖
- 所属主题/产业链：生猪养殖、饲料成本、猪周期
- 当前状态：观察
- 是否纳入好公司列表：待评估
- 最近复核日期：待补充

## 业务概览
- 主营业务：待补充
- 盈利模式：待补充
- 行业位置：待补充
```

- [ ] **Step 2: Create the Muyuan investment thesis file**

Document content must include:

```md
# 牧原股份投资逻辑

## 一句话结论
- 待补充

## 核心投资逻辑
- 逻辑 1：待补充
- 逻辑 2：待补充
- 逻辑 3：待补充

## 主要风险
- 风险 1：待补充
- 风险 2：待补充
- 风险 3：待补充
```

- [ ] **Step 3: Create the daily checklist and key indicator files**

`universe/muyuan/tracking/daily_checklist.md`:

```md
# 牧原股份日检查清单

- 收盘价与涨跌幅
- PE_TTM / PB / 换手率 / 市值
- 生猪价格变化
- 行业产能去化或补产能信息
- 公司公告与月度经营更新
- 市场热度与资金面变化
- 当前五档状态是否需要调整
```

`universe/muyuan/tracking/key_indicators.md`:

```md
# 牧原股份关键跟踪指标

## 价格与估值
- 收盘价
- PE_TTM
- PB
- 换手率
- 总市值

## 行业与周期
- 生猪价格
- 能繁母猪存栏趋势
- 行业去产能/补产能信号

## 公司经营
- 月度出栏数据
- 成本变化
- 重要公告

## 热度与交易层
- 成交额变化
- 换手率变化
- 资金流向
```

- [ ] **Step 4: Create the valuation, decision rules, and current view files**

`universe/muyuan/valuation/valuation_framework.md`:

```md
# 牧原股份估值框架

## 估值用途
估值不参与好公司判断，只用于交易依据判断。

## 当前重点口径
- PE_TTM
- PB
- 总市值
- 流通市值

## 估值判断目标
- 判断当前价格是否具备安全边际
- 判断是否进入加仓观察或减仓观察区
```

`universe/muyuan/decision/decision_rules.md`:

```md
# 牧原股份五档决策规则

- 观察：未建仓，判断是否达到好公司标准
- 持有：已判断为好公司，当前无需操作
- 加仓观察：好公司，且价格/赔率/周期/经营条件更有利
- 减仓观察：公司仍然优秀，但短期热度偏高，考虑部分收益落袋为安
- 卖出复核：核心逻辑可能发生变化，需要重新评估是否继续持有
```

`universe/muyuan/decision/current_view.md`:

```md
# 牧原股份当前观点

## 当前状态
- 状态：观察

## 当前结论
- 是否已确认为好公司：待评估
- 当前交易依据：待补充
- 下一步关注点：待补充
```

- [ ] **Step 5: Verify all Muyuan files exist**

Run:

```bash
find universe/muyuan -maxdepth 3 -type f | sort
```

Expected: the seven markdown files listed above

### Task 4: Add Signal and Review Templates

**Files:**
- Create: `signals/definitions/muyuan_signals.md`
- Create: `review/daily/README.md`
- Create: `review/weekly/README.md`
- Create: `review/monthly/README.md`

**Interfaces:**
- Consumes: signals and review directories
- Produces: shared indicator definitions and the 21:00 review template

- [ ] **Step 1: Create the signal definition file**

Document content must include:

```md
# 牧原股份信号定义

## 用途
本文件定义牧原股份第一版研究驱动决策系统所使用的关键跟踪信号。

## 信号分组

### 1. 价格与估值
- 收盘价
- PE_TTM
- PB
- 换手率
- 总市值

### 2. 行业与周期
- 生猪价格
- 能繁母猪存栏趋势
- 行业去产能/补产能信号

### 3. 公司经营
- 月度出栏数据
- 成本变化
- 重要公告

### 4. 热度与交易层
- 成交额变化
- 资金流向
- 市场讨论热度

## 评估原则
- 先看周期位置
- 再看公司经营兑现度
- 再看估值和赔率
- 最后用热度修正仓位动作节奏
```

- [ ] **Step 2: Create the daily review template**

`review/daily/README.md`:

```md
# 每晚 21:00 日复盘模板

## 1. 今日核心结论

## 2. 关键数据更新
- 收盘价
- PE_TTM
- PB
- 换手率
- 总市值
- 数据来源与校验来源

## 3. 关键跟踪指标变化
- 猪价
- 行业产能
- 公司经营更新
- 公告与新闻
- 市场热度

## 4. 当前五档状态
- 观察 / 持有 / 加仓观察 / 减仓观察 / 卖出复核

## 5. 明日建议

## 6. 指标有效性检查
- 哪些指标有解释力
- 哪些指标噪音较大
- 是否需要补充或剔除指标
```

- [ ] **Step 3: Create the weekly and monthly review placeholders**

`review/weekly/README.md`:

```md
# 周复盘

- 回顾一周内五档状态变化
- 回顾关键指标是否有效
- 回顾是否存在错误判断
- 更新下周重点观察项
```

`review/monthly/README.md`:

```md
# 月复盘

- 回顾月内状态变化与决策得失
- 回顾好公司评分是否需要调整
- 回顾交易依据是否仍然有效
- 判断是否需要新增或删除关键指标
```

- [ ] **Step 4: Verify the signal and review files**

Run:

```bash
find signals/definitions review -maxdepth 2 -type f | sort
```

Expected: signal definition file and three review README files

## Self-Review

- Spec coverage: directories, good-company framework, Muyuan sample files, signal definition, and 21:00 review template are all covered by the four tasks above.
- Placeholder scan: intentional `待补充` markers remain only inside repository templates where future research content will be filled manually; the plan itself contains no execution placeholders.
- Type consistency: not applicable beyond file paths and fixed state labels, which are consistent across all tasks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-27-investment-framework-mvp.md`. The user already requested execution to begin, so proceed inline with the tasks above.
