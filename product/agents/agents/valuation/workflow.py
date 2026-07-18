"""估值 Agent 多轮调度工作流。

职责：
- 协调估值 Agent 与数据获取 Agent 的多轮补证闭环。
- 控制最大轮数、必要数据缺失和收敛终止。
- 只负责编排，不承载具体取数和估值判断逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .agent import ValuationAgent
from .data_agent import DataAcquisitionAgent
from .schemas import ValuationEvidenceAttempt, ValuationEvidenceItem, ValuationRequest, ValuationResult


@dataclass(frozen=True)
class ValuationResearchRound:
    """单轮研究记录。"""

    round_index: int
    valuation_result: ValuationResult
    request_snapshot: dict[str, Any] = field(default_factory=dict)
    prefill_notes: list[str] = field(default_factory=list)
    added_evidence: list[ValuationEvidenceItem] = field(default_factory=list)
    acquisition_attempts: list[ValuationEvidenceAttempt] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ValuationResearchOutcome:
    """多轮估值研究最终结果。"""

    final_request: ValuationRequest
    final_result: ValuationResult
    rounds: list[ValuationResearchRound]
    termination_reason: str


def _merge_request(
    request: ValuationRequest,
    *,
    evidence_items: list[ValuationEvidenceItem] | None = None,
    peer_notes: list[str] | None = None,
    round_index: int | None = None,
    max_rounds: int | None = None,
) -> ValuationRequest:
    """合并请求与新增证据。"""
    merged_evidence = list(request.evidence_items)
    if evidence_items:
        merged_evidence.extend(evidence_items)
    merged_notes = list(request.peer_notes)
    if peer_notes:
        merged_notes.extend(peer_notes)
    return replace(
        request,
        evidence_items=merged_evidence,
        peer_notes=merged_notes,
        round_index=round_index or request.round_index,
        max_rounds=max_rounds or request.max_rounds,
    )


@dataclass(frozen=True)
class ValuationResearchCoordinator:
    """估值研究多 Agent 协调器。"""

    valuation_agent: ValuationAgent
    data_agent: DataAcquisitionAgent = field(default_factory=DataAcquisitionAgent)
    max_rounds: int = 5

    def run(self, request: ValuationRequest) -> ValuationResearchOutcome:
        """运行多轮补证估值研究。"""
        working_request = request

        rounds: list[ValuationResearchRound] = []
        final_result: ValuationResult | None = None
        termination_reason = "未收敛"

        for round_index in range(1, self.max_rounds + 1):
            working_request = _merge_request(
                working_request,
                round_index=round_index,
                max_rounds=self.max_rounds,
            )
            # 先由估值 Agent 预填稳定字段，再进入本轮模型分析。
            prepared_request = self.valuation_agent.prepare_request(working_request)
            working_request = prepared_request.request
            final_result = self.valuation_agent.run(working_request)
            rounds.append(
                ValuationResearchRound(
                    round_index=round_index,
                    request_snapshot=working_request.to_prompt_payload(),
                    prefill_notes=prepared_request.notes,
                    valuation_result=final_result,
                )
            )

            if final_result.can_conclude or not final_result.data_needs:
                termination_reason = "估值结论已收敛"
                break

            if round_index >= self.max_rounds:
                termination_reason = "达到最大轮数"
                break

            full_channel_expansion = round_index >= 3
            evidence_batch = self.data_agent.collect(
                working_request,
                final_result.data_needs,
                full_channel_expansion=full_channel_expansion,
            )
            rounds[-1] = replace(
                rounds[-1],
                added_evidence=evidence_batch.items,
                acquisition_attempts=evidence_batch.attempts,
                notes=evidence_batch.notes,
            )
            if not evidence_batch.items:
                termination_reason = "必要数据缺失且未找到可替代来源"
                break

            working_request = _merge_request(
                working_request,
                evidence_items=evidence_batch.items,
                peer_notes=evidence_batch.notes,
                round_index=round_index + 1,
                max_rounds=self.max_rounds,
            )

        if final_result is None:
            raise RuntimeError("Valuation research did not produce any result.")

        return ValuationResearchOutcome(
            final_request=working_request,
            final_result=final_result,
            rounds=rounds,
            termination_reason=termination_reason,
        )
