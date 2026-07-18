#!/usr/bin/env python3

"""估值 Agent 手动验证脚本。

职责：
- 用牧原股份样本数据手动触发估值多 Agent 闭环。
- 打印每一轮结果、补数诉求和最终循环数。
- 默认使用本地可控 runner 便于快速验证流程；需要真实模型时可切到 real 模式。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from product.agents.agents.valuation import (  # noqa: E402
    DataAcquisitionAgent,
    ValuationAgent,
    ValuationDataNeed,
    ValuationEvidenceItem,
    ValuationRequest,
    ValuationResearchCoordinator,
)
from product.app.backend.infrastructure.model_service import ModelService  # noqa: E402


def build_muyuan_sample_request(report_date: str) -> ValuationRequest:
    """构造牧原股份手动验证请求。

    这里只放原始证据，不预填快照字段，保持与正式 Agent 链路一致。
    """
    return ValuationRequest(
        symbol="002714.SZ",
        company_name="牧原股份",
        as_of_date=report_date,
        evidence_items=[
            ValuationEvidenceItem(
                title="牧原股份原始经营背景",
                source="项目文档",
                date="2026-06-27",
                content="公司仍处于猪周期波动环境中，估值判断需要结合价格、盈利和行业位置。",
            ),
            ValuationEvidenceItem(
                title="牧原股份原始价格证据",
                source="Tushare",
                date="2026-06-27",
                content="收盘价 33.56 元，PE(TTM) 19.81 倍，PB 2.246 倍，换手率 2.759%，总市值 1937.42 亿元。",
            ),
        ],
        peer_notes=[
            "样本数据来自现有牧原日报口径",
            "先验证多轮协作和回调链路，再切真实模型",
        ],
    )


def build_mock_data_agent() -> DataAcquisitionAgent:
    """构造可控的数据获取 Agent。"""

    class _MockProvider:
        """本地可控证据提供方。"""

        name = "websearch-deepseek"

        def fetch(self, request: ValuationRequest, need: ValuationDataNeed) -> list[ValuationEvidenceItem]:
            return [
                ValuationEvidenceItem(
                    title=f"{need.title}补充证据",
                    source="网页搜索",
                    date=request.as_of_date,
                    content=f"围绕 {request.company_name} 的 {need.query} 已检索到可用公开证据。",
                    url="https://example.com/valuation-evidence",
                )
            ]

    return DataAcquisitionAgent(providers=[_MockProvider()])


def build_mock_runner() -> Any:
    """构造可控的模型 runner。

    第一轮先提出数据诉求，第二轮在补证后收敛。
    """
    state = {"calls": 0}

    def _runner(prompt: str) -> dict[str, Any]:
        state["calls"] += 1
        if state["calls"] == 1:
            return {
                "valuation_status": "数据不足",
                "valuation_summary": "当前原始证据可支撑初步判断，但还需要历史估值分位来确认位置。",
                "valuation_method": "原始证据 + 历史分位补证",
                "current_market_cap_billion": 1937.42,
                "fair_value_range": "暂无",
                "key_evidence": [
                    "Tushare 原始价格证据显示收盘价 33.56 元、PE(TTM) 19.81 倍、PB 2.246 倍。",
                    "项目文档提供了行业背景证据。",
                ],
                "risk_points": ["缺少历史估值分位，暂时不能判断当前是否处于低位区间。"],
                "missing_data": ["历史估值分位", "三年估值区间对照"],
                "next_questions": ["补充牧原股份近三年PE TTM/PB历史区间。"],
                "source_list": ["Tushare", "项目文档"],
                "data_needs": [
                    {
                        "title": "历史估值分位",
                        "query": "牧原股份近三年PE TTM PB历史区间",
                        "required": True,
                        "preferred_sources": ["websearch-deepseek"],
                        "rationale": "判断当前估值位置是否偏低估",
                        "fallback_queries": ["牧原股份 估值 历史区间", "牧原股份 PB PE 历史数据"],
                    }
                ],
                "can_conclude": False,
                "blocked_reason": "",
            }
        return {
            "valuation_status": "合理",
            "valuation_summary": "补齐历史分位后，当前估值更接近合理区间，暂不支持激进追高。",
            "valuation_method": "原始证据 + 历史分位对照",
            "current_market_cap_billion": 1937.42,
            "fair_value_range": "1800-2100 亿元",
            "key_evidence": [
                "Tushare 原始价格证据显示收盘价 33.56 元、PE(TTM) 19.81 倍、PB 2.246 倍。",
                "联网补充证据显示历史估值区间存在可对照参考。",
            ],
            "risk_points": [
                "猪周期波动仍可能导致利润与估值弹性变化。",
            ],
            "missing_data": [],
            "next_questions": ["后续继续补充历史分位和行业周期位置。"],
            "source_list": ["Tushare", "websearch-deepseek", "项目文档"],
            "data_needs": [],
            "can_conclude": True,
            "blocked_reason": "",
        }

    return _runner


def run_demo(mode: str, report_date: str) -> dict[str, Any]:
    """执行一次估值手动验证。"""
    request = build_muyuan_sample_request(report_date)
    if mode == "real":
        model_service = ModelService.from_project_config()
        valuation_agent = ValuationAgent(model_runner=model_service.complete_json)
        data_agent = DataAcquisitionAgent()
    else:
        valuation_agent = ValuationAgent(
            model_runner=build_mock_runner(),
        )
        data_agent = build_mock_data_agent()

    coordinator = ValuationResearchCoordinator(
        valuation_agent=valuation_agent,
        data_agent=data_agent,
        max_rounds=5,
    )
    outcome = coordinator.run(request)
    return {
        "mode": mode,
        "report_date": report_date,
        "rounds": len(outcome.rounds),
        "termination_reason": outcome.termination_reason,
        "final_result": outcome.final_result.to_dict(),
        "round_details": [
            {
                "round_index": item.round_index,
                "request_snapshot": item.request_snapshot,
                "prefill_notes": item.prefill_notes,
                "valuation_status": item.valuation_result.valuation_status,
                "valuation_summary": item.valuation_result.valuation_summary,
                "data_needs": [need.title for need in item.valuation_result.data_needs],
                "added_evidence": [
                    {
                        "title": evidence.title,
                        "source": evidence.source,
                        "date": evidence.date,
                        "content": evidence.content,
                        "url": evidence.url,
                    }
                    for evidence in item.added_evidence
                ],
                "acquisition_attempts": [
                    {
                        "need_title": attempt.need_title,
                        "provider_name": attempt.provider_name,
                        "status": attempt.status,
                        "evidence_count": attempt.evidence_count,
                        "query": attempt.query,
                        "message": attempt.message,
                    }
                    for attempt in item.acquisition_attempts
                ],
                "notes": item.notes,
            }
            for item in outcome.rounds
        ],
    }


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="Manually run Muyuan valuation agent.")
    parser.add_argument("--mode", choices=["mock", "real"], default="mock", help="Run mode.")
    parser.add_argument("--date", default="2026-06-28", help="Report date in YYYY-MM-DD format.")
    return parser.parse_args()


def main() -> int:
    """命令行入口。"""
    args = parse_args()
    result = run_demo(mode=args.mode, report_date=args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
