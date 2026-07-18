"""估值 Agent 的输入输出结构定义。

职责：
- 定义估值分析请求、证据项和结果结构。
- 让上游调用方与模型调用层之间使用稳定的 JSON 口径。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValuationEvidenceItem:
    """单条估值证据。"""

    title: str
    source: str
    date: str
    content: str
    url: str = ""
    primary_source: str = ""
    verification_sources: list[str] = field(default_factory=list)
    confidence_level: str = ""


@dataclass(frozen=True)
class ValuationDataNeed:
    """单条估值数据诉求。"""

    title: str
    query: str
    required: bool = True
    preferred_sources: list[str] = field(default_factory=list)
    rationale: str = ""
    fallback_queries: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ValuationEvidenceBatch:
    """一轮补充得到的证据包。"""

    items: list[ValuationEvidenceItem] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    failed_sources: list[str] = field(default_factory=list)
    attempts: list["ValuationEvidenceAttempt"] = field(default_factory=list)


@dataclass(frozen=True)
class ValuationEvidenceAttempt:
    """单次数据补充尝试记录。"""

    need_title: str
    provider_name: str
    status: str
    evidence_count: int
    query: str = ""
    message: str = ""


@dataclass(frozen=True)
class ValuationRequest:
    """估值分析请求。"""

    symbol: str
    company_name: str
    as_of_date: str
    current_market_cap_billion: float | None = None
    current_price: float | None = None
    pe_ttm: float | None = None
    pb: float | None = None
    turnover_rate: float | None = None
    evidence_items: list[ValuationEvidenceItem] = field(default_factory=list)
    peer_notes: list[str] = field(default_factory=list)
    round_index: int = 1
    max_rounds: int = 5

    def to_prompt_payload(self) -> dict[str, Any]:
        """转换为 prompt 可直接消费的 JSON 结构。"""
        payload = asdict(self)
        payload["evidence_items"] = [asdict(item) for item in self.evidence_items]
        return payload


@dataclass(frozen=True)
class ValuationResult:
    """估值分析结果。"""

    valuation_status: str
    valuation_summary: str
    valuation_method: str
    current_market_cap_billion: float | None
    fair_value_range: str
    key_evidence: list[str]
    risk_points: list[str]
    missing_data: list[str]
    next_questions: list[str]
    source_list: list[str]
    data_needs: list[ValuationDataNeed] = field(default_factory=list)
    can_conclude: bool = False
    blocked_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为可直接序列化的字典。"""
        payload = asdict(self)
        payload["data_needs"] = [asdict(item) for item in self.data_needs]
        return payload
