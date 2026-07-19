"""A 股个股数据能力。

职责：
- 提供个股行情、估值、市值、交易热度等通用数据能力。
- 封装 Tushare 主数据获取和东方财富校验数据解析。
- 为日报任务和未来数据 skill 提供统一入口。

边界：
- 本文件只做确定性取数、字段合并、单位转换和格式化。
- 不判断公司好坏、估值高低或交易建议。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

def _row_value(row: Any, key: str) -> Any:
    """兼容 pandas Series 和普通 dict 的字段读取。"""
    if hasattr(row, "__getitem__"):
        return row[key]
    return row.get(key)


def _sort_rows_desc(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """按交易日倒序排列普通字典行。"""
    return sorted(rows, key=lambda row: str(row["trade_date"]), reverse=True)


def _is_dataframe(value: Any) -> bool:
    """判断对象是否表现为 pandas DataFrame。"""
    return hasattr(value, "empty") and hasattr(value, "sort_values") and hasattr(value, "iloc")


def _rows_empty(rows: Any) -> bool:
    """判断 DataFrame 或普通行列表是否为空。"""
    if _is_dataframe(rows):
        return bool(rows.empty)
    return not list(rows)


def _sort_history(daily: Any, daily_basic: Any) -> tuple[Any, Any]:
    """统一排序 Tushare 返回的行情和基础指标数据。"""
    if _is_dataframe(daily):
        return (
            daily.sort_values("trade_date", ascending=False),
            daily_basic.sort_values("trade_date", ascending=False),
        )
    return _sort_rows_desc(daily), _sort_rows_desc(daily_basic)


def _latest_row(rows: Any) -> Any:
    """读取已按交易日倒序排列后的最新一行。"""
    if _is_dataframe(rows):
        return rows.iloc[0]
    return rows[0]


def _resolve_tushare_window(as_of_date: str | None = None, lookback_days: int = 180) -> tuple[str, str]:
    """根据业务时点动态计算 Tushare 查询窗口。

    约定：
    - end_date 取 as_of_date；若未传入，则取当天日期
    - start_date 按 lookback_days 向前回溯
    - 这里不做跨日缓存，保证每次执行都重新判断最新交易日
    """
    end_day = date.fromisoformat(as_of_date) if as_of_date else date.today()
    start_day = end_day - timedelta(days=max(lookback_days, 1))
    return start_day.strftime("%Y%m%d"), end_day.strftime("%Y%m%d")


def load_tushare_history(
    token: str,
    *,
    ts_code: str,
    as_of_date: str | None = None,
    lookback_days: int = 180,
) -> tuple[Any, Any]:
    """通过 Tushare 读取个股行情和基础估值数据。"""
    import tushare as ts  # type: ignore

    start_date, end_date = _resolve_tushare_window(as_of_date=as_of_date, lookback_days=lookback_days)
    pro = ts.pro_api(token)
    daily = pro.daily(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields="ts_code,trade_date,open,high,low,close,pct_chg,vol,amount",
    )
    daily_basic = pro.daily_basic(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields="ts_code,trade_date,turnover_rate,turnover_rate_f,volume_ratio,pe,pe_ttm,pb,total_share,float_share,free_share,total_mv,circ_mv",
    )
    return _sort_history(daily, daily_basic)


def build_stock_snapshot(daily_rows: Any, basic_rows: Any) -> tuple[str, dict[str, float]]:
    """根据行情和估值数据构造最新交易日快照。"""
    daily, daily_basic = _sort_history(daily_rows, basic_rows)
    if _rows_empty(daily) or _rows_empty(daily_basic):
        raise RuntimeError("No stock data returned.")

    latest_daily = _latest_row(daily)
    latest_basic = _latest_row(daily_basic)
    trade_date = str(_row_value(latest_daily, "trade_date"))
    trade_date_human = f"{trade_date[0:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
    return trade_date_human, {
        "close": float(_row_value(latest_daily, "close")),
        "pct_chg": float(_row_value(latest_daily, "pct_chg")),
        "pe_ttm": float(_row_value(latest_basic, "pe_ttm")),
        "pb": float(_row_value(latest_basic, "pb")),
        "turnover_rate": float(_row_value(latest_basic, "turnover_rate")),
        "total_mv_billion": float(_row_value(latest_basic, "total_mv")) / 10000,
    }


def _trend_sentence(metric_name: str, values: list[float], period: str) -> str:
    """根据首尾变化生成趋势卡片的一句话说明。"""
    if len(values) < 2:
        return f"{period}样本不足，暂不做趋势判断。"
    start = values[0]
    end = values[-1]
    if start == 0:
        return f"{period}样本起点为零，当前仅展示走势，不做幅度判断。"
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
    return f"{metric_name}{period}{direction}，最新值为{end:.2f}。"


def _merge_rows(daily_rows: Any, basic_rows: Any) -> list[dict[str, Any]]:
    """按 ts_code + trade_date 合并行情和基础指标数据。"""
    if _is_dataframe(daily_rows):
        merged = daily_rows.merge(basic_rows, on=["ts_code", "trade_date"], how="inner")
        if merged.empty:
            return []
        return merged.sort_values("trade_date", ascending=True).tail(20).to_dict("records")

    basic_map = {(str(row["ts_code"]), str(row["trade_date"])): row for row in basic_rows}
    merged_rows: list[dict[str, Any]] = []
    for daily in daily_rows:
        key = (str(daily["ts_code"]), str(daily["trade_date"]))
        basic = basic_map.get(key)
        if not basic:
            continue
        merged_rows.append({**daily, **basic})
    return sorted(merged_rows, key=lambda row: str(row["trade_date"]))[-20:]


def build_stock_trend_metrics(daily_rows: Any, basic_rows: Any) -> list[dict[str, Any]]:
    """构造日报当前使用的个股趋势卡片数据。"""
    merged = _merge_rows(daily_rows, basic_rows)
    if not merged:
        return []

    def series(column: str, scale: float = 1.0) -> list[float]:
        """从合并行中提取数值序列。"""
        return [float(row[column]) * scale for row in merged if row.get(column) is not None]

    def latest(column: str, scale: float = 1.0, suffix: str = "") -> str:
        """格式化某个指标的最新值。"""
        values = series(column, scale=scale)
        if not values:
            return "-"
        value = values[-1]
        if suffix == "%":
            return f"{value:.3f}%"
        if suffix == "元":
            return f"{value:.2f} 元"
        if suffix == "倍":
            return f"{value:.2f} 倍"
        if suffix == "亿元":
            return f"{value:.2f} 亿元"
        return f"{value:.2f}"

    return [
        {
            "name": "收盘价",
            "period": "近20交易日",
            "latest": latest("close", suffix="元"),
            "values": series("close"),
            "explanation": _trend_sentence("收盘价", series("close"), "近20个交易日"),
            "stroke": "#2563eb",
        },
        {
            "name": "PE(TTM)",
            "period": "近20交易日",
            "latest": latest("pe_ttm", suffix="倍"),
            "values": series("pe_ttm"),
            "explanation": _trend_sentence("PE(TTM)", series("pe_ttm"), "近20个交易日"),
            "stroke": "#7c3aed",
        },
        {
            "name": "PB",
            "period": "近20交易日",
            "latest": latest("pb", suffix="倍"),
            "values": series("pb"),
            "explanation": _trend_sentence("PB", series("pb"), "近20个交易日"),
            "stroke": "#059669",
        },
        {
            "name": "换手率",
            "period": "近20交易日",
            "latest": latest("turnover_rate", suffix="%"),
            "values": series("turnover_rate"),
            "explanation": _trend_sentence("换手率", series("turnover_rate"), "近20个交易日"),
            "stroke": "#ea580c",
        },
        {
            "name": "总市值",
            "period": "近20交易日",
            "latest": latest("total_mv", scale=1 / 10000, suffix="亿元"),
            "values": series("total_mv", scale=1 / 10000),
            "explanation": _trend_sentence("总市值", series("total_mv", scale=1 / 10000), "近20个交易日"),
            "stroke": "#0f766e",
        },
    ]


def get_tushare_snapshot(
    *,
    token: str,
    ts_code: str,
    as_of_date: str | None = None,
    lookback_days: int = 180,
) -> tuple[str, dict[str, float]]:
    """获取指定标的的 Tushare 最新交易日快照。"""
    daily, daily_basic = load_tushare_history(
        token,
        ts_code=ts_code,
        as_of_date=as_of_date,
        lookback_days=lookback_days,
    )
    return build_stock_snapshot(daily, daily_basic)


def get_tushare_trend_metrics(
    *,
    token: str,
    ts_code: str,
    as_of_date: str | None = None,
    lookback_days: int = 180,
) -> list[dict[str, Any]]:
    """获取指定标的的 Tushare 趋势指标。"""
    daily, daily_basic = load_tushare_history(
        token,
        ts_code=ts_code,
        as_of_date=as_of_date,
        lookback_days=lookback_days,
    )
    return build_stock_trend_metrics(daily, daily_basic)


def _extract_number(text: str, pattern: str) -> float | None:
    """从文本中按正则提取数字。"""
    match = re.search(pattern, text)
    if not match:
        return None
    return float(match.group(1))


def parse_eastmoney_stdout(stdout: str) -> dict[str, float] | None:
    """解析东方财富 mx-data 表格输出，不绑定具体股票名称。"""
    lines = stdout.splitlines()
    header_line = None
    row_index = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("| date |"):
            header_line = stripped
            row_index = index + 2
            break
    if header_line is None:
        return None

    headers = [part.strip() for part in header_line.strip("|").split("|")]
    try:
        total_mv_index = headers.index("总市值")
    except ValueError:
        total_mv_index = headers.index("总市值(证监会算法)") if "总市值(证监会算法)" in headers else -1
    pe_index = headers.index("市盈率PE(TTM)") if "市盈率PE(TTM)" in headers else -1
    turnover_index = headers.index("换手率") if "换手率" in headers else -1
    if min(total_mv_index, pe_index, turnover_index) < 0:
        return None

    for line in lines[row_index:]:
        stripped = line.strip()
        if not stripped.startswith("| 20"):
            continue
        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if len(parts) <= max(total_mv_index, pe_index, turnover_index):
            continue
        total_mv = _extract_number(parts[total_mv_index], r"([0-9.]+)亿")
        pe_ttm = _extract_number(parts[pe_index], r"([0-9.]+)倍")
        turnover = _extract_number(parts[turnover_index], r"([0-9.]+)%")
        if total_mv is None or pe_ttm is None or turnover is None:
            continue
        return {
            "total_mv_billion": total_mv,
            "pe_ttm": pe_ttm,
            "turnover_rate": turnover,
        }
    return None


def get_eastmoney_snapshot(
    *,
    stock_name: str = "牧原股份",
    stock_code: str = "002714",
    skill_script: Path | None = None,
) -> dict[str, float] | None:
    """调用东方财富 mx-data skill 获取个股校验数据。"""
    if skill_script is not None:
        script = skill_script
    else:
        repo_root = Path(__file__).resolve().parents[3]
        repo_skill_script = repo_root / "skills" / "released" / "mx-data" / "mx_data.py"
        home_skill_script = Path.home() / ".codex" / "skills" / "mx-data" / "mx_data.py"
        script = repo_skill_script if repo_skill_script.exists() else home_skill_script
    if not script.exists():
        return None
    result = subprocess.run(
        [sys.executable, str(script), f"{stock_name}{stock_code}最新PE PB 换手率 总市值"],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        cwd=str(script.parent),
    )
    if result.returncode != 0:
        return None
    return parse_eastmoney_stdout(result.stdout)
