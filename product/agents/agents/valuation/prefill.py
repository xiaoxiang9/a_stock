"""估值 Agent 的预填逻辑。

职责：
- 从估值请求已有证据中提取稳定快照字段。
- 仅补齐分析入口需要的确定性字段，不承担数据获取职责。
- 保持幂等，方便 Agent 和工作流重复调用而不污染结果。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from .schemas import ValuationEvidenceItem, ValuationRequest


_PRICE_PATTERN = re.compile(r"收盘价\s*([0-9]+(?:\.[0-9]+)?)\s*元")
_PE_PATTERN = re.compile(r"PE(?:\(TTM\)|TTM)?\s*([0-9]+(?:\.[0-9]+)?)\s*倍")
_PB_PATTERN = re.compile(r"PB\s*([0-9]+(?:\.[0-9]+)?)\s*倍")
_TURNOVER_PATTERN = re.compile(r"换手率\s*([0-9]+(?:\.[0-9]+)?)\s*%")
_MARKET_CAP_PATTERN = re.compile(r"总市值\s*([0-9]+(?:\.[0-9]+)?)\s*亿元")


@dataclass(frozen=True)
class ValuationPrefillResult:
    """预填后的估值请求与预填说明。"""

    request: ValuationRequest
    notes: list[str]


def _extract_snapshot_fields(content: str) -> dict[str, float]:
    """从证据文本中提取可稳定复用的估值快照字段。"""
    snapshot: dict[str, float] = {}
    price_match = _PRICE_PATTERN.search(content)
    if price_match:
        snapshot["current_price"] = float(price_match.group(1))
    pe_match = _PE_PATTERN.search(content)
    if pe_match:
        snapshot["pe_ttm"] = float(pe_match.group(1))
    pb_match = _PB_PATTERN.search(content)
    if pb_match:
        snapshot["pb"] = float(pb_match.group(1))
    turnover_match = _TURNOVER_PATTERN.search(content)
    if turnover_match:
        snapshot["turnover_rate"] = float(turnover_match.group(1))
    market_cap_match = _MARKET_CAP_PATTERN.search(content)
    if market_cap_match:
        snapshot["current_market_cap_billion"] = float(market_cap_match.group(1))
    return snapshot


def _build_prefill_note(item: ValuationEvidenceItem, filled_fields: list[str]) -> str:
    """构造预填说明，方便在 prompt 和 trace 中回溯。"""
    source = item.source.strip() or "未知来源"
    field_text = "、".join(filled_fields)
    return f"预填快照来自 {source}：{field_text}"


def prefill_valuation_request(request: ValuationRequest) -> ValuationPrefillResult:
    """从已有证据中补齐稳定快照字段。

    该函数只处理确定性字段，不访问任何外部数据源。
    """
    current_price = request.current_price
    pe_ttm = request.pe_ttm
    pb = request.pb
    turnover_rate = request.turnover_rate
    current_market_cap_billion = request.current_market_cap_billion
    notes = list(request.peer_notes)
    prefill_notes: list[str] = []

    for item in request.evidence_items:
        snapshot = _extract_snapshot_fields(item.content)
        filled_fields: list[str] = []
        if current_price is None and "current_price" in snapshot:
            current_price = snapshot["current_price"]
            filled_fields.append(f"current_price={current_price:.2f}")
        if pe_ttm is None and "pe_ttm" in snapshot:
            pe_ttm = snapshot["pe_ttm"]
            filled_fields.append(f"pe_ttm={pe_ttm:.2f}")
        if pb is None and "pb" in snapshot:
            pb = snapshot["pb"]
            filled_fields.append(f"pb={pb:.3f}")
        if turnover_rate is None and "turnover_rate" in snapshot:
            turnover_rate = snapshot["turnover_rate"]
            filled_fields.append(f"turnover_rate={turnover_rate:.3f}")
        if current_market_cap_billion is None and "current_market_cap_billion" in snapshot:
            current_market_cap_billion = snapshot["current_market_cap_billion"]
            filled_fields.append(f"current_market_cap_billion={current_market_cap_billion:.2f}")
        if filled_fields:
            prefill_notes.append(_build_prefill_note(item, filled_fields))
        if (
            current_price is not None
            and pe_ttm is not None
            and pb is not None
            and turnover_rate is not None
            and current_market_cap_billion is not None
        ):
            break

    if prefill_notes:
        notes.extend(prefill_notes)

    return ValuationPrefillResult(
        request=replace(
            request,
            current_market_cap_billion=current_market_cap_billion,
            current_price=current_price,
            pe_ttm=pe_ttm,
            pb=pb,
            turnover_rate=turnover_rate,
            peer_notes=notes,
        ),
        notes=prefill_notes,
    )
