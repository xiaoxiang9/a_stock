# 多 Agent 体系

多 Agent 研究体系负责宏观、行业、个股和估值分析的协同编排。

## 配置边界

- 公开配置：`product/agents/config/agents.toml`
- 私密配置：`product/agents/config/private.local.toml`
- 配置加载器：`product.agents.config.agents_config`、`product.agents.config.private_config`

agents 子系统不读取 app 子系统或 data 子系统的配置文件，也不复用它们的配置加载器。

## 当前状态

- `product/agents/scripts/start.sh` 会校验独立配置并检查 `websearch-deepseek` 数据源是否可用
- `product/agents/scripts/run_valuation.py` 可手动触发牧原估值多 Agent 闭环，打印循环数和最终结果
- `agents/valuation/` 已具备独立估值分析骨架，包含预填、证据收集、prompt 和结果收敛
- `AkShare` 已作为 `agents` 子系统的通用行情和猪周期 provider 纳入估值取数链路
- `websearch-deepseek` 已作为 `agents` 子系统的联网搜索 provider 纳入估值取数链路
- 研究工作流与其他 Agent 逻辑后续再接入 `workflows/` 和 `agents/`

## 估值 Agent 取数边界

- 代码层不做指标级汇总或冲突裁决，统一交给模型完成合并、排序和解释
- 估值 Agent 会先对请求做确定性预填，再把预填后的请求交给模型分析
- 多渠道原始证据都要保留给模型，由模型统一完成合并、排序和解释
- 第三轮及之后若仍需补数，数据获取 Agent 会自动把剩余可用渠道补入查询顺序，进入全渠道扫描模式
- 网络搜索证据的来源优先级和误差判断交给模型，但 prompt 会明确公告、政府官方、企业官方、权威媒体的建议顺序
- 证据收集失败时只降级，不阻断分析流程
