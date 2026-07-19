# 通用数据能力清单

本文件维护项目当前可使用或计划固化的数据能力。

数据层不绑定具体标的。股票代码、公司名称、行业、时间范围、统计频率等都应作为查询参数传入。牧原股份日报只是当前这些数据能力的一组调用场景，后续分析麦格米特或其他公司时，应复用同一套数据能力。

## 1. 数据获取优先级

默认优先级如下：

1. 固化数据集 / 本地可信快照
2. 已代码固化的数据接口或 fetcher
3. Tushare
4. 东方财富 skill
5. 官方网站、交易所公告、监管公告、公司公告等权威公开来源
6. 权威财经网站，例如同花顺、新浪财经、Yahoo Finance 等
7. 互联网搜索，多信源验证

说明：

- 固化数据集 / 本地可信快照优先级最高，因为它是已经被项目校验、可复现、可追溯的数据资产。
- 当固化数据集缺失或过期时，再按优先级向外部数据源获取。
- 任何用于分析的数据都必须带来源、口径、时间和可信等级。
- 如果核心数据不可信，应停在数据校验层，不继续生成强结论。

## 2. 统一返回口径

每个数据能力后续都应返回统一可信数据对象，而不是只返回裸值。

```json
{
  "capability": "stock_valuation_metrics",
  "name": "PE(TTM)",
  "value": 20.65,
  "unit": "倍",
  "as_of": "2026-06-30",
  "period": "交易日",
  "query": {
    "ts_code": "002714.SZ",
    "trade_date": "20260630"
  },
  "primary_source": {
    "name": "Tushare",
    "method": "daily_basic",
    "url": ""
  },
  "check_sources": [
    {
      "name": "东方财富",
      "method": "mx-finance-data",
      "url": "",
      "status": "unavailable"
    }
  ],
  "trust_level": "single_source",
  "status": "available",
  "notes": "东方财富校验暂未获取成功"
}
```

## 3. 可信等级

| 可信等级 | 含义 | 是否允许进入分析 |
| --- | --- | --- |
| `trusted` | 主来源成功，校验来源一致，或该数据已在本地可信快照中固化 | 允许 |
| `verified_with_diff` | 主来源成功，校验来源存在差异，但差异可解释且已标注口径 | 允许，但必须说明差异 |
| `single_source` | 只有单一来源，来源可信但暂未完成校验 | 允许展示，模型分析必须标注单来源风险 |
| `untrusted` | 数据缺失、来源不明、口径冲突过大或校验失败 | 不允许用于强分析结论 |

## 4. 当前数据能力

### 4.1 A 股个股行情

| 字段 | 说明 |
| --- | --- |
| 数据能力 ID | `stock_daily_quote` |
| 适用范围 | A 股个股 |
| 查询参数 | `ts_code`、`trade_date`、`start_date`、`end_date` |
| 当前用途 | 日报收盘价、涨跌幅、近 20 交易日趋势 |
| 固化数据集优先 | `product/data/validated/stock_daily_quote/`，待建立 |
| 主来源 | Tushare `daily` |
| 校验来源 | 东方财富行情数据、交易所行情页，待固化 |
| 更新频率 | 交易日收盘后 |
| 时间口径 | 交易日 |
| 单位口径 | 价格为元，涨跌幅为百分比 |
| 当前状态 | 已迁入数据层 fetcher，日报任务按参数调用 |
| 当前代码位置 | `product/data/fetchers/stock.py` |

### 4.2 A 股个股估值指标

| 字段 | 说明 |
| --- | --- |
| 数据能力 ID | `stock_valuation_metrics` |
| 适用范围 | A 股个股 |
| 查询参数 | `ts_code`、`trade_date`、`start_date`、`end_date`、`fields` |
| 当前用途 | PE(TTM)、PB、总市值、流通市值等估值快照 |
| 固化数据集优先 | `product/data/validated/stock_valuation_metrics/`，待建立 |
| 主来源 | Tushare `daily_basic` |
| 校验来源 | 东方财富 `mx-finance-data` |
| 更新频率 | 交易日收盘后 |
| 时间口径 | 交易日 |
| 单位口径 | PE/PB 为倍，总市值统一为亿元 |
| 当前状态 | 已迁入数据层 fetcher，东方财富校验偶发不可用 |
| 当前代码位置 | `product/data/fetchers/stock.py` |

### 4.3 A 股个股月度估值历史与百分位

| 字段 | 说明 |
| --- | --- |
| 数据能力 ID | `stock_monthly_valuation_percentile` |
| 适用范围 | A 股个股 |
| 查询参数 | `ts_code`、`as_of_date`、`refresh_if_missing` |
| 当前用途 | 月度 PE(PB) 历史序列、最新月度值、历史百分位 |
| 固化数据集优先 | `product/data/snapshots/stock_valuation_monthly/`，待建立 |
| 主来源 | Tushare `daily_basic`，按月压缩 |
| 校验来源 | Tushare 月内最新交易日复算、后续可扩展东方财富校验 |
| 更新频率 | 每月 3 日刷新当月值 |
| 时间口径 | 月度，按每月最后一个交易日落点 |
| 单位口径 | PE/PB 为倍；百分位为 0-1 区间经验分位 |
| 当前状态 | 已实现月度序列加工、独立 API、初始化和刷新入口 |
| 当前代码位置 | `product/data/processors/stock_valuation_monthly.py`、`product/data/services/stock_valuation_monthly.py`、`product/data/api/main.py` |

### 4.4 A 股个股交易热度

| 字段 | 说明 |
| --- | --- |
| 数据能力 ID | `stock_trading_heat` |
| 适用范围 | A 股个股 |
| 查询参数 | `ts_code`、`trade_date`、`start_date`、`end_date`、`fields` |
| 当前用途 | 换手率、量比、成交活跃度趋势 |
| 固化数据集优先 | `product/data/validated/stock_trading_heat/`，待建立 |
| 主来源 | Tushare `daily_basic` |
| 校验来源 | 东方财富 `mx-finance-data` |
| 更新频率 | 交易日收盘后 |
| 时间口径 | 交易日 |
| 单位口径 | 换手率为百分比 |
| 当前状态 | 已迁入数据层 fetcher，日报任务按参数调用 |
| 当前代码位置 | `product/data/fetchers/stock.py` |

### 4.5 个股公告检索

| 字段 | 说明 |
| --- | --- |
| 数据能力 ID | `stock_announcements` |
| 适用范围 | A 股上市公司 |
| 查询参数 | `stock_code`、`company_name`、`start_date`、`end_date`、`keywords`、`limit` |
| 当前用途 | 日报重大公告、可转债提示、董事会决议等信号 |
| 固化数据集优先 | `product/data/validated/stock_announcements/`，待建立 |
| 主来源 | 交易所公告、巨潮资讯、公司公告 |
| 校验来源 | 东方财富 `mx-finance-search`、东方财富公告、权威财经网站 |
| 更新频率 | 每日 |
| 时间口径 | 公告披露日 |
| 单位口径 | 非数值数据，必须保留标题、发布日期、来源和链接 |
| 当前状态 | 已迁入数据层 fetcher，优先通过本地 `mx-finance-search` 技能获取，必要时回退到本地 mx-search 缓存，待进一步结构化 |
| 当前代码位置 | `product/data/fetchers/signals.py` |

### 4.6 个股月度经营数据检索

| 字段 | 说明 |
| --- | --- |
| 数据能力 ID | `stock_monthly_operating_data` |
| 适用范围 | 有月度经营披露的上市公司 |
| 查询参数 | `stock_code`、`company_name`、`period`、`keywords` |
| 当前用途 | 月度销售简报、收入、销量、均价等经营兑现信号 |
| 固化数据集优先 | `product/data/validated/stock_monthly_operating_data/`，待建立 |
| 主来源 | 公司公告、交易所公告、巨潮资讯 |
| 校验来源 | 东方财富 `mx-finance-search`、权威财经网站 |
| 更新频率 | 按公司披露节奏，通常月度 |
| 时间口径 | 披露月份 / 经营月份必须区分 |
| 单位口径 | 按公告原文保留，结构化时统一收入为亿元、销量按公告口径 |
| 当前状态 | 已迁入数据层 fetcher，通过日报信号进入模型分析，待结构化字段 |
| 当前代码位置 | `product/data/fetchers/signals.py` |

### 4.7 生猪现货价格

| 字段 | 说明 |
| --- | --- |
| 数据能力 ID | `hog_spot_price` |
| 适用范围 | 生猪养殖行业分析 |
| 查询参数 | `start_date`、`end_date`、`frequency` |
| 当前用途 | 猪周期位置、养殖行业价格趋势 |
| 固化数据集优先 | `product/data/validated/hog_spot_price/`，待建立 |
| 主来源 | AkShare `spot_hog_year_trend_soozhu()` |
| 校验来源 | 搜猪网、农业农村部、权威财经网站，待固化 |
| 更新频率 | 每日 |
| 时间口径 | 自然日 |
| 单位口径 | 元/公斤 |
| 当前状态 | 已代码固化 |
| 当前代码位置 | `product/data/fetchers/hog_cycle.py` |

### 4.8 生猪期货价格

| 字段 | 说明 |
| --- | --- |
| 数据能力 ID | `hog_futures_price` |
| 适用范围 | 生猪养殖行业分析 |
| 查询参数 | `symbol`、`start_date`、`end_date`、`frequency` |
| 当前用途 | 市场远期预期、现货基差计算 |
| 固化数据集优先 | `product/data/validated/hog_futures_price/`，待建立 |
| 主来源 | AkShare `futures_main_sina("LH0")` |
| 校验来源 | 大连商品交易所行情数据，待固化 |
| 更新频率 | 交易日 |
| 时间口径 | 期货交易日 |
| 单位口径 | 原始多为元/吨，数据层统一换算为元/公斤 |
| 当前状态 | 已代码固化 |
| 当前代码位置 | `product/data/fetchers/hog_cycle.py` |

### 4.9 生猪现货基差

| 字段 | 说明 |
| --- | --- |
| 数据能力 ID | `hog_basis` |
| 适用范围 | 生猪养殖行业分析 |
| 查询参数 | `start_date`、`end_date`、`frequency` |
| 当前用途 | 判断现货与期货相对强弱 |
| 固化数据集优先 | `product/data/validated/hog_basis/`，待建立 |
| 主来源 | 派生指标：生猪现货价格 - 生猪期货价格 |
| 校验来源 | 无直接校验源，依赖两个底层数据能力可信度 |
| 更新频率 | 随现货和期货数据更新 |
| 时间口径 | 仅比较同月或同日可对齐数据 |
| 单位口径 | 元/公斤 |
| 当前状态 | 已代码固化 |
| 当前代码位置 | `product/data/fetchers/hog_cycle.py` |

### 4.10 VIX

| 字段 | 说明 |
| --- | --- |
| 数据能力 ID | `market_vix` |
| 适用范围 | 市场温度、宏观风险偏好 |
| 查询参数 | `start_date`、`end_date`、`frequency` |
| 当前用途 | 美股 ETF 买入决策 |
| 固化数据集优先 | `product/data/validated/market_vix/`，待建立 |
| 主来源 | Cboe 官方历史数据 |
| 校验来源 | 其他权威行情源，待固化 |
| 更新频率 | 交易日 |
| 时间口径 | 美股交易日 |
| 单位口径 | 指数点位 |
| 当前状态 | 已代码固化 |
| 当前代码位置 | `product/data/fetchers/market_data.py` |

### 4.10 CNN Fear & Greed

| 字段 | 说明 |
| --- | --- |
| 数据能力 ID | `market_fear_greed` |
| 适用范围 | 市场情绪、风险偏好 |
| 查询参数 | `start_date`、`end_date`、`frequency` |
| 当前用途 | 美股 ETF 买入决策 |
| 固化数据集优先 | `product/data/validated/market_fear_greed/`，待建立 |
| 主来源 | CNN Business |
| 校验来源 | 暂无稳定校验源 |
| 更新频率 | 每日 |
| 时间口径 | 自然日 / 市场日，按 CNN 返回时间为准 |
| 单位口径 | 0-100 分 |
| 当前状态 | 已代码固化 |
| 当前代码位置 | `product/data/fetchers/market_data.py` |

### 4.11 ETF 技术指标 RSI

| 字段 | 说明 |
| --- | --- |
| 数据能力 ID | `etf_rsi` |
| 适用范围 | ETF 技术指标 |
| 查询参数 | `symbol`、`period`、`start_date`、`end_date` |
| 当前用途 | QQQ RSI(14)，用于美股 ETF 买入决策 |
| 固化数据集优先 | `product/data/validated/etf_rsi/`，待建立 |
| 主来源 | Nasdaq 历史行情后本地计算 |
| 校验来源 | 其他行情源或技术指标库，待固化 |
| 更新频率 | 交易日 |
| 时间口径 | 美股交易日 |
| 单位口径 | RSI 分值，0-100 |
| 当前状态 | 已代码固化 |
| 当前代码位置 | `product/data/fetchers/market_data.py` |

## 5. 后续扩展规则

新增数据能力时，必须先补充本清单，再实现 fetcher 或调用逻辑。

新增条目必须回答：

1. 这个能力是否通用，还是某个标的的特例？
2. 查询参数是什么？
3. 固化数据集路径是什么？
4. 主来源是什么？
5. 校验来源是什么？
6. 时间口径和单位口径是什么？
7. 数据失败时是否允许继续分析？
8. 当前可信等级如何判断？

如果答案不清楚，先进入“待设计数据能力”，不要直接进入生产分析链路。
