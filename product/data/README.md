# 数据层

数据层负责数据来源、获取、校验、缓存、数据库操作和衍生指标。

数据层不绑定具体标的。股票代码、公司名称、行业、时间范围、统计频率等都应作为查询参数传入。当前牧原股份日报只是通用数据能力的一组调用场景。

当前 data 子系统同时承担独立 HTTP API 的职责，对外提供月度 PE/PB 历史百分位查询、初始化落库和月度刷新入口。

## 配置边界

- 公开配置：`product/data/config/data.toml`
- 私密配置：`product/data/config/private.local.toml`
- 配置加载器：`product.data.config.data_config`、`product.data.config.private_config`

data 子系统不读取 app 子系统的配置文件，也不复用 app 的配置加载器。

## 数据获取优先级

1. 固化数据集 / 本地可信快照
2. 已代码固化的数据接口或 fetcher
3. Tushare
4. 东方财富 skill
5. 官方、交易所、监管、公司公告等权威公开来源
6. 权威财经网站，例如同花顺、新浪财经、Yahoo Finance 等
7. 互联网搜索，多信源验证

## 当前落地

- 月度 PE/PB 历史序列按 `ts_code` 存储为“一只股票一条记录”
- 支持全量初始化、月度刷新和按标的查询
- 查询结果直接返回最新月度值、月度序列和历史百分位

## 当前清单

- [通用数据能力清单](./catalog/data_capabilities.md)
- [关键数据来源入口](./catalog/key_data_sources.md)

关键数据能力必须进入数据能力清单，并尽量通过代码固化执行路径。任何进入模型分析的数据，都必须带来源、时间、口径和可信等级。
