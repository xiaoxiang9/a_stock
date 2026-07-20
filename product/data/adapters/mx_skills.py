"""东方财富妙想技能包适配层。

职责：
- 优先从仓库固化的 `skills/released/` 目录加载妙想技能脚本。
- 为 `mx-finance-data` 和 `mx-finance-search` 提供稳定的动态加载入口。
- 将技能包的文件输出转成数据层可消费的结果，避免业务代码直接依赖外部安装态。

边界：
- 这里只负责定位、加载和薄封装，不在这里写具体投研判断。
- 如果仓库副本缺失，才回退到本机安装目录。
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

import pandas as pd

from product.app.backend.infrastructure.config.private_config import load_private_config


ROOT = Path(__file__).resolve().parents[3]


def _candidate_skill_scripts(skill_name: str, script_relpath: str) -> list[Path]:
    """按仓库优先、本机安装态兜底的顺序列出候选脚本路径。"""
    candidates = [
        ROOT / "skills" / "released" / skill_name / script_relpath,
        Path.home() / ".codex" / "skills" / skill_name / script_relpath,
    ]
    return [path for path in candidates if path.exists()]


def _load_module_from_path(module_name: str, script_path: Path) -> ModuleType | None:
    """按文件路径动态加载 Python 模块。"""
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ensure_mx_api_key_env() -> None:
    """把私密配置中的妙想密钥注入进进程环境。

    新版 skill 脚本只读取环境变量，这里负责从仓库内的私密配置托底，
    避免把密钥写进可追踪源码。
    """
    current_key = (os.environ.get("EM_API_KEY") or os.environ.get("MX_APIKEY") or "").strip()
    if current_key:
        return
    try:
        private_config = load_private_config()
    except Exception:
        return
    secrets = dict(private_config.raw.get("secrets", {}))
    api_key = str(secrets.get("mx_api_key") or secrets.get("em_api_key") or "").strip()
    if not api_key:
        return
    os.environ.setdefault("EM_API_KEY", api_key)
    os.environ.setdefault("MX_APIKEY", api_key)


@lru_cache(maxsize=8)
def load_released_skill_module(skill_name: str, script_relpath: str = "scripts/get_data.py") -> ModuleType | None:
    """加载仓库固化的 skill 模块。

    skill_name 统一按 released 目录名传入，例如：
    - `mx-finance-data`
    - `mx-finance-search`
    """
    candidates = _candidate_skill_scripts(skill_name, script_relpath)
    if not candidates:
        return None
    return _load_module_from_path(f"a_stock_{skill_name.replace('-', '_')}", candidates[0])


def _normalize_number(value: Any) -> float | None:
    """从任意单元格值中提取浮点数。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    cleaned = (
        text.replace(",", "")
        .replace("亿元", "")
        .replace("亿", "")
        .replace("倍", "")
        .replace("%", "")
        .replace("元", "")
    )
    for token in cleaned.split():
        try:
            return float(token)
        except ValueError:
            continue
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_trade_date(value: Any) -> str | None:
    """把 xlsx 表头里的日期列名规范为 YYYY-MM-DD。"""
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    if len(text) == 8 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    return None


def extract_mx_finance_snapshot_from_workbook(xlsx_path: Path) -> tuple[str, dict[str, float]] | None:
    """从 `mx-finance-data` 输出的 xlsx 中提取最新快照。

    该 skill 的表格通常是“首列指标名称、后续列为日期”的宽表，
    因此这里取最后一个日期列作为最新值列，再从指标行中抽取目标字段。
    """
    if not xlsx_path.exists():
        return None

    try:
        sheets = pd.read_excel(xlsx_path, sheet_name=None)
    except Exception:
        return None

    trade_date: str | None = None
    snapshot: dict[str, float] = {}
    field_aliases = {
        "pe_ttm": ("市盈率PE(TTM)", "PE(TTM)", "PE_ttm", "pe_ttm"),
        "pb": ("市净率PB", "PB", "pb"),
        "turnover_rate": ("换手率", "turnover_rate", "换手"),
        "total_mv_billion": ("总市值", "总市值(证监会算法)", "market_cap", "总市值（亿元）"),
    }

    for df in sheets.values():
        if df is None or df.empty or len(df.columns) < 2:
            continue

        label_col = df.columns[0]
        latest_col = df.columns[-1]
        if trade_date is None:
            trade_date = _normalize_trade_date(latest_col) or trade_date

        labels = df[label_col].astype(str).str.strip()
        values = df[latest_col]
        value_map = {label: value for label, value in zip(labels, values) if label}

        for field_name, aliases in field_aliases.items():
            if field_name in snapshot:
                continue
            matched_value = None
            for alias in aliases:
                for label, cell_value in value_map.items():
                    if alias in label:
                        matched_value = _normalize_number(cell_value)
                        if matched_value is not None:
                            break
                if matched_value is not None:
                    break
            if matched_value is None:
                continue
            if field_name == "total_mv_billion" and matched_value > 100000:
                matched_value = matched_value / 10000
            snapshot[field_name] = matched_value

        if len(snapshot) == 4:
            break

    if trade_date is None or len(snapshot) < 3:
        return None
    return trade_date, snapshot


def _extract_search_summary_lines(raw_result: Any, *, limit: int = 3) -> list[str]:
    """从 `mx-finance-search` 的返回结果中提取可展示摘要。

    优先读取结构化 JSON 返回；如果只有纯文本，则退化为前几条非空行，
    保留 skill 名称，避免上层摘要失真。
    """
    def _walk_for_items(value: Any) -> list[dict[str, Any]]:
        """递归寻找最像资讯列表的结构化结果。"""
        if isinstance(value, list):
            items = [item for item in value if isinstance(item, dict)]
            if items and any(item.get("title") or item.get("content") for item in items):
                return items
            for item in value:
                nested = _walk_for_items(item)
                if nested:
                    return nested
        if isinstance(value, dict):
            for key in ("llmSearchResponse", "searchResponse", "result", "data"):
                nested_value = value.get(key)
                if nested_value is None:
                    continue
                nested = _walk_for_items(nested_value)
                if nested:
                    return nested
            if value.get("title") or value.get("content"):
                return [value]
        return []

    lines: list[str] = []
    payload: Any = raw_result.get("raw") if isinstance(raw_result, dict) else None
    items = _walk_for_items(payload)
    if items:
        for item in items[:limit]:
            title = str(item.get("title") or item.get("content") or "").strip()
            if not title:
                continue
            date = str(item.get("date") or item.get("publishDate") or "").strip()
            source = str(
                item.get("source")
                or item.get("informationType")
                or item.get("sourceName")
                or "东方财富妙想 mx-finance-search"
            ).strip()
            if len(date) >= 10:
                date = date[:10]
            lines.append(f"{date}｜{source}｜{title}")
        if lines:
            return lines

    content = str(raw_result.get("content") or "").strip() if isinstance(raw_result, dict) else ""
    if content:
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            nested_items = _walk_for_items(parsed)
            if nested_items:
                for item in nested_items[:limit]:
                    title = str(item.get("title") or item.get("content") or "").strip()
                    if not title:
                        continue
                    date = str(item.get("date") or item.get("publishDate") or "").strip()
                    source = str(
                        item.get("source")
                        or item.get("informationType")
                        or item.get("sourceName")
                        or "东方财富妙想 mx-finance-search"
                    ).strip()
                    if len(date) >= 10:
                        date = date[:10]
                    lines.append(f"{date}｜{source}｜{title}")
                if lines:
                    return lines
        for line in content.splitlines():
            text = line.strip()
            if not text or text in {"{", "}", "[", "]"}:
                continue
            lines.append(f"东方财富妙想 mx-finance-search｜{text}")
            if len(lines) >= limit:
                break
    return lines


def query_mx_finance_snapshot(
    query: str,
    *,
    indicators: str | None = None,
) -> tuple[str, dict[str, float]] | None:
    """调用 `mx-finance-data` 技能并提取最新快照。"""
    _ensure_mx_api_key_env()
    module = load_released_skill_module("mx-finance-data")
    if module is None:
        return None

    query_fn = getattr(module, "query_mx_finance_data_direct", None) or getattr(module, "query_mx_finance_data", None)
    if query_fn is None:
        return None

    async def _run_query(output_dir: Path) -> dict[str, Any]:
        return await query_fn(query=query, indicators=indicators, output_dir=output_dir)

    with tempfile.TemporaryDirectory(prefix="a_stock_mx_finance_") as tmpdir:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_run_query(Path(tmpdir)))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    if not isinstance(result, dict):
        return None
    if result.get("error"):
        return None

    xlsx_path_text = result.get("file_path") or result.get("csv_path")
    if not xlsx_path_text:
        return None

    return extract_mx_finance_snapshot_from_workbook(Path(xlsx_path_text))


def query_mx_finance_news_summary(
    query: str,
    *,
    limit: int = 3,
) -> list[str]:
    """调用 `mx-finance-search` 技能并提取摘要行。"""
    _ensure_mx_api_key_env()
    module = load_released_skill_module("mx-finance-search")
    if module is None:
        return []

    query_fn = getattr(module, "query_financial_news", None)
    if query_fn is None:
        return []

    async def _run_query(output_dir: Path) -> dict[str, Any]:
        return await query_fn(query=query, output_dir=output_dir)

    with tempfile.TemporaryDirectory(prefix="a_stock_mx_finance_search_") as tmpdir:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_run_query(Path(tmpdir)))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    if not isinstance(result, dict) or result.get("error"):
        return []
    return _extract_search_summary_lines(result, limit=limit)
