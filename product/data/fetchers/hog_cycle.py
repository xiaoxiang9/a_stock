"""生猪行业数据能力。

职责：
- 从 AkShare 读取生猪现货和期货主连数据。
- 统一单位为元/公斤。
- 构造现货、生猪期货、现货基差三类趋势卡片。

边界：
- 本文件只做数据获取、字段归一、单位转换和派生指标计算。
- 不判断猪周期位置，也不输出投资建议。
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any, Iterable


SPOT_SOURCE_NAME = "AkShare spot_hog_year_trend_soozhu()"
FUTURES_SOURCE_NAME = 'AkShare futures_main_sina("LH0")'
BASIS_SOURCE_NAME = "现货价 - 期货价（均换算为元/公斤）"
TON_TO_KG = 1000.0


@dataclass(frozen=True)
class NormalizedPoint:
    """归一化后的时间序列点。"""

    date: str
    value: float


def _round(value: float) -> float:
    """统一保留两位小数。"""
    return round(float(value), 2)


def _format_value(value: float, unit: str) -> str:
    """格式化带单位的指标展示值。"""
    if unit:
        return f"{_round(value):.2f} {unit}"
    return f"{_round(value):.2f}"


def _pick_first_present(row: dict[str, Any], keys: Iterable[str]) -> Any:
    """按候选字段顺序取第一个非空值。"""
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return None


def _normalize_points(
    rows: Iterable[dict[str, Any]],
    date_keys: Iterable[str],
    value_keys: Iterable[str],
) -> list[NormalizedPoint]:
    """把不同数据源字段名归一成 date/value。"""
    points: list[NormalizedPoint] = []
    for row in rows:
        raw_date = _pick_first_present(row, date_keys)
        raw_value = _pick_first_present(row, value_keys)
        if raw_date in (None, "") or raw_value in (None, ""):
            continue
        day = str(raw_date).strip()
        try:
            datetime.strptime(day, "%Y-%m-%d")
        except ValueError:
            continue
        points.append(NormalizedPoint(date=day, value=_round(float(raw_value))))
    points.sort(key=lambda point: point.date)
    return points


def _monthly_last_points(points: list[dict[str, Any]], months: int = 12) -> list[dict[str, Any]]:
    """按月取最后一个可用观测值。"""
    if not points:
        return []
    monthly: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for point in points:
        month = str(point["date"])[:7]
        monthly[month] = {"date": str(point["date"]), "value": _round(float(point["value"]))}
    ordered = sorted(monthly.values(), key=lambda item: item["date"])
    if months > 0:
        ordered = ordered[-months:]
    return ordered


def _month_index(points: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """按年月索引趋势点，方便计算同月基差。"""
    return {str(point["date"])[:7]: point for point in points}


def _build_basis_monthly(
    spot_monthly: list[dict[str, Any]],
    futures_monthly: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """用同月现货价减期货价计算基差。"""
    spot_map = _month_index(spot_monthly)
    futures_map = _month_index(futures_monthly)
    basis_points: list[dict[str, Any]] = []
    for month in sorted(set(spot_map) & set(futures_map)):
        spot_value = float(spot_map[month]["value"])
        futures_value = float(futures_map[month]["value"])
        basis_points.append(
            {
                "date": max(str(spot_map[month]["date"]), str(futures_map[month]["date"])),
                "value": _round(spot_value - futures_value),
            }
        )
    return basis_points


def _trend_sentence(name: str, values: list[float], period: str) -> str:
    """根据首尾变化生成趋势卡片的一句话说明。"""
    if len(values) < 2:
        return f"{period}样本不足，暂不做趋势判断。"
    start = values[0]
    end = values[-1]
    if start == 0:
        return f"{period}起点为零，当前仅展示走势，不做幅度判断。"
    change = (end - start) / abs(start)
    if change >= 0.05:
        direction = "明显上行"
    elif change <= -0.05:
        direction = "明显回落"
    elif change > 0:
        direction = "温和抬升"
    elif change < 0:
        direction = "温和回落"
    else:
        direction = "基本持平"
    return f"{name}{period}{direction}，最新值为{end:.2f}。"


def _metric(
    *,
    name: str,
    period: str,
    unit: str,
    values: list[dict[str, Any]],
    source_name: str,
    methodology: str,
    stroke: str,
) -> dict[str, Any]:
    """把月度时间序列封装成前端和邮件共用的趋势卡片结构。"""
    if not values:
        raise ValueError(f"{name} 没有可用数据")
    latest = values[-1]
    numeric_values = [float(item["value"]) for item in values]
    latest_value = float(latest["value"])
    return {
        "name": name,
        "period": period,
        "latest": _format_value(latest_value, unit),
        "latest_value": _round(latest_value),
        "updated_at": str(latest["date"]),
        "unit": unit,
        "values": numeric_values,
        "points": [{"date": str(item["date"]), "value": _round(float(item["value"]))} for item in values],
        "explanation": _trend_sentence(name, numeric_values, period),
        "stroke": stroke,
        "methodology": methodology,
        "source": {"name": source_name, "url": ""},
    }


def build_hog_cycle_metrics(
    spot_points: list[dict[str, Any]],
    futures_points: list[dict[str, Any]],
    *,
    months: int = 12,
) -> list[dict[str, Any]]:
    """构造猪周期三张趋势卡片：现货、期货、基差。"""
    spot_monthly = _monthly_last_points(spot_points, months=months)
    futures_monthly = _monthly_last_points(futures_points, months=months)
    futures_monthly_kg = [
        {"date": item["date"], "value": _round(float(item["value"]) / TON_TO_KG)} for item in futures_monthly
    ]
    basis_monthly = _build_basis_monthly(spot_monthly, futures_monthly_kg)
    return [
        _metric(
            name="现货生猪",
            period="今年以来（月度）",
            unit="元/公斤",
            values=spot_monthly,
            source_name=SPOT_SOURCE_NAME,
            methodology="AkShare 仅提供今年以来走势，按月取该月最后一个可用监测日价格",
            stroke="#2563eb",
        ),
        _metric(
            name="生猪期货",
            period=f"近{months}个月（月度）",
            unit="元/公斤",
            values=futures_monthly_kg,
            source_name=FUTURES_SOURCE_NAME,
            methodology="按月取 LH0 主力连续的最后一个可用交易日结算价，并换算为元/公斤",
            stroke="#7c3aed",
        ),
        _metric(
            name="现货基差",
            period="今年以来可用月份（月度）",
            unit="元/公斤",
            values=basis_monthly,
            source_name=BASIS_SOURCE_NAME,
            methodology="现货价格与期货结算价统一换算为元/公斤后计算差值",
            stroke="#16a34a",
        ),
    ]


def _load_points_from_akshare() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """从 AkShare 拉取现货生猪和生猪期货主连数据。"""
    import akshare as ak  # type: ignore

    spot_df = ak.spot_hog_year_trend_soozhu()
    futures_df = ak.futures_main_sina(symbol="LH0")
    spot_points = _normalize_points(spot_df.to_dict("records"), ("日期", "date"), ("价格", "price"))
    futures_points = _normalize_points(
        futures_df.to_dict("records"),
        ("日期", "date"),
        ("动态结算价", "settle", "收盘价", "close"),
    )
    if not futures_points:
        futures_points = _normalize_points(
            futures_df.to_dict("records"),
            ("日期", "date"),
            ("收盘价", "close", "动态结算价", "settle"),
        )
    return (
        [{"date": point.date, "value": point.value} for point in spot_points],
        [{"date": point.date, "value": point.value} for point in futures_points],
    )


@lru_cache(maxsize=1)
def get_hog_cycle_metrics(months: int = 12) -> list[dict[str, Any]]:
    """获取猪周期趋势指标。"""
    spot_points, futures_points = _load_points_from_akshare()
    return build_hog_cycle_metrics(spot_points, futures_points, months=months)


def render_hog_cycle_lines(metrics: list[dict[str, Any]]) -> list[str]:
    """把猪周期指标转换为 Markdown 报告中的摘要行。"""
    lines: list[str] = []
    for metric in metrics:
        source = str(metric.get("source", {}).get("name", ""))
        updated_at = str(metric.get("updated_at", ""))
        explanation = str(metric.get("explanation", ""))
        lines.append(
            f"{metric['name']}：{metric['latest']}｜最新日期 {updated_at}｜来源：{source}｜趋势：{explanation}"
        )
    return lines
