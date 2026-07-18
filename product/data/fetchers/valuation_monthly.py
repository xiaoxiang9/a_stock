"""股票月度估值历史取数。

职责：
- 读取 Tushare 的日频估值数据。
- 压缩为月频 PE/PB 序列，供数据层持久化和查询。

边界：
- 不做数据库写入。
- 不做投资判断。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

from product.data.processors.stock_valuation_monthly import build_monthly_valuation_points


def _to_records(rows: Any) -> list[dict[str, Any]]:
    """把 Tushare 返回值统一转成普通字典列表。"""
    if hasattr(rows, "to_dict"):
        return list(rows.to_dict("records"))
    return [dict(row) for row in rows]


def _resolve_date(value: str | None, default: date) -> str:
    """把业务日期转换成 Tushare 所需的 YYYYMMDD。"""
    if not value:
        return default.strftime("%Y%m%d")
    if "-" in value:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y%m%d")
    return value


def load_tushare_daily_basic_history(
    token: str,
    *,
    ts_code: str,
    start_date: str,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """读取指定标的的日频估值数据。"""
    import tushare as ts  # type: ignore

    pro = ts.pro_api(token)
    daily_basic = pro.daily_basic(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields="ts_code,trade_date,pe_ttm,pb",
    )
    return _to_records(daily_basic)


def fetch_monthly_valuation_points(
    token: str,
    *,
    ts_code: str,
    start_date: str = "19900101",
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """按月抓取指定标的的 PE/PB 历史点。"""
    normalized_end = _resolve_date(end_date, date.today())
    rows = load_tushare_daily_basic_history(
        token,
        ts_code=ts_code,
        start_date=start_date,
        end_date=normalized_end,
    )
    return build_monthly_valuation_points(rows)


def fetch_tushare_listed_stocks(token: str) -> list[dict[str, Any]]:
    """读取当前上市股票清单，用于全量初始化。"""
    import tushare as ts  # type: ignore

    pro = ts.pro_api(token)
    stock_basic = pro.stock_basic(exchange="", list_status="L", fields="ts_code,symbol,name,list_date")
    return _to_records(stock_basic)

