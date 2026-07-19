"""估值 Agent 的 prompt 构造。

职责：
- 固定估值分析口径和输出 schema。
- 让模型先补数，再收敛结论，避免一开始就给出伪完整判断。
"""

from __future__ import annotations

import json

from .schemas import ValuationRequest


def build_valuation_prompt(request: ValuationRequest) -> str:
    """构造估值分析 prompt。

    估值 Agent 只分析上游传入的证据包，不自行编造外部数据。
    如果证据不足，必须明确输出缺失项和下一步需要补充的问题。
    """
    instruction = f"""
你是A股估值分析 Agent。你的任务是根据输入的股票代码、公司名称、估值快照和外部证据，输出一份结构化估值结果。

要求：
1. 只能基于输入内容分析，不要编造不存在的数据。
2. 如果证据不足，必须明确写出 missing_data 和 next_questions。
3. 允许先给出暂定判断，但必须说明判断依据和不确定性。
4. 重点关注当前市值、PE(TTM)、PB、价格位置、行业周期和公开证据；其中部分稳定字段可能已由 Agent 预填。
5. 你的输入可能包含多渠道原始证据，重复和冲突都要由你自己汇总，不要假设上游已经做过裁决。
6. 如果同一指标来自多个来源，先按证据强度自行合并，再在 source_list 和 cross_validation_notes 中说明主来源、验证来源和冲突来源。
7. 如果网络搜索结果都带有明确来源，优先级按公告 > 政府官方 > 企业官方 > 权威媒体；如果是非搜索高置信度数据，优先保留非搜索来源。
8. 如果不同来源误差在可接受范围内，可以合并并保留验证来源；如果误差超出范围，要显式保留冲突并说明为什么保留当前主来源。
9. 如果核心数据还不够，必须给出 data_needs，便于数据获取 Agent 继续补数。
10. 如果已经足够形成判断，can_conclude 输出 true。
11. 如果缺失数据且没有替代方案，blocked_reason 必须说明原因。
12. 当前处于第 {request.round_index} 轮，最多 {request.max_rounds} 轮。请在 data_needs 中控制补数粒度。
13. 不要输出 Markdown，不要输出代码块，只输出严格 JSON。

输出 JSON schema：
{{
  "valuation_status": "偏低估/合理/偏高估/数据不足",
  "valuation_summary": "一句话结论",
  "valuation_method": "估值方法或判断框架",
  "current_market_cap_billion": 0.0,
  "fair_value_range": "区间或判断范围",
  "key_evidence": ["核心依据1", "核心依据2"],
  "risk_points": ["主要风险1", "主要风险2"],
  "missing_data": ["缺失项1"],
  "next_questions": ["下一步需要补充的问题1"],
  "source_list": ["来源1", "来源2"],
          "data_needs": [
        {{
          "title": "缺失数据项",
          "query": "用于获取该数据的自然语言查询",
          "required": true,
          "preferred_sources": ["tushare", "akshare", "mx-finance-data", "mx-finance-search", "mx-data", "mx-search", "websearch-deepseek"],
          "rationale": "为什么需要这个数据",
          "fallback_queries": ["可替代查询1", "可替代查询2"]
        }}
      ],
  "cross_validation_notes": ["多源重复证据如何统一", "如果存在差异，差异来自哪里"],
  "can_conclude": false,
  "blocked_reason": ""
}}
""".strip()
    return f"{instruction}\n\n输入数据：\n{json.dumps(request.to_prompt_payload(), ensure_ascii=False, indent=2)}"
