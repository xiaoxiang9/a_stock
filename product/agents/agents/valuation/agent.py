"""估值 Agent 执行器。

职责：
- 先对输入请求做确定性预填。
- 将预填后的请求转成提示词。
- 调用上游提供的模型执行器，输出结构化估值结果。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from .prompt import build_valuation_prompt
from .prefill import ValuationPrefillResult, prefill_valuation_request
from .schemas import ValuationDataNeed, ValuationRequest, ValuationResult


class ValuationModelRunner(Protocol):
    """估值 Agent 使用的模型执行器协议。"""

    def __call__(self, prompt: str) -> dict[str, Any] | str: ...


def _normalize_list(value: Any) -> list[str]:
    """把任意序列化值收敛为字符串列表。"""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_result(raw: dict[str, Any]) -> ValuationResult:
    """清洗模型输出，确保估值结果字段稳定。"""
    data_needs: list[ValuationDataNeed] = []
    for item in raw.get("data_needs", []) or []:
        if not isinstance(item, dict):
            continue
        data_needs.append(
            ValuationDataNeed(
                title=str(item.get("title", "")).strip() or "未命名诉求",
                query=str(item.get("query", "")).strip(),
                required=bool(item.get("required", True)),
                preferred_sources=[str(source).strip() for source in item.get("preferred_sources", []) if str(source).strip()],
                rationale=str(item.get("rationale", "")).strip(),
                fallback_queries=[str(source).strip() for source in item.get("fallback_queries", []) if str(source).strip()],
            )
        )
    return ValuationResult(
        valuation_status=str(raw.get("valuation_status", "数据不足")).strip() or "数据不足",
        valuation_summary=str(raw.get("valuation_summary", "")).strip() or "暂无结论",
        valuation_method=str(raw.get("valuation_method", "")).strip() or "暂未明确",
        current_market_cap_billion=(
            float(raw["current_market_cap_billion"])
            if raw.get("current_market_cap_billion") not in (None, "")
            else None
        ),
        fair_value_range=str(raw.get("fair_value_range", "")).strip() or "暂无范围",
        key_evidence=_normalize_list(raw.get("key_evidence")),
        risk_points=_normalize_list(raw.get("risk_points")),
        missing_data=_normalize_list(raw.get("missing_data")),
        next_questions=_normalize_list(raw.get("next_questions")),
        source_list=_normalize_list(raw.get("source_list")),
        data_needs=data_needs,
        can_conclude=bool(raw.get("can_conclude", False)),
        blocked_reason=str(raw.get("blocked_reason", "")).strip(),
    )


@dataclass(frozen=True)
class ValuationAgent:
    """估值分析 Agent。

    该 Agent 负责把请求和外部证据收敛成结构化结论。
    """

    model_runner: ValuationModelRunner

    def prepare_request(self, request: ValuationRequest) -> ValuationPrefillResult:
        """对估值请求做确定性预填。"""
        return prefill_valuation_request(request)

    def run(self, request: ValuationRequest) -> ValuationResult:
        """执行一次估值分析。"""
        prepared = self.prepare_request(request)
        prompt = build_valuation_prompt(prepared.request)
        raw_output = self.model_runner(prompt)
        if isinstance(raw_output, str):
            raw = json.loads(raw_output)
        else:
            raw = raw_output
        if not isinstance(raw, dict):
            raise RuntimeError("Valuation Agent output must be a JSON object.")
        return _normalize_result(raw)
