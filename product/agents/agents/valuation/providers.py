"""估值 Agent 的外部证据提供方。

职责：
- 将 Tushare、AkShare、妙想和联网搜索封装为独立 provider。
- 只做证据采集和格式化，不做估值判断。
- 允许在后续阶段继续增加新的证据源，不影响调度逻辑。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import select
import shutil
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from product.agents.config.agents_config import load_agents_config
from product.agents.config.private_config import load_private_agents_config
from product.data.adapters.mx_skills import query_mx_finance_news_summary, query_mx_finance_snapshot

from .schemas import ValuationDataNeed, ValuationEvidenceItem, ValuationRequest


MX_QUERY_URL = "https://mkapi2.dfcfs.com/finskillshub/api/claw/query"
MX_NEWS_SEARCH_URL = "https://mkapi2.dfcfs.com/finskillshub/api/claw/news-search"
HOG_SPOT_SOURCE_NAME = "AkShare spot_hog_year_trend_soozhu()"
HOG_FUTURES_SOURCE_NAME = 'AkShare futures_main_sina("LH0")'
HOG_BASIS_SOURCE_NAME = "现货价 - 期货价（均换算为元/公斤）"
TON_TO_KG = 1000.0


def _clean_text(value: Any) -> str:
    """把任意值清洗为非空字符串。"""
    return str(value).strip() if value is not None else ""


def _parse_date(date_text: str) -> datetime:
    """把 YYYY-MM-DD 解析为日期对象。"""
    return datetime.strptime(date_text, "%Y-%m-%d")


def _yyyymmdd(date_text: str) -> str:
    """把 YYYY-MM-DD 转为 YYYYMMDD。"""
    return date_text.replace("-", "")


def _human_date(date_text: str) -> str:
    """把 YYYYMMDD 转为 YYYY-MM-DD。"""
    return f"{date_text[0:4]}-{date_text[4:6]}-{date_text[6:8]}"


def _load_tushare_token() -> str:
    """优先从 agents 私密配置和环境变量读取 Tushare token。"""
    try:
        private_config = load_private_agents_config()
        token = _clean_text(private_config.secrets.get("tushare_token"))
        if token:
            return token
    except Exception:
        pass
    return _clean_text(os.getenv("TUSHARE_TOKEN")) or _clean_text(os.getenv("TS_TOKEN"))


def _load_mx_api_key() -> str:
    """优先从 agents 私密配置和环境变量读取妙想 API Key。"""
    try:
        private_config = load_private_agents_config()
        api_key = _clean_text(private_config.secrets.get("mx_api_key"))
        if api_key:
            return api_key
    except Exception:
        pass
    return _clean_text(os.getenv("MX_APIKEY"))


def _load_websearch_api_key(api_key_env: str = "DEEPSEEK_API_KEY") -> str:
    """优先从 agents 私密配置和环境变量读取 websearch-deepseek 的 API Key。"""
    try:
        private_config = load_private_agents_config()
        api_key = _clean_text(
            private_config.secrets.get("websearch_api_key") or private_config.secrets.get("deepseek_api_key")
        )
        if api_key:
            return api_key
    except Exception:
        pass
    return _clean_text(os.getenv("WEBSEARCH_API_KEY")) or _clean_text(os.getenv(api_key_env)) or _clean_text(
        os.getenv("DEEPSEEK_API_KEY")
    )


def _load_websearch_config() -> dict[str, Any]:
    """读取 agents 子系统里的 websearch 配置。"""
    try:
        config = load_agents_config()
        return {
            "enabled": config.search.websearch_enabled,
            "command": _clean_text(config.search.websearch_command) or "websearch-deepseek",
            "api_key_env": _clean_text(config.search.websearch_api_key_env) or "DEEPSEEK_API_KEY",
            "model": _clean_text(config.search.websearch_model) or "deepseek-v4-flash",
            "thinking": _clean_text(config.search.websearch_thinking) or "enabled",
            "max_tokens": config.search.websearch_max_tokens,
            "timeout_seconds": config.search.websearch_timeout_seconds,
        }
    except Exception:
        return {
            "enabled": True,
            "command": "websearch-deepseek",
            "api_key_env": "DEEPSEEK_API_KEY",
            "model": "deepseek-v4-flash",
            "thinking": "enabled",
            "max_tokens": 32768,
            "timeout_seconds": 90,
        }


def _load_akshare_module() -> Any | None:
    """加载 AkShare 模块，缺失时返回 None。"""
    try:
        import akshare as ak  # type: ignore

        return ak
    except Exception:
        return None


def _pick_first_present(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """按候选字段顺序取第一个非空值。"""
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return None


def _to_records(value: Any) -> list[dict[str, Any]]:
    """把 AkShare 返回值归一成普通字典行。"""
    if hasattr(value, "to_dict"):
        return list(value.to_dict("records"))
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    return []


def _sort_desc_by_date(rows: list[dict[str, Any]], *date_keys: str) -> list[dict[str, Any]]:
    """按候选日期字段倒序排列。"""
    def _date_value(row: dict[str, Any]) -> str:
        raw = _pick_first_present(row, date_keys)
        text = _clean_text(raw)
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            return text
        if len(text) == 8 and text.isdigit():
            return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
        return text

    return sorted(rows, key=_date_value, reverse=True)


def _humanize_date(value: str) -> str:
    """把 YYYYMMDD 或 YYYY-MM-DD 归一为 YYYY-MM-DD。"""
    text = _clean_text(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10]


def _extract_hog_cycle_points() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """从 AkShare 拉取生猪现货和期货主连数据。"""
    ak = _load_akshare_module()
    if ak is None:
        return [], []
    try:
        spot_df = ak.spot_hog_year_trend_soozhu()
        futures_df = ak.futures_main_sina(symbol="LH0")
    except Exception:
        return [], []
    spot_rows = _sort_desc_by_date(_to_records(spot_df), "日期", "date")
    futures_rows = _sort_desc_by_date(_to_records(futures_df), "日期", "date")
    spot_points: list[dict[str, Any]] = []
    futures_points: list[dict[str, Any]] = []
    for row in spot_rows:
        day = _humanize_date(str(_pick_first_present(row, ("日期", "date")) or ""))
        value = _pick_first_present(row, ("价格", "price", "收盘价", "close"))
        if day and value not in (None, ""):
            try:
                spot_points.append({"date": day, "value": round(float(value), 2)})
            except Exception:
                continue
    for row in futures_rows:
        day = _humanize_date(str(_pick_first_present(row, ("日期", "date")) or ""))
        value = _pick_first_present(row, ("动态结算价", "settle", "收盘价", "close"))
        if day and value not in (None, ""):
            try:
                futures_points.append({"date": day, "value": round(float(value), 2)})
            except Exception:
                continue
    spot_points.sort(key=lambda item: str(item["date"]))
    futures_points.sort(key=lambda item: str(item["date"]))
    return spot_points, futures_points


def _extract_stock_history_points(symbol: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    """从 AkShare 拉取个股历史行情。"""
    ak = _load_akshare_module()
    if ak is None:
        return []
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
    except Exception:
        return []
    rows = _sort_desc_by_date(_to_records(df), "日期", "date", "trade_date")
    points: list[dict[str, Any]] = []
    for row in rows:
        day = _humanize_date(str(_pick_first_present(row, ("日期", "date", "trade_date")) or ""))
        close = _pick_first_present(row, ("收盘", "close"))
        pct = _pick_first_present(row, ("涨跌幅", "pct_chg"))
        if not day or close in (None, ""):
            continue
        try:
            points.append(
                {
                    "date": day,
                    "close": round(float(close), 2),
                    "pct_chg": round(float(pct), 2) if pct not in (None, "") else None,
                }
            )
        except Exception:
            continue
    points.sort(key=lambda item: str(item["date"]))
    return points


def _extract_stock_individual_info(symbol: str) -> dict[str, str]:
    """从 AkShare 拉取个股概览信息。"""
    ak = _load_akshare_module()
    if ak is None:
        return {}
    try:
        df = ak.stock_individual_info_em(symbol=symbol)
    except Exception:
        return {}
    rows = _to_records(df)
    info: dict[str, str] = {}
    for row in rows:
        item = _clean_text(row.get("item") or row.get("项目") or row.get("名称"))
        value = _clean_text(row.get("value") or row.get("值"))
        if item and value:
            info[item] = value
    return info


def _build_query_symbol(request: ValuationRequest) -> str:
    """构造妙想查询关键词。"""
    code = request.symbol.split(".")[0]
    return f"{request.company_name}{code}最新PE PB 换手率 总市值 公司简介"


@lru_cache(maxsize=8)
def _load_tushare_history(
    token: str,
    *,
    ts_code: str,
    start_date: str,
    end_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """通过 Tushare 读取个股行情和基础指标。"""
    import tushare as ts  # type: ignore

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
    daily_rows = daily.to_dict("records") if hasattr(daily, "to_dict") else list(daily)
    basic_rows = daily_basic.to_dict("records") if hasattr(daily_basic, "to_dict") else list(daily_basic)
    daily_rows = sorted(daily_rows, key=lambda row: str(row["trade_date"]), reverse=True)
    basic_rows = sorted(basic_rows, key=lambda row: str(row["trade_date"]), reverse=True)
    return daily_rows, basic_rows


def _build_tushare_snapshot(
    daily_rows: list[dict[str, Any]],
    basic_rows: list[dict[str, Any]],
) -> tuple[str, dict[str, float]]:
    """基于 Tushare 行情和基础指标构造快照。"""
    if not daily_rows or not basic_rows:
        raise RuntimeError("No stock data returned.")
    latest_daily = daily_rows[0]
    latest_basic = basic_rows[0]
    trade_date = _human_date(str(latest_daily["trade_date"]))
    return trade_date, {
        "close": float(latest_daily["close"]),
        "pct_chg": float(latest_daily["pct_chg"]),
        "pe_ttm": float(latest_basic["pe_ttm"]),
        "pb": float(latest_basic["pb"]),
        "turnover_rate": float(latest_basic["turnover_rate"]),
        "total_mv_billion": float(latest_basic["total_mv"]) / 10000,
    }


def _query_mx_api(url: str, api_key: str, query: str) -> dict[str, Any]:
    """直接调用妙想金融数据 API。"""
    request = urllib.request.Request(
        url,
        data=json.dumps({"toolQuery": query}, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "apikey": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8", errors="replace")
    return json.loads(payload)


def _extract_mx_evidence_lines(result: dict[str, Any], limit: int = 3) -> list[str]:
    """从妙想返回结果中提取简短证据行。"""
    lines: list[str] = []
    try:
        dto_list = result["data"]["data"]["searchDataResultDTO"]["dataTableDTOList"]
    except Exception:
        dto_list = []
    if not isinstance(dto_list, list):
        return lines
    for dto in dto_list[:limit]:
        if not isinstance(dto, dict):
            continue
        title = _clean_text(dto.get("title") or dto.get("inputTitle") or dto.get("entityName") or "妙想证据")
        condition = _clean_text(dto.get("condition"))
        lines.append(f"{title}｜{condition}" if condition else title)
    return lines


def _extract_mx_search_lines(result: dict[str, Any], limit: int = 3) -> list[dict[str, str]]:
    """从妙想资讯搜索返回结果中提取证据行。"""
    items: list[dict[str, str]] = []
    try:
        llm_data = result["data"]["data"]["llmSearchResponse"]["data"]
    except Exception:
        llm_data = []
    if not isinstance(llm_data, list):
        return items
    for item in llm_data[:limit]:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title") or "妙想资讯")
        content = _clean_text(item.get("content") or item.get("summary") or item.get("trunk") or title)
        source = _clean_text(item.get("insName") or item.get("informationType") or "东方财富妙想 mx-search")
        date = _clean_text(item.get("date") or "")
        if len(date) >= 10:
            date = date[:10]
        items.append(
            {
                "title": title,
                "content": content,
                "source": source,
                "date": date,
                "url": _clean_text(item.get("url") or item.get("sourceUrl") or ""),
            }
        )
    return items


def _query_mx_news_search(url: str, api_key: str, query: str) -> dict[str, Any]:
    """直接调用妙想资讯搜索 API。"""
    request = urllib.request.Request(
        url,
        data=json.dumps({"query": query}, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "apikey": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8", errors="replace")
    return json.loads(payload)


def _extract_websearch_urls(text: str, limit: int = 3) -> list[dict[str, str]]:
    """从 websearch-deepseek 的返回文本里提取来源链接。"""
    urls: list[dict[str, str]] = []
    marker = text.lower().rfind("### sources")
    source_text = text[marker:] if marker >= 0 else text
    for match in re.finditer(r"\[(?P<title>[^\]]+)\]\((?P<url>[^)]+)\)", source_text):
        title = _clean_text(match.group("title"))
        url = _clean_text(match.group("url"))
        if not title or not url:
            continue
        urls.append({"title": title, "url": url})
        if len(urls) >= limit:
            break
    return urls


def _read_json_rpc_line(proc: subprocess.Popen[str], expected_id: int, timeout_seconds: int) -> dict[str, Any]:
    """从 MCP 进程 stdout 中读取指定 id 的 JSON-RPC 响应。"""
    deadline = time.monotonic() + timeout_seconds
    stdout = proc.stdout
    if stdout is None:
        raise RuntimeError("websearch-deepseek process has no stdout pipe")
    while True:
        if proc.poll() is not None and stdout.closed:
            raise RuntimeError("websearch-deepseek process exited before responding")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("websearch-deepseek response timed out")
        ready, _, _ = select.select([stdout], [], [], remaining)
        if not ready:
            continue
        line = stdout.readline()
        if not line:
            if proc.poll() is not None:
                raise RuntimeError("websearch-deepseek process exited before responding")
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("id") == expected_id:
            return payload


def _send_json_rpc_line(proc: subprocess.Popen[str], payload: dict[str, Any]) -> None:
    """向 MCP 进程写入一条 JSON-RPC 请求。"""
    stdin = proc.stdin
    if stdin is None:
        raise RuntimeError("websearch-deepseek process has no stdin pipe")
    stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    stdin.flush()


def _call_websearch_deepseek(
    *,
    command: str,
    api_key: str,
    model: str,
    thinking: str,
    max_tokens: int,
    timeout_seconds: int,
    query: str,
    explanation: str | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """通过本机 websearch-deepseek MCP Server 发起联网搜索。"""
    env = os.environ.copy()
    env["DEEPSEEK_API_KEY"] = api_key
    env["WEBSEARCH_MODEL"] = model
    env["WEBSEARCH_THINKING"] = thinking
    env["WEBSEARCH_MAX_TOKENS"] = str(max_tokens)
    proc = subprocess.Popen(
        [command],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
    )
    try:
        _send_json_rpc_line(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {"name": "a_stock-agents", "version": "1.0.0"},
                    "capabilities": {},
                },
            },
        )
        _read_json_rpc_line(proc, expected_id=1, timeout_seconds=timeout_seconds)
        tool_arguments: dict[str, Any] = {"query": query}
        if explanation:
            tool_arguments["explanation"] = explanation
        _send_json_rpc_line(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "web_search",
                    "arguments": tool_arguments,
                },
            },
        )
        response = _read_json_rpc_line(proc, expected_id=2, timeout_seconds=timeout_seconds)
        if response.get("error"):
            raise RuntimeError(str(response["error"]))
        result = response.get("result") or {}
        content = result.get("content") or []
        text_blocks: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = _clean_text(block.get("text"))
                if text:
                    text_blocks.append(text)
        text = "\n\n".join(text_blocks).strip()
        return text, _extract_websearch_urls(text, limit=3)
    finally:
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class EvidenceProvider(Protocol):
    """外部证据提供方协议。"""

    name: str

    def fetch(self, request: ValuationRequest, need: ValuationDataNeed) -> list[ValuationEvidenceItem]: ...


@dataclass(frozen=True)
class TushareEvidenceProvider:
    """Tushare 证据提供方。"""

    token: str
    name: str = "tushare"

    @classmethod
    def from_environment(cls) -> "TushareEvidenceProvider | None":
        """从环境或私密配置构造 provider，缺少 token 则返回 None。"""
        token = _load_tushare_token()
        return cls(token=token) if token else None

    def fetch(self, request: ValuationRequest, need: ValuationDataNeed) -> list[ValuationEvidenceItem]:
        """按诉求补充 Tushare 证据。"""
        if not any(keyword in need.query for keyword in ("PE", "PB", "市值", "换手率", "价格", "估值")):
            return []
        try:
            end_date = request.as_of_date
            start_date = (_parse_date(request.as_of_date) - timedelta(days=180)).strftime("%Y-%m-%d")
            daily_rows, basic_rows = _load_tushare_history(
                self.token,
                ts_code=request.symbol,
                start_date=_yyyymmdd(start_date),
                end_date=_yyyymmdd(end_date),
            )
            trade_date, snapshot = _build_tushare_snapshot(daily_rows, basic_rows)
            return [
                ValuationEvidenceItem(
                    title=f"{need.title}｜Tushare",
                    source="Tushare",
                    date=trade_date,
                    content=(
                        f"收盘价 {snapshot['close']:.2f} 元，PE(TTM) {snapshot['pe_ttm']:.2f} 倍，"
                        f"PB {snapshot['pb']:.3f} 倍，换手率 {snapshot['turnover_rate']:.3f}%，"
                        f"总市值 {snapshot['total_mv_billion']:.2f} 亿元。"
                    ),
                )
            ]
        except Exception:
            return []


@dataclass(frozen=True)
class MxDataEvidenceProvider:
    """妙想金融数据证据提供方。"""

    api_key: str
    mx_query_url: str = MX_QUERY_URL
    name: str = "mx-data"

    @classmethod
    def from_environment(cls) -> "MxDataEvidenceProvider | None":
        """从环境或私密配置构造 provider，缺少 API Key 则返回 None。"""
        api_key = _load_mx_api_key()
        return cls(api_key=api_key) if api_key else None

    def fetch(self, request: ValuationRequest, need: ValuationDataNeed) -> list[ValuationEvidenceItem]:
        """按诉求补充妙想证据。"""
        query = need.query or _build_query_symbol(request)
        try:
            snapshot_result = query_mx_finance_snapshot(query, indicators="PE PB 换手率 总市值")
        except Exception:
            return []
        if not snapshot_result:
            return []

        trade_date, snapshot = snapshot_result
        if not isinstance(snapshot, dict) or not snapshot:
            return []
        content = (
            f"总市值 {snapshot.get('total_mv_billion', 0.0):.2f} 亿元，"
            f"PE(TTM) {snapshot.get('pe_ttm', 0.0):.2f} 倍，"
            f"PB {snapshot.get('pb', 0.0):.3f} 倍，"
            f"换手率 {snapshot.get('turnover_rate', 0.0):.3f}%。"
        )
        return [
            ValuationEvidenceItem(
                title=need.title or "妙想公开证据",
                source="东方财富妙想 mx-data",
                date=trade_date or request.as_of_date,
                content=content,
            )
        ]


@dataclass(frozen=True)
class MxSearchEvidenceProvider:
    """妙想资讯搜索证据提供方。"""

    api_key: str
    mx_news_search_url: str = MX_NEWS_SEARCH_URL
    name: str = "mx-search"

    @classmethod
    def from_environment(cls) -> "MxSearchEvidenceProvider | None":
        """从环境或私密配置构造 provider，缺少 API Key 则返回 None。"""
        api_key = _load_mx_api_key()
        return cls(api_key=api_key) if api_key else None

    def fetch(self, request: ValuationRequest, need: ValuationDataNeed) -> list[ValuationEvidenceItem]:
        """按诉求补充妙想资讯证据。"""
        query = need.query or f"{request.company_name} 最新公告 研报 解读"
        try:
            lines = query_mx_finance_news_summary(query, limit=3)
        except Exception:
            return []
        if not lines:
            return []
        items: list[ValuationEvidenceItem] = []
        for line in lines:
            parts = [part.strip() for part in line.split("｜", 2)]
            if len(parts) == 3:
                date_text, source_text, title_text = parts
            elif len(parts) == 2:
                date_text, title_text = parts
                source_text = "东方财富妙想 mx-search"
            else:
                date_text = request.as_of_date
                source_text = "东方财富妙想 mx-search"
                title_text = line
            items.append(
                ValuationEvidenceItem(
                    title=title_text or need.title or "妙想资讯搜索结果",
                    source=source_text or "东方财富妙想 mx-search",
                    date=date_text or request.as_of_date,
                    content=title_text or line,
                )
            )
        return items


@dataclass(frozen=True)
class AkShareEvidenceProvider:
    """AkShare 证据提供方。"""

    name: str = "akshare"

    @classmethod
    def from_environment(cls) -> "AkShareEvidenceProvider | None":
        """从环境检查 AkShare 是否可用。"""
        return cls() if _load_akshare_module() is not None else None

    def fetch(self, request: ValuationRequest, need: ValuationDataNeed) -> list[ValuationEvidenceItem]:
        """按诉求补充 AkShare 证据。

        这里不做过度裁剪，默认尽量同时返回个股行情、个股概览和生猪周期证据，
        让上层模型自行判断哪些证据更适合当前分析任务。
        """
        query = f"{need.title} {need.query}".strip()
        symbol = request.symbol.split(".")[0]
        items: list[ValuationEvidenceItem] = []
        end_date = _yyyymmdd(request.as_of_date)
        start_date = _yyyymmdd((_parse_date(request.as_of_date) - timedelta(days=120)).strftime("%Y-%m-%d"))
        hog_keywords = ("猪", "生猪", "猪价", "期货", "现货", "基差", "猪周期")
        hog_trigger = any(keyword in query for keyword in hog_keywords) or any(
            keyword in request.company_name for keyword in ("牧原", "温氏", "新希望", "正邦", "天邦", "生猪", "养殖")
        )
        history_points = _extract_stock_history_points(symbol=symbol, start_date=start_date, end_date=end_date)
        if history_points:
            latest = history_points[-1]
            parts = [f"收盘价 {latest['close']:.2f} 元"]
            if latest.get("pct_chg") is not None:
                parts.append(f"涨跌幅 {float(latest['pct_chg']):.2f}%")
            items.append(
                ValuationEvidenceItem(
                    title=f"{request.company_name} AkShare 行情",
                    source="AkShare stock_zh_a_hist",
                    date=str(latest["date"]),
                    content="，".join(parts) + "。",
                )
            )
        stock_info = _extract_stock_individual_info(symbol)
        if stock_info:
            summary_bits = []
            for label in ("总市值", "流通市值", "行业", "上市时间", "总股本", "流通股本"):
                value = stock_info.get(label)
                if value:
                    summary_bits.append(f"{label} {value}")
            if summary_bits:
                items.append(
                    ValuationEvidenceItem(
                        title=f"{request.company_name} AkShare 概览",
                        source="AkShare stock_individual_info_em",
                        date=request.as_of_date,
                        content="；".join(summary_bits) + "。",
                    )
                )
        if hog_trigger:
            spot_points, futures_points = _extract_hog_cycle_points()
            if spot_points:
                latest_spot = spot_points[-1]
                items.append(
                    ValuationEvidenceItem(
                        title="AkShare 生猪现货",
                        source=HOG_SPOT_SOURCE_NAME,
                        date=str(latest_spot["date"]),
                        content=f"现货生猪最新值 {latest_spot['value']:.2f} 元/公斤。",
                    )
                )
            if futures_points:
                latest_futures = futures_points[-1]
                items.append(
                    ValuationEvidenceItem(
                        title="AkShare 生猪期货",
                        source=HOG_FUTURES_SOURCE_NAME,
                        date=str(latest_futures["date"]),
                        content=f"生猪期货主连最新值 {latest_futures['value']:.2f} 元/公斤。",
                    )
                )
            if spot_points and futures_points:
                basis_points: list[dict[str, Any]] = []
                futures_map = {str(point["date"])[:7]: point for point in futures_points}
                for spot_point in spot_points:
                    month = str(spot_point["date"])[:7]
                    futures_point = futures_map.get(month)
                    if not futures_point:
                        continue
                    basis_points.append(
                        {
                            "date": max(str(spot_point["date"]), str(futures_point["date"])),
                            "value": round(float(spot_point["value"]) - float(futures_point["value"]), 2),
                        }
                    )
                if basis_points:
                    latest_basis = basis_points[-1]
                    items.append(
                        ValuationEvidenceItem(
                            title="AkShare 现货基差",
                            source=HOG_BASIS_SOURCE_NAME,
                            date=str(latest_basis["date"]),
                            content=f"现货基差最新值 {latest_basis['value']:.2f} 元/公斤。",
                        )
                    )
        return items


@dataclass(frozen=True)
class WebSearchDeepseekEvidenceProvider:
    """websearch-deepseek 联网搜索证据提供方。"""

    command: str
    api_key: str
    model: str = "deepseek-v4-flash"
    thinking: str = "enabled"
    max_tokens: int = 32768
    timeout_seconds: int = 90
    name: str = "websearch-deepseek"

    @classmethod
    def from_environment(cls) -> "WebSearchDeepseekEvidenceProvider | None":
        """从 agents 配置和环境构造 provider，缺少可执行命令或密钥时返回 None。"""
        config = _load_websearch_config()
        if not config["enabled"]:
            return None
        command = _clean_text(config["command"]) or "websearch-deepseek"
        if not shutil.which(command) and not Path(command).exists():
            return None
        api_key = _load_websearch_api_key(config["api_key_env"])
        if not api_key:
            return None
        return cls(
            command=command,
            api_key=api_key,
            model=_clean_text(config["model"]) or "deepseek-v4-flash",
            thinking=_clean_text(config["thinking"]) or "enabled",
            max_tokens=int(config["max_tokens"]),
            timeout_seconds=int(config["timeout_seconds"]),
        )

    def fetch(self, request: ValuationRequest, need: ValuationDataNeed) -> list[ValuationEvidenceItem]:
        """按诉求补充 DeepSeek 联网搜索证据。"""
        query = need.query or f"{request.company_name} 估值 公告 研报"
        explanation = f"为估值分析补充 {request.company_name} 的实时公开信息。"
        try:
            text, sources = _call_websearch_deepseek(
                command=self.command,
                api_key=self.api_key,
                model=self.model,
                thinking=self.thinking,
                max_tokens=self.max_tokens,
                timeout_seconds=self.timeout_seconds,
                query=query,
                explanation=explanation,
            )
        except Exception:
            return []
        if not text and not sources:
            return []
        first_source = sources[0] if sources else {}
        content = text or query
        if first_source.get("url"):
            content = f"{content}\n\n来源：{first_source['url']}"
        return [
            ValuationEvidenceItem(
                title=need.title or "websearch-deepseek 联网搜索",
                source="websearch-deepseek",
                date=request.as_of_date,
                content=content,
                url=first_source.get("url", ""),
            )
        ]


def build_default_providers() -> list[EvidenceProvider]:
    """构造默认证据提供方列表。"""
    providers: list[EvidenceProvider] = []
    tushare_provider = TushareEvidenceProvider.from_environment()
    if tushare_provider:
        providers.append(tushare_provider)
    akshare_provider = AkShareEvidenceProvider.from_environment()
    if akshare_provider:
        providers.append(akshare_provider)
    mx_provider = MxDataEvidenceProvider.from_environment()
    if mx_provider:
        providers.append(mx_provider)
    mx_search_provider = MxSearchEvidenceProvider.from_environment()
    if mx_search_provider:
        providers.append(mx_search_provider)
    websearch_deepseek_provider = WebSearchDeepseekEvidenceProvider.from_environment()
    if websearch_deepseek_provider:
        providers.append(websearch_deepseek_provider)
    return providers
