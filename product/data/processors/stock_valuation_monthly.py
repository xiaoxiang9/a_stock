"""股票月度估值序列加工。

职责：
- 将 Tushare 或其他数据源返回的日频 PE/PB 数据压缩为月频序列。
- 计算最新月度快照和历史百分位。
- 为数据层存储和查询 API 提供统一的数据结构。

边界：
- 这里只做确定性数据处理，不访问数据库，不发起网络请求。
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class MonthlyValuationPoint:
    """单月估值点。"""

    month: str
    trade_date: str
    pe_ttm: float
    pb: float


def _month_key(trade_date: str) -> str:
    """把交易日转换成月维度键。"""
    cleaned = trade_date.strip()
    if not cleaned:
        return cleaned
    if "-" in cleaned:
        parts = cleaned.split("-")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"{parts[0]}-{parts[1][:2]}"
        return cleaned[:7]
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    if len(digits) >= 6:
        return f"{digits[:4]}-{digits[4:6]}"
    return cleaned


def _trade_date_sort_key(trade_date: str) -> str:
    """把不同格式的交易日归一为可比较的排序键。"""
    digits = "".join(ch for ch in trade_date if ch.isdigit())
    return digits or trade_date.strip()


def _to_float(value: Any) -> float | None:
    """把可选数值转换为浮点数。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def build_monthly_valuation_points(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """将日频估值数据压缩为月频序列。

    每个月只保留最后一个交易日的数据，保证月度记录与“当月最终状态”对齐。
    """
    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    sorted_rows = sorted(rows, key=lambda row: _trade_date_sort_key(str(row.get("trade_date", ""))))
    for row in sorted_rows:
        trade_date = str(row.get("trade_date", "")).strip()
        if not trade_date:
            continue
        pe_ttm = _to_float(row.get("pe_ttm"))
        pb = _to_float(row.get("pb"))
        if pe_ttm is None or pb is None:
            continue
        month = _month_key(trade_date)
        grouped[month] = {
            "month": month,
            "trade_date": trade_date,
            "pe_ttm": pe_ttm,
            "pb": pb,
        }
    return list(grouped.values())


def _percentile_rank(values: Sequence[float], latest_value: float) -> float:
    """计算最新值在历史序列中的经验百分位。"""
    valid_values = [value for value in values if value is not None]
    if not valid_values:
        return 0.0
    less_or_equal = sum(1 for value in valid_values if value <= latest_value)
    return round(less_or_equal / len(valid_values), 4)


def summarize_monthly_valuation_points(points: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """汇总月度估值序列，返回最新值和历史百分位。"""
    normalized_points = [
        {
            "month": str(point.get("month", "")).strip(),
            "trade_date": str(point.get("trade_date", "")).strip(),
            "pe_ttm": _to_float(point.get("pe_ttm")),
            "pb": _to_float(point.get("pb")),
        }
        for point in points
        if str(point.get("month", "")).strip()
    ]
    normalized_points = [point for point in normalized_points if point["pe_ttm"] is not None and point["pb"] is not None]
    if not normalized_points:
        return {
            "months": [],
            "pe_values": [],
            "pb_values": [],
            "latest_month": "",
            "latest_trade_date": "",
            "latest_pe_ttm": None,
            "latest_pb": None,
            "pe_percentile": 0.0,
            "pb_percentile": 0.0,
            "series_count": 0,
        }

    latest_point = normalized_points[-1]
    pe_values = [float(point["pe_ttm"]) for point in normalized_points]
    pb_values = [float(point["pb"]) for point in normalized_points]
    return {
        "months": [point["month"] for point in normalized_points],
        "pe_values": pe_values,
        "pb_values": pb_values,
        "latest_month": latest_point["month"],
        "latest_trade_date": latest_point["trade_date"],
        "latest_pe_ttm": latest_point["pe_ttm"],
        "latest_pb": latest_point["pb"],
        "pe_percentile": _percentile_rank(pe_values, float(latest_point["pe_ttm"])),
        "pb_percentile": _percentile_rank(pb_values, float(latest_point["pb"])),
        "series_count": len(normalized_points),
    }


def build_monthly_valuation_payload(
    *,
    ts_code: str,
    stock_name: str,
    listed_date: str | None,
    points: Sequence[Mapping[str, Any]],
    source: str = "Tushare",
) -> dict[str, Any]:
    """构造月度估值存储/返回 payload。"""
    summary = summarize_monthly_valuation_points(points)
    payload = {
        "ts_code": ts_code,
        "stock_name": stock_name,
        "listed_date": listed_date or "",
        "source": source,
        **summary,
    }
    return payload
