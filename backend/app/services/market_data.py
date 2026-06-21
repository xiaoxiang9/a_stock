import asyncio
import csv
import io
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Coroutine

import httpx


VIX_DATA_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
VIX_SOURCE_URL = "https://www.cboe.com/tradable_products/vix/vix_historical_data/"
CNN_DATA_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
CNN_SOURCE_URL = "https://www.cnn.com/markets/fear-and-greed"
NASDAQ_DATA_URL = "https://api.nasdaq.com/api/quote/QQQ/historical"
NASDAQ_SOURCE_URL = "https://www.nasdaq.com/market-activity/etf/qqq/historical"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

CACHE_TTL_SECONDS = 300
_cache: dict[str, Any] = {"expires_at": 0.0, "payload": None}
_cache_lock = asyncio.Lock()


def _round(value: float) -> float:
    return round(value, 2)


def _one_month_trend(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not points:
        return []
    newest = date.fromisoformat(points[-1]["date"])
    cutoff = newest - timedelta(days=31)
    return [point for point in points if date.fromisoformat(point["date"]) >= cutoff]


async def _fetch_vix(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get(VIX_DATA_URL, headers={"Accept": "text/csv,*/*"})
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
        "trend": _one_month_trend(points),
        "methodology": "最新官方日线收盘值",
        "source": {
            "name": "Cboe Global Markets",
            "url": VIX_SOURCE_URL,
        },
    }


async def _fetch_cnn(client: httpx.AsyncClient) -> dict[str, Any]:
    headers = {
        **REQUEST_HEADERS,
        "Origin": "https://www.cnn.com",
        "Referer": "https://www.cnn.com/",
    }
    response = await client.get(CNN_DATA_URL, headers=headers)
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
        "trend": _one_month_trend(points),
        "methodology": f"CNN 综合情绪评分 · {current.get('rating', '').replace('_', ' ').title()}",
        "source": {
            "name": "CNN Business",
            "url": CNN_SOURCE_URL,
        },
    }


def _calculate_wilder_rsi(closes: list[dict[str, Any]], period: int = 14) -> list[dict[str, Any]]:
    if len(closes) <= period:
        raise ValueError("QQQ 收盘数据不足以计算 RSI(14)")

    changes = [closes[index]["close"] - closes[index - 1]["close"] for index in range(1, len(closes))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period

    def rsi_value() -> float:
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
        "Referer": NASDAQ_SOURCE_URL,
    }
    response = await client.get(NASDAQ_DATA_URL, params=params, headers=headers)
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
        "trend": _one_month_trend(rsi_points),
        "methodology": "基于 Nasdaq 日收盘价计算 RSI(14)，Wilder 平滑",
        "source": {
            "name": "Nasdaq",
            "url": NASDAQ_SOURCE_URL,
        },
    }


def _unavailable_indicator(key: str, error: Exception) -> dict[str, Any]:
    labels = {
        "vix": ("VIX", "CBOE 波动率指数", 28, ">", "Cboe Global Markets", VIX_SOURCE_URL),
        "cnn": ("CNN", "Fear & Greed Index", 18, "<", "CNN Business", CNN_SOURCE_URL),
        "qqq_rsi": ("QQQ RSI", "Invesco QQQ · 14 日", 12, "<", "Nasdaq", NASDAQ_SOURCE_URL),
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
    try:
        return await fetcher(client)
    except Exception as error:
        return _unavailable_indicator(key, error)


async def _build_payload() -> dict[str, Any]:
    timeout = httpx.Timeout(20.0, connect=10.0)
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
