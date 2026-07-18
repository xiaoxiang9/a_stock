"""海外市场指标数据获取器。

职责：
- 属于数据层，统一负责 VIX、CNN Fear & Greed、QQQ 历史行情等外部市场数据获取。
- 计算 QQQ RSI(14)、阈值偏离度等确定性衍生指标，并输出前端可直接展示的数据结构。
- 维护数据来源、统计口径、缓存和单数据源失败兜底结构。

上下游关系：
- 上游依赖 `product.data.config.data_config` 读取市场数据接口、请求头、超时和缓存配置。
- 下游由后端基础设施层 `product/app/backend/infrastructure/market_data/market_data.py` 兼容导出，
  再提供给 API 页面展示。

职责边界：
- 本文件只做确定性取数、清洗、计算和格式化。
- ETF 是否值得买入的开放式分析不在这里完成；这里只按固定阈值判断规则是否触发。
"""

from __future__ import annotations

import asyncio
import csv
import io
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Coroutine

import httpx

from product.data.config.data_config import load_data_config


DATA_CONFIG = load_data_config()

# 市场数据接口对请求头较敏感，统一从配置读取，便于后续按数据源调整。
REQUEST_HEADERS = {
    "User-Agent": DATA_CONFIG.market_data.request_user_agent,
    "Accept": DATA_CONFIG.market_data.request_accept,
    "Accept-Language": DATA_CONFIG.market_data.request_accept_language,
}

CACHE_TTL_SECONDS = DATA_CONFIG.market_data.cache_ttl_seconds
# 这里使用进程内短缓存：页面多次刷新时不重复打官方接口；
# refresh=true 会绕过缓存，适合人工校验最新数据。
_cache: dict[str, Any] = {"expires_at": 0.0, "payload": None}
_cache_lock = asyncio.Lock()


def _round(value: float) -> float:
    """统一保留两位小数，保证接口展示口径稳定。"""
    return round(value, 2)


def _trigger_deviation(value: float, threshold: float, operator: str) -> float:
    """计算指标距离触发阈值的百分比，正数代表朝触发方向超出阈值。"""
    if operator == ">":
        return _round(((value - threshold) / threshold) * 100)
    return _round(((threshold - value) / threshold) * 100)


def _one_month_trend(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """从时间序列中截取最近约一个月趋势点。"""
    if not points:
        return []
    newest = date.fromisoformat(points[-1]["date"])
    cutoff = newest - timedelta(days=31)
    return [point for point in points if date.fromisoformat(point["date"]) >= cutoff]


async def _fetch_vix(client: httpx.AsyncClient) -> dict[str, Any]:
    """读取 CBOE VIX 官方历史 CSV，并转换成前端统一指标结构。"""
    response = await client.get(
        DATA_CONFIG.market_data.vix_data_url,
        headers={"Accept": "text/csv,*/*"},
    )
    response.raise_for_status()

    points: list[dict[str, Any]] = []
    for row in csv.DictReader(io.StringIO(response.text)):
        if not row.get("DATE") or not row.get("CLOSE"):
            continue
        day = datetime.strptime(row["DATE"], "%m/%d/%Y").date().isoformat()
        points.append({"date": day, "value": _round(float(row["CLOSE"]))})

    if not points:
        raise ValueError("CBOE VIX 数据为空")

    points.sort(key=lambda point: point["date"])
    latest = points[-1]
    return {
        "key": "vix",
        "name": "VIX",
        "subtitle": "CBOE 波动率指数",
        "value": latest["value"],
        "unit": "",
        "updated_at": latest["date"],
        "threshold": 28,
        "operator": ">",
        "met": latest["value"] > 28,
        "deviation_pct": _trigger_deviation(latest["value"], 28, ">"),
        "trend": _one_month_trend(points),
        "methodology": "最新官方日线收盘值",
        "source": {
            "name": "Cboe Global Markets",
            "url": DATA_CONFIG.market_data.vix_source_url,
        },
    }


async def _fetch_cnn(client: httpx.AsyncClient) -> dict[str, Any]:
    """读取 CNN Fear & Greed 数据，作为市场情绪极端恐慌指标。"""
    headers = {
        **REQUEST_HEADERS,
        "Origin": "https://www.cnn.com",
        "Referer": "https://www.cnn.com/",
    }
    response = await client.get(DATA_CONFIG.market_data.cnn_data_url, headers=headers)
    response.raise_for_status()
    payload = response.json()

    current = payload["fear_and_greed"]
    historical = payload["fear_and_greed_historical"]["data"]
    points = [
        {
            "date": datetime.fromtimestamp(item["x"] / 1000, tz=timezone.utc).date().isoformat(),
            "value": _round(float(item["y"])),
        }
        for item in historical
        if item.get("x") is not None and item.get("y") is not None
    ]
    points.sort(key=lambda point: point["date"])

    value = _round(float(current["score"]))
    updated_at = datetime.fromisoformat(current["timestamp"]).date().isoformat()
    return {
        "key": "cnn",
        "name": "CNN",
        "subtitle": "Fear & Greed Index",
        "value": value,
        "unit": "",
        "updated_at": updated_at,
        "threshold": 18,
        "operator": "<",
        "met": value < 18,
        "deviation_pct": _trigger_deviation(value, 18, "<"),
        "trend": _one_month_trend(points),
        "methodology": f"CNN 综合情绪评分 · {current.get('rating', '').replace('_', ' ').title()}",
        "source": {
            "name": "CNN Business",
            "url": DATA_CONFIG.market_data.cnn_source_url,
        },
    }


def _calculate_wilder_rsi(closes: list[dict[str, Any]], period: int = 14) -> list[dict[str, Any]]:
    """按 Wilder 平滑算法计算 RSI，避免依赖外部技术指标库。"""
    if len(closes) <= period:
        raise ValueError("QQQ 收盘数据不足以计算 RSI(14)")

    changes = [closes[index]["close"] - closes[index - 1]["close"] for index in range(1, len(closes))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period

    def rsi_value() -> float:
        """根据当前平均涨跌幅计算 RSI 单点值。"""
        if average_loss == 0:
            return 100.0 if average_gain else 50.0
        relative_strength = average_gain / average_loss
        return 100 - (100 / (1 + relative_strength))

    values = [{"date": closes[period]["date"], "value": _round(rsi_value())}]
    for index in range(period, len(changes)):
        average_gain = ((average_gain * (period - 1)) + gains[index]) / period
        average_loss = ((average_loss * (period - 1)) + losses[index]) / period
        values.append({"date": closes[index + 1]["date"], "value": _round(rsi_value())})
    return values


async def _fetch_qqq_rsi(client: httpx.AsyncClient) -> dict[str, Any]:
    """读取 Nasdaq QQQ 日线并本地计算 RSI(14)。"""
    today = datetime.now(timezone.utc).date()
    params = {
        "assetclass": "etf",
        "fromdate": (today - timedelta(days=100)).isoformat(),
        "todate": today.isoformat(),
        "limit": 5000,
        "offset": 0,
    }
    headers = {
        **REQUEST_HEADERS,
        "Referer": DATA_CONFIG.market_data.nasdaq_source_url,
    }
    response = await client.get(DATA_CONFIG.market_data.nasdaq_data_url, params=params, headers=headers)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status", {}).get("rCode") != 200:
        raise ValueError("Nasdaq QQQ 历史行情返回异常")

    rows = payload["data"]["tradesTable"]["rows"]
    closes = [
        {
            "date": datetime.strptime(row["date"], "%m/%d/%Y").date().isoformat(),
            "close": float(row["close"].replace("$", "").replace(",", "")),
        }
        for row in rows
        if row.get("date") and row.get("close") not in (None, "--")
    ]
    closes.sort(key=lambda point: point["date"])
    rsi_points = _calculate_wilder_rsi(closes)
    latest = rsi_points[-1]
    return {
        "key": "qqq_rsi",
        "name": "QQQ RSI",
        "subtitle": "Invesco QQQ · 14 日",
        "value": latest["value"],
        "unit": "",
        "updated_at": latest["date"],
        "threshold": 12,
        "operator": "<",
        "met": latest["value"] < 12,
        "deviation_pct": _trigger_deviation(latest["value"], 12, "<"),
        "trend": _one_month_trend(rsi_points),
        "methodology": "基于 Nasdaq 日收盘价计算 RSI(14)，Wilder 平滑",
        "source": {
            "name": "Nasdaq",
            "url": DATA_CONFIG.market_data.nasdaq_source_url,
        },
    }


def _unavailable_indicator(key: str, error: Exception) -> dict[str, Any]:
    """构造单个指标不可用时的统一返回结构。"""
    # 单个数据源失败不应拖垮整个页面；用“不可用指标”显式暴露错误和来源。
    labels = {
        "vix": ("VIX", "CBOE 波动率指数", 28, ">", "Cboe Global Markets", DATA_CONFIG.market_data.vix_source_url),
        "cnn": ("CNN", "Fear & Greed Index", 18, "<", "CNN Business", DATA_CONFIG.market_data.cnn_source_url),
        "qqq_rsi": ("QQQ RSI", "Invesco QQQ · 14 日", 12, "<", "Nasdaq", DATA_CONFIG.market_data.nasdaq_source_url),
    }
    name, subtitle, threshold, operator, source_name, source_url = labels[key]
    return {
        "key": key,
        "name": name,
        "subtitle": subtitle,
        "value": None,
        "unit": "",
        "updated_at": None,
        "threshold": threshold,
        "operator": operator,
        "met": False,
        "deviation_pct": None,
        "trend": [],
        "methodology": "官方数据暂不可用",
        "error": str(error),
        "source": {"name": source_name, "url": source_url},
    }


async def _collect_indicator(
    key: str,
    fetcher: Callable[[httpx.AsyncClient], Coroutine[Any, Any, dict[str, Any]]],
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    """拉取单个指标，失败时返回显式不可用结构。"""
    try:
        return await fetcher(client)
    except Exception as error:
        return _unavailable_indicator(key, error)


async def _build_payload() -> dict[str, Any]:
    """并发获取三项指标并组装 ETF 决策接口返回体。"""
    # 三项指标相互独立，并发获取能缩短页面等待时间。
    timeout = httpx.Timeout(
        DATA_CONFIG.market_data.request_timeout_seconds,
        connect=DATA_CONFIG.market_data.connect_timeout_seconds,
    )
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        indicators = await asyncio.gather(
            _collect_indicator("vix", _fetch_vix, client),
            _collect_indicator("cnn", _fetch_cnn, client),
            _collect_indicator("qqq_rsi", _fetch_qqq_rsi, client),
        )

    ready = all(indicator["value"] is not None for indicator in indicators)
    should_buy = ready and all(indicator["met"] for indicator in indicators)
    met_count = sum(1 for indicator in indicators if indicator["met"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": {
            "ready": ready,
            "should_buy": should_buy,
            "label": "满足买入条件" if should_buy else ("暂不买入" if ready else "数据待恢复"),
            "summary": (
                "三项极端恐慌条件同时成立，触发策略买入信号。"
                if should_buy
                else (
                    f"当前满足 {met_count}/3 项条件，尚未触发策略买入信号。"
                    if ready
                    else "部分官方数据暂不可用，当前不生成买入信号。"
                )
            ),
            "rule": "VIX > 28 且 CNN < 18 且 QQQ RSI(14) < 12",
            "met_count": met_count,
            "total_count": 3,
        },
        "indicators": indicators,
        "disclaimer": "本模块仅提供规则化决策支持，不构成投资建议。行情为官方来源可获得的最新日线或指数值。",
    }


async def get_etf_buy_decision(force_refresh: bool = False) -> dict[str, Any]:
    """获取 ETF 买入决策数据。

    该模块是规则型决策支持：代码只计算固定阈值是否满足，
    不做自由发挥式投资判断。
    """
    now = time.monotonic()
    if not force_refresh and _cache["payload"] is not None and now < _cache["expires_at"]:
        return _cache["payload"]

    async with _cache_lock:
        now = time.monotonic()
        if not force_refresh and _cache["payload"] is not None and now < _cache["expires_at"]:
            return _cache["payload"]
        payload = await _build_payload()
        _cache["payload"] = payload
        _cache["expires_at"] = now + CACHE_TTL_SECONDS
        return payload
