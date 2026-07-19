"""公告和经营数据检索能力。

职责：
- 优先调用仓库固化的 `mx-finance-search` 技能获取资讯摘要。
- 在新 skill 不可用时，继续读取本地 mx-search 缓存结果作为兼容兜底。
- 将原始搜索结果压缩为带日期、来源和标题的摘要行。
- 支持按公司名称和关键词参数化查询，避免绑定单一标的。

边界：
- 本文件只做信源摘要，不判断公告影响。
- 个股异动和影响分析由模型根据摘要和结构化数据完成。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from product.data.adapters.mx_skills import query_mx_finance_news_summary

DEFAULT_MX_OUTPUT_DIR = Path.home() / ".openclaw" / "workspace" / "mx_data" / "output"


def summarize_mx_search_output(
    raw: str,
    limit: int = 3,
    title_keywords: list[str] | None = None,
) -> list[str]:
    """把 mx-search 原始输出压缩成“日期｜来源｜标题”摘要。"""
    raw = raw.strip()
    if not raw:
        return []

    def matches_title(title: str) -> bool:
        """判断搜索结果标题是否满足关键词过滤条件。"""
        if not title_keywords:
            return True
        return any(keyword in title for keyword in title_keywords)

    if raw.startswith("{"):
        try:
            payload: Any = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            items = payload.get("data")
            if isinstance(items, list):
                results: list[str] = []
                for item in items[:limit]:
                    if not isinstance(item, dict):
                        continue
                    title = str(item.get("title") or "").strip()
                    if not title or not matches_title(title):
                        continue
                    date = str(item.get("date") or "").strip()
                    source = str(item.get("source") or item.get("informationType") or "来源待识别").strip()
                    if len(date) >= 10:
                        date = date[:10]
                    results.append(f"{date}｜{source}｜{title}")
                if results:
                    return results

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    results: list[str] = []
    index = 0
    while index < len(lines) and len(results) < limit:
        if lines[index].startswith("标题："):
            title = lines[index].split("：", 1)[1].strip()
            if not matches_title(title):
                index += 1
                continue
            source = ""
            date = ""
            for follow in lines[index + 1 : index + 5]:
                if follow.startswith("来源："):
                    source = follow.split("：", 1)[1].strip()
                elif follow.startswith("日期："):
                    date = follow.split("：", 1)[1].strip()
            source = source or "来源待识别"
            date = date or "日期待识别"
            results.append(f"{date}｜{source}｜{title}")
        index += 1
    return results


def _read_text_if_exists(path: Path) -> str | None:
    """读取存在的文本文件，不存在时返回空。"""
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _load_cached_signal_lines(
    filename: str,
    *,
    base_dir: Path = DEFAULT_MX_OUTPUT_DIR,
    limit: int = 3,
    title_keywords: list[str] | None = None,
) -> list[str]:
    """读取指定文件名的本地妙想搜索缓存。"""
    content = _read_text_if_exists(base_dir / filename)
    if not content:
        return []
    return summarize_mx_search_output(content, limit=limit, title_keywords=title_keywords)


def _load_latest_cached_signal_lines(
    patterns: list[str],
    *,
    base_dir: Path = DEFAULT_MX_OUTPUT_DIR,
    limit: int = 3,
    title_keywords: list[str] | None = None,
) -> list[str]:
    """按文件模式读取最近一次缓存结果。"""
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(base_dir.glob(pattern))
    candidates = [path for path in candidates if path.is_file()]
    if not candidates:
        return []
    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    content = _read_text_if_exists(latest)
    if not content:
        return []
    return summarize_mx_search_output(content, limit=limit, title_keywords=title_keywords)


def get_signal_data(
    *,
    company_name: str = "牧原股份",
    base_dir: Path = DEFAULT_MX_OUTPUT_DIR,
) -> dict[str, list[str]]:
    """获取个股公告和月度经营数据摘要。"""
    news_query_announcement = f"{company_name} 最新公告 重大事项"
    news_query_sales = f"{company_name} 销售简报 月度经营数据"
    announcement_lines = query_mx_finance_news_summary(news_query_announcement, limit=3) or _load_latest_cached_signal_lines(
        [f"mx_search_*{company_name}*公告*.txt", f"mx_search_*{company_name}*销售简报*.txt"],
        base_dir=base_dir,
        limit=3,
        title_keywords=["公告", "决议"],
    )
    sales_brief_lines = query_mx_finance_news_summary(news_query_sales, limit=3) or _load_latest_cached_signal_lines(
        [f"mx_search_*{company_name}*销售简报*.txt", f"mx_search_*{company_name}*公告*.txt"],
        base_dir=base_dir,
        limit=3,
        title_keywords=["销售简报", "商品猪销售收入"],
    )
    return {
        "announcements": announcement_lines,
        "sales_brief": sales_brief_lines,
    }
