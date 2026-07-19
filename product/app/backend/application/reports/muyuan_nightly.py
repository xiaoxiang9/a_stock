#!/usr/bin/env python3

"""牧原股份夜间复盘任务。

职责：
- 获取 Tushare 主数据、东方财富校验数据和公告/销售简报等信号。
- 组装模型分析上下文，调用统一模型服务生成当前状态和个股异动。
- 渲染 Markdown 报告、HTML 邮件，并通过仓库内私密配置发送。
- 支持生成 macOS launchd 定时任务配置。

边界：
- 本文件负责数据流转、任务编排、格式化渲染和发送。
- 当前状态、个股异动、异动影响等投研判断必须由模型生成。
- 代码只做结构校验和展示清洗，不用规则硬编码替代分析。
"""

from __future__ import annotations

import asyncio
import argparse
import inspect
import json
import os
import subprocess
import sys
import uuid
import smtplib
from html import escape as html_escape
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from product.app.backend.infrastructure.model_service import ModelService, build_codex_exec_command as _build_codex_exec_command
from product.app.backend.infrastructure.config.private_config import load_private_config
from product.app.backend.infrastructure.config.project_config import ModelRuntimeConfig, load_project_config
from product.agents.agents.valuation import (
    ValuationAgent,
    ValuationEvidenceItem,
    ValuationRequest,
    ValuationResult,
    ValuationResearchCoordinator,
)
from product.data.fetchers.hog_cycle import get_hog_cycle_metrics, render_hog_cycle_lines
from product.data.fetchers.signals import get_signal_data, summarize_mx_search_output
from product.data.fetchers.stock import (
    get_eastmoney_snapshot,
    get_tushare_snapshot,
    get_tushare_trend_metrics,
    parse_eastmoney_stdout,
)

PROJECT_CONFIG = load_project_config()
REPORT_DIR = ROOT / PROJECT_CONFIG.report.output_dir
DEFAULT_RECIPIENT = PROJECT_CONFIG.email.recipient
DEFAULT_LABEL = PROJECT_CONFIG.launchd.label
DEFAULT_HOUR = PROJECT_CONFIG.launchd.hour
DEFAULT_MINUTE = PROJECT_CONFIG.launchd.minute


def _report_clock_label() -> str:
    """返回日报文案中统一使用的执行时间。"""
    return f"{PROJECT_CONFIG.launchd.hour:02d}:{PROJECT_CONFIG.launchd.minute:02d}"


def build_email_subject(report_date: str) -> str:
    """生成邮件主题，保持日报邮件可按日期检索。"""
    return f"牧原股份 {report_date} {_report_clock_label()} 日复盘"


def _render_signal_lines(lines: list[str], fallback: str) -> str:
    """把信号摘要列表渲染为 Markdown 列表。"""
    if not lines:
        return fallback
    return "\n".join([f"- {line}" for line in lines])


def extract_report_summary(markdown_body: str) -> dict[str, str]:
    """从 Markdown 正文提取头部摘要。

    兼容早期纯 Markdown 邮件；当前主要摘要来自模型分析结果。
    """
    summary = {
        "conclusion": "未提取到一句话结论",
        "status": "未提取",
        "changed": "未提取",
        "reason": "未提取到变化原因",
    }
    for raw_line in markdown_body.splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or "：" not in line:
            continue
        label, value = line[2:].split("：", 1)
        label = label.strip()
        value = value.strip()
        if label == "一句话结论":
            summary["conclusion"] = value
        elif label == "当前状态":
            summary["status"] = value
        elif label == "是否较昨日变化":
            summary["changed"] = value
        elif label == "变化原因":
            summary["reason"] = value
    return summary


def build_sparkline_svg(
    values: list[float],
    *,
    width: int = 180,
    height: int = 56,
    stroke: str = "#0f172a",
    fill: str = "none",
) -> str:
    """生成邮件内联折线图 SVG。

    邮件客户端对外部脚本支持弱，因此趋势图直接内嵌为静态 SVG。
    """
    chart_width = max(width - 8, 1)
    chart_height = max(height - 8, 1)
    padding = 4
    if not values:
        return (
            f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="空趋势图">'
            f'<rect x="0" y="0" width="{width}" height="{height}" rx="8" fill="#f8fafc" stroke="#e5e7eb"/>'
            f'<line x1="{padding}" y1="{height / 2:.1f}" x2="{width - padding}" y2="{height / 2:.1f}" '
            f'stroke="{stroke}" stroke-width="1.5" stroke-dasharray="3 3" opacity="0.35"/>'
            "</svg>"
        )

    if len(values) == 1:
        points = [(padding, height / 2)]
    else:
        min_value = min(values)
        max_value = max(values)
        value_span = max(max_value - min_value, 1e-9)
        step = chart_width / (len(values) - 1)
        points = []
        for index, value in enumerate(values):
            x = padding + index * step
            y_ratio = (value - min_value) / value_span
            y = padding + (1 - y_ratio) * chart_height
            points.append((x, y))

    points_str = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    baseline_y = height - padding
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        'xmlns="http://www.w3.org/2000/svg" role="img">'
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="8" fill="#f8fafc" stroke="#e5e7eb"/>'
        f'<line x1="{padding}" y1="{baseline_y:.1f}" x2="{width - padding}" y2="{baseline_y:.1f}" '
        'stroke="#e5e7eb" stroke-width="1"/>'
        f'<polyline points="{points_str}" fill="{fill}" stroke="{stroke}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg>"
    )


def _trend_sentence(metric_name: str, values: list[float], period: str) -> str:
    """根据数值首尾变化生成趋势说明。

    该说明仅用于趋势卡片辅助展示，不替代模型对异动影响的判断。
    """
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


def render_metric_trend_cards(trend_metrics: list[dict[str, Any]] | None) -> str:
    """把关键指标转换成 HTML 趋势卡片。"""
    if not trend_metrics:
        return (
            "<p style=\"margin:0;color:#6b7280;\">"
            "当前暂无趋势数据，后续会按指标特性补齐折线图。"
            "</p>"
        )

    cards = []
    for metric in trend_metrics:
        name = str(metric.get("name", "指标"))
        period = str(metric.get("period", ""))
        latest = str(metric.get("latest", "-"))
        explanation = str(metric.get("explanation", ""))
        source = metric.get("source", {}) or {}
        source_name = str(source.get("name", ""))
        updated_at = str(metric.get("updated_at", ""))
        values = [float(value) for value in metric.get("values", [])]
        svg = build_sparkline_svg(values, stroke=str(metric.get("stroke", "#0f172a")))
        cards.append(
            "<div style=\"flex:1 1 260px;border:1px solid #e5e7eb;border-radius:14px;"
            "padding:16px 16px 14px;background:#ffffff;box-shadow:0 1px 2px rgba(15,23,42,0.04);\">"
            f"<div style=\"display:flex;justify-content:space-between;gap:12px;align-items:baseline;\">"
            f"<div style=\"font-size:15px;font-weight:700;color:#0f172a;\">{html_escape(name)}</div>"
            f"<div style=\"font-size:12px;color:#64748b;\">{html_escape(period)}</div>"
            "</div>"
            f"<div style=\"font-size:22px;font-weight:700;margin:10px 0 8px;color:#111827;\">{html_escape(latest)}</div>"
            f"<div style=\"margin:6px 0 10px;\">{svg}</div>"
            f"<div style=\"font-size:13px;line-height:1.6;color:#334155;\">{html_escape(explanation)}</div>"
            f"<div style=\"font-size:12px;line-height:1.6;color:#64748b;margin-top:8px;\">"
            f"来源：{html_escape(source_name)}"
            f"{'｜最新日期：' + html_escape(updated_at) if updated_at else ''}"
            "</div>"
            "</div>"
        )

    return (
        "<div style=\"display:flex;flex-wrap:wrap;gap:14px;\">"
        + "".join(cards)
        + "</div>"
    )


def build_report_context(
    report_date: str,
    latest_trade_date: str,
    tushare_data: dict[str, float],
    eastmoney_data: dict[str, float] | None,
    signal_data: dict[str, list[str]] | None,
    trend_metrics: list[dict[str, Any]] | None,
    pig_cycle_metrics: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """组装模型分析上下文。

    代码只做数据流转，不在这里硬编码“异动名称”或投资判断。
    """
    return {
        "report_date": report_date,
        "latest_trade_date": latest_trade_date,
        "tushare_snapshot": tushare_data,
        "eastmoney_snapshot": eastmoney_data,
        "signals": signal_data or {},
        "trend_metrics": trend_metrics or [],
        "pig_cycle_metrics": pig_cycle_metrics or [],
    }


def build_valuation_request(
    report_date: str,
    latest_trade_date: str,
    tushare_data: dict[str, float],
    eastmoney_data: dict[str, float] | None,
    signal_data: dict[str, list[str]] | None,
    trend_metrics: list[dict[str, Any]] | None,
    pig_cycle_metrics: list[dict[str, Any]] | None,
) -> ValuationRequest:
    """组装估值 Agent 的请求对象。

    该请求只封装当前日报已经拿到的确定性数据和证据摘要，
    不在这里向 data 层发起新的取数。
    """
    evidence_items: list[ValuationEvidenceItem] = [
        ValuationEvidenceItem(
            title="价格与估值快照",
            source="Tushare",
            date=latest_trade_date,
            content=(
                f"收盘价 {tushare_data['close']:.2f} 元，PE(TTM) {tushare_data['pe_ttm']:.2f} 倍，"
                f"PB {tushare_data['pb']:.3f} 倍，换手率 {tushare_data['turnover_rate']:.3f}%，"
                f"总市值 {tushare_data['total_mv_billion']:.2f} 亿元。"
            ),
        )
    ]
    if eastmoney_data:
        evidence_items.append(
            ValuationEvidenceItem(
                title="东方财富校验快照",
                source="东方财富 mx-data",
                date=latest_trade_date,
                content=(
                    f"总市值 {eastmoney_data.get('total_mv_billion', 0.0):.2f} 亿元，"
                    f"PE(TTM) {eastmoney_data.get('pe_ttm', 0.0):.2f} 倍，"
                    f"换手率 {eastmoney_data.get('turnover_rate', 0.0):.3f}%。"
                ),
            )
        )
    for key, source_name in (("announcements", "公告摘要"), ("sales_brief", "月度销售简报")):
        for line in (signal_data or {}).get(key, [])[:3]:
            evidence_items.append(
                ValuationEvidenceItem(
                    title=source_name,
                    source=source_name,
                    date=report_date,
                    content=str(line),
                )
            )
    for metric in (pig_cycle_metrics or [])[:2]:
        evidence_items.append(
            ValuationEvidenceItem(
                title=str(metric.get("name", "猪周期指标")),
                source=str((metric.get("source", {}) or {}).get("name", "猪周期数据")),
                date=str(metric.get("updated_at", latest_trade_date)),
                content=str(metric.get("explanation", metric.get("latest", ""))),
            )
        )

    peer_notes = []
    for metric in (trend_metrics or [])[:3]:
        name = str(metric.get("name", "")).strip()
        latest = str(metric.get("latest", "")).strip()
        if name and latest:
            peer_notes.append(f"{name} 当前值 {latest}")

    return ValuationRequest(
        symbol=PROJECT_CONFIG.tushare.ts_code,
        company_name="牧原股份",
        as_of_date=report_date,
        current_market_cap_billion=tushare_data.get("total_mv_billion"),
        current_price=tushare_data.get("close"),
        pe_ttm=tushare_data.get("pe_ttm"),
        pb=tushare_data.get("pb"),
        turnover_rate=tushare_data.get("turnover_rate"),
        evidence_items=evidence_items,
        peer_notes=peer_notes,
    )


def _valuation_result_fallback(valuation_request: ValuationRequest, error: Exception) -> ValuationResult:
    """当估值 Agent 调用失败时，返回保守的降级结果。"""
    return ValuationResult(
        valuation_status="数据不足",
        valuation_summary=f"估值分析暂时未能完成：{error}",
        valuation_method="基于当前可得快照做结构化评估",
        current_market_cap_billion=valuation_request.current_market_cap_billion,
        fair_value_range="暂无范围",
        key_evidence=[],
        risk_points=["估值 Agent 未能正常返回结果"],
        missing_data=["模型调用失败或输出结构不完整"],
        next_questions=["请在模型可用后重新执行估值分析"],
        source_list=[item.source for item in valuation_request.evidence_items[:3]],
    )


def _run_valuation_outcome(
    valuation_request: ValuationRequest,
    model_service: ModelService | None = None,
    valuation_agent: ValuationAgent | None = None,
) -> Any:
    """运行估值多轮协调器并返回完整结果。

    这里仅负责把模型服务、估值 Agent 和调度器组装起来，
    不承载任何估值结论逻辑。
    """
    service = model_service or ModelService.from_project_config()
    if valuation_agent is None:
        if not hasattr(service, "complete_json"):
            raise AttributeError("model_service must provide complete_json")
        valuation_agent = ValuationAgent(model_runner=service.complete_json)
    coordinator = ValuationResearchCoordinator(valuation_agent=valuation_agent)
    return coordinator.run(valuation_request)


def analyze_valuation_with_model(
    valuation_request: ValuationRequest,
    model_service: ModelService | None = None,
    valuation_agent: ValuationAgent | None = None,
) -> ValuationResult:
    """调用估值 Agent 生成结构化结果。"""
    try:
        outcome = _run_valuation_outcome(
            valuation_request=valuation_request,
            model_service=model_service,
            valuation_agent=valuation_agent,
        )
        return outcome.final_result
    except Exception as exc:
        return _valuation_result_fallback(valuation_request, exc)


def analyze_valuation_with_trace(
    valuation_request: ValuationRequest,
    model_service: ModelService | None = None,
    valuation_agent: ValuationAgent | None = None,
) -> tuple[ValuationResult, list[dict[str, Any]], str]:
    """调用估值 Agent 并返回轮次轨迹。

    核心估值逻辑仍由模型驱动；这里仅把每轮输入输出整理为可观察数据，
    方便夜间复盘、邮件回调和手动调试时追踪多轮补数过程。
    """
    try:
        if valuation_agent is None and model_service is not None and not hasattr(model_service, "complete_json"):
            valuation_result = analyze_valuation_with_model(
                valuation_request=valuation_request,
                model_service=model_service,
                valuation_agent=valuation_agent,
            )
            return valuation_result, [], "已通过兼容路径返回结果"

        outcome = _run_valuation_outcome(
            valuation_request=valuation_request,
            model_service=model_service,
            valuation_agent=valuation_agent,
        )
        trace = [
            {
                "round_index": round_item.round_index,
                "request_snapshot": round_item.request_snapshot,
                "prefill_notes": round_item.prefill_notes,
                "valuation_status": round_item.valuation_result.valuation_status,
                "valuation_summary": round_item.valuation_result.valuation_summary,
                "data_needs": [need.title for need in round_item.valuation_result.data_needs],
                "acquisition_attempts": [
                    {
                        "need_title": attempt.need_title,
                        "provider_name": attempt.provider_name,
                        "status": attempt.status,
                        "evidence_count": attempt.evidence_count,
                        "query": attempt.query,
                        "message": attempt.message,
                    }
                    for attempt in round_item.acquisition_attempts
                ],
                "added_evidence": [
                    {
                        "title": evidence.title,
                        "source": evidence.source,
                        "date": evidence.date,
                        "content": evidence.content,
                        "url": evidence.url,
                    }
                    for evidence in round_item.added_evidence
                ],
                "notes": round_item.notes,
            }
            for round_item in outcome.rounds
        ]
        return outcome.final_result, trace, outcome.termination_reason
    except Exception as exc:
        fallback = _valuation_result_fallback(valuation_request, exc)
        return fallback, [], f"回退：{exc}"


def render_valuation_markdown(
    valuation_request: ValuationRequest,
    valuation_result: ValuationResult,
) -> str:
    """把估值结果渲染成 Markdown 片段。"""
    evidence_lines = "\n".join(
        [
            f"- {item.title}｜{item.source}｜{item.date}｜{item.content}"
            for item in valuation_request.evidence_items[:5]
        ]
    ) or "- 暂无"
    key_evidence_lines = "\n".join([f"- {line}" for line in valuation_result.key_evidence]) or "- 暂无"
    risk_lines = "\n".join([f"- {line}" for line in valuation_result.risk_points]) or "- 暂无"
    missing_lines = "\n".join([f"- {line}" for line in valuation_result.missing_data]) or "- 暂无"
    question_lines = "\n".join([f"- {line}" for line in valuation_result.next_questions]) or "- 暂无"
    source_lines = "\n".join([f"- {line}" for line in valuation_result.source_list]) or "- 暂无"
    current_market_cap = (
        f"{valuation_result.current_market_cap_billion:.2f} 亿元"
        if valuation_result.current_market_cap_billion is not None
        else "暂无"
    )
    return f"""## 4. 估值分析

- 估值状态：{valuation_result.valuation_status}
- 估值结论：{valuation_result.valuation_summary}
- 估值方法：{valuation_result.valuation_method}
- 当前市值：{current_market_cap}
- 参考区间：{valuation_result.fair_value_range}

### 4.1 关键依据

{key_evidence_lines}

### 4.2 风险点

{risk_lines}

### 4.3 缺失数据

{missing_lines}

### 4.4 下一步补数问题

{question_lines}

### 4.5 输入证据清单

{evidence_lines}

### 4.6 来源列表

{source_lines}
"""


def build_analysis_prompt(context: dict[str, Any]) -> str:
    """构造投研分析提示词。

    个股异动、当前状态、影响判断都由模型完成；
    代码仅约束输出结构和最大条数，避免展示层不可控。
    """
    instruction = """
你是A股价值投资研究员。你的任务是根据输入的原始数据，输出一份结构化分析结果。

要求：
1. 只能基于输入的原始数据分析，不要编造不存在的事实。
2. 所有研究判断必须由你来完成，代码只负责传递数据和展示结果。
3. 只输出严格 JSON，不要输出 Markdown、代码块、解释性前后缀。
4. 个股异动最多 5 条，按影响重要性排序。
5. 异动名称必须是事实结论，尽量体现方向和数值，例如“5月商品猪销售收入同比下降30.13%”“换手率提升至2.759%”“能繁母猪存栏企稳回升”。
6. 异动信息写事实、数据和信源；若没有链接，source_link 置空字符串。
7. 异动影响只写该异动可能对公司质地或股价走势带来的影响，不要复述数据本身。
8. 若状态没有发生变化，status_changed 输出“否”，change_reason 输出空字符串。

输出 JSON schema：
{
  "current_status": "持有",
  "conclusion": "一句话结论",
  "status_changed": "是/否",
  "change_reason": "变化原因或空字符串",
  "focus_changes": [
    {
      "name": "异动名称",
      "info": "异动信息",
      "impact": "异动影响",
      "source_link": ""
    }
  ]
}
""".strip()
    return f"{instruction}\n\n原始数据：\n{json.dumps(context, ensure_ascii=False, indent=2)}"


def load_model_runtime_config() -> ModelRuntimeConfig:
    """读取运行阶段模型配置。"""
    return load_project_config().model


def build_codex_exec_command(
    prompt: str,
    config: ModelRuntimeConfig | None = None,
    output_file: Path | None = None,
) -> list[str]:
    """构造 Codex CLI 调用命令。

    这是兼容旧调用的薄封装，实际命令拼装逻辑位于公共层。
    """
    return _build_codex_exec_command(
        prompt,
        runtime=config or load_model_runtime_config(),
        output_file=output_file,
    )


def _codex_exec(prompt: str, config: ModelRuntimeConfig | None = None) -> str:
    """执行一次模型调用并返回原始文本。"""
    # 保留给测试和兼容调用；实际模型路由统一交给 ModelService。
    service = ModelService(runtime=config or load_model_runtime_config())
    return service._run(prompt)


def _normalize_analysis_result(raw: dict[str, Any]) -> dict[str, Any]:
    """清洗模型输出形态，保证后续渲染不会因字段缺失失败。"""
    focus_changes: list[dict[str, str]] = []
    for item in raw.get("focus_changes", []) or []:
        if not isinstance(item, dict):
            continue
        focus_changes.append(
            {
                "name": str(item.get("name", "")).strip(),
                "info": str(item.get("info", "")).strip(),
                "impact": str(item.get("impact", "")).strip(),
                "source_link": str(item.get("source_link", "")).strip(),
            }
        )
    return {
        "current_status": str(raw.get("current_status", "持有")).strip() or "持有",
        "conclusion": str(raw.get("conclusion", "")).strip() or "暂无结论",
        "status_changed": str(raw.get("status_changed", "否")).strip() or "否",
        "change_reason": str(raw.get("change_reason", "")).strip(),
        "focus_changes": focus_changes[:5],
    }


def analyze_report_with_model(
    context: dict[str, Any],
    analysis_client: Any | None = None,
    model_service: ModelService | None = None,
    model_config: ModelRuntimeConfig | None = None,
) -> dict[str, Any]:
    """调用模型生成日报分析结果。"""
    prompt = build_analysis_prompt(context)
    if analysis_client is not None:
        raw_text = analysis_client(prompt)
        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Model output is not valid JSON: {raw_text[:500]}") from exc
        if not isinstance(raw, dict):
            raise RuntimeError("Model output JSON must be an object.")
    else:
        service = model_service or ModelService(runtime=model_config or load_model_runtime_config())
        raw = service.complete_json(prompt)
    return _normalize_analysis_result(raw)


def build_focus_changes(
    tushare_data: dict[str, float],
    eastmoney_data: dict[str, float] | None,
    signal_data: dict[str, list[str]] | None,
    trend_metrics: list[dict[str, Any]] | None,
    analysis_client: Any | None = None,
    model_service: ModelService | None = None,
    model_config: ModelRuntimeConfig | None = None,
) -> list[dict[str, str]]:
    """兼容旧调用：只返回个股异动列表。"""
    context = build_report_context(
        report_date="",
        latest_trade_date="",
        tushare_data=tushare_data,
        eastmoney_data=eastmoney_data,
        signal_data=signal_data,
        trend_metrics=trend_metrics,
        pig_cycle_metrics=[],
    )
    analysis = analyze_report_with_model(
        context,
        analysis_client=analysis_client,
        model_service=model_service,
        model_config=model_config,
    )
    return analysis.get("focus_changes", [])


def render_focus_changes_markdown(focus_changes: list[dict[str, str]] | None) -> str:
    """渲染 Markdown 版个股异动，保持三段式输出。"""
    if not focus_changes:
        return "暂无显著异动，继续跟踪基础指标。"

    parts: list[str] = []
    for index, item in enumerate(focus_changes[:5], start=1):
        source_link = item.get("source_link", "").strip()
        info_text = item.get("info", "暂无").strip()
        if source_link:
            info_text = f"{info_text} ({source_link})"
        parts.append(f"{index}. 异动名称：{item.get('name', '未命名异动')}")
        parts.append(f"   异动信息：{info_text}")
        parts.append(f"   异动影响：{item.get('impact', '暂无')}")
        parts.append("")
    return "\n".join(parts).rstrip()


def render_focus_change_cards_html(focus_changes: list[dict[str, str]] | None) -> str:
    """渲染 HTML 邮件里的个股异动卡片。"""
    if not focus_changes:
        return "<p style=\"margin:0;color:#6b7280;\">暂无显著异动，继续跟踪基础指标。</p>"

    cards = []
    for item in focus_changes[:5]:
        name = html_escape(item.get("name", "未命名异动"))
        info = html_escape(item.get("info", "暂无"))
        source_link = item.get("source_link", "").strip()
        if source_link:
            info = f'{info} <a href="{html_escape(source_link)}" target="_blank" rel="noreferrer">链接</a>'
        impact = html_escape(item.get("impact", "暂无"))
        cards.append(
            "<div style=\"border:1px solid #e5e7eb;border-radius:14px;padding:14px 16px;background:#f8fafc;"
            "box-shadow:0 1px 2px rgba(15,23,42,0.04);\">"
            f"<div style=\"font-size:15px;font-weight:700;color:#0f172a;margin-bottom:8px;\">{name}</div>"
            f"<div style=\"font-size:13px;line-height:1.65;color:#334155;\"><strong>异动信息：</strong>{info}</div>"
            f"<div style=\"font-size:13px;line-height:1.65;color:#334155;margin-top:6px;\"><strong>异动影响：</strong>{impact}</div>"
            "</div>"
        )
    return "<div style=\"display:flex;flex-direction:column;gap:12px;\">%s</div>" % "".join(cards)


def render_key_metrics_html(key_metrics: dict[str, str] | None) -> str:
    """渲染 HTML 邮件里的关键指标卡片。"""
    if not key_metrics:
        return "<p style=\"margin:0;color:#6b7280;\">暂无关键指标。</p>"

    cards = []
    for name, value in key_metrics.items():
        cards.append(
            "<div style=\"flex:1 1 160px;border:1px solid #e5e7eb;border-radius:12px;padding:12px 14px;"
            "background:#f8fafc;\">"
            f"<div style=\"font-size:12px;color:#64748b;margin-bottom:6px;\">{html_escape(str(name))}</div>"
            f"<div style=\"font-size:18px;font-weight:700;color:#0f172a;\">{html_escape(str(value))}</div>"
            "</div>"
        )
    return "<div style=\"display:flex;flex-wrap:wrap;gap:12px;\">%s</div>" % "".join(cards)


def render_valuation_card_html(valuation_result: ValuationResult | None) -> str:
    """渲染 HTML 邮件里的估值结果摘要。"""
    if valuation_result is None:
        return "<p style=\"margin:0;color:#6b7280;\">暂无估值结果。</p>"

    current_market_cap = (
        f"{valuation_result.current_market_cap_billion:.2f} 亿元"
        if valuation_result.current_market_cap_billion is not None
        else "暂无"
    )
    key_evidence_html = "".join(
        f"<li style=\"margin:4px 0;\">{html_escape(item)}</li>" for item in valuation_result.key_evidence
    ) or "<li style=\"margin:4px 0;\">暂无</li>"
    risk_html = "".join(
        f"<li style=\"margin:4px 0;\">{html_escape(item)}</li>" for item in valuation_result.risk_points
    ) or "<li style=\"margin:4px 0;\">暂无</li>"
    missing_html = "".join(
        f"<li style=\"margin:4px 0;\">{html_escape(item)}</li>" for item in valuation_result.missing_data
    ) or "<li style=\"margin:4px 0;\">暂无</li>"
    return (
        "<div style=\"border:1px solid #e2e8f0;border-radius:14px;padding:16px 18px;background:#f8fafc;\">"
        f"<div style=\"font-size:20px;font-weight:700;color:#0f172a;margin-bottom:6px;\">{html_escape(valuation_result.valuation_status)}</div>"
        f"<div style=\"font-size:15px;line-height:1.7;color:#1e293b;margin-bottom:8px;\">{html_escape(valuation_result.valuation_summary)}</div>"
        f"<div style=\"font-size:13px;color:#475569;margin-bottom:10px;\">估值方法：{html_escape(valuation_result.valuation_method)}｜当前市值：{html_escape(current_market_cap)}｜参考区间：{html_escape(valuation_result.fair_value_range)}</div>"
        "<div style=\"font-size:13px;color:#334155;line-height:1.65;\">"
        "<strong>关键依据：</strong><ul style=\"margin:6px 0 10px 18px;padding:0;\">"
        f"{key_evidence_html}</ul>"
        "<strong>风险点：</strong><ul style=\"margin:6px 0 10px 18px;padding:0;\">"
        f"{risk_html}</ul>"
        "<strong>缺失数据：</strong><ul style=\"margin:6px 0 0 18px;padding:0;\">"
        f"{missing_html}</ul>"
        "</div>"
        "</div>"
    )


def _sanitize_markdown_cell(value: Any) -> str:
    """清理 Markdown 表格单元格中的换行和分隔符。"""
    text = str(value).replace("\n", " ").replace("|", "/").strip()
    return text or "暂无"


def render_valuation_trace_markdown(valuation_trace: list[dict[str, Any]] | None) -> str:
    """把估值多轮补数路径渲染成 Markdown 章节。

    这里只记录确定性的轮次、证据获取路径和结果摘要，便于邮件和首页对齐同一份执行轨迹。
    """
    valuation_trace = valuation_trace or []
    if not valuation_trace:
        return "## 13. 数据获取轮次与路径\n\n- 本次未进入估值补数闭环。\n"

    parts = ["## 13. 数据获取轮次与路径", ""]
    for round_item in valuation_trace:
        round_index = round_item.get("round_index", "—")
        valuation_status = _sanitize_markdown_cell(round_item.get("valuation_status", "—"))
        valuation_summary = _sanitize_markdown_cell(round_item.get("valuation_summary", "—"))
        parts.append(f"### 第 {round_index} 轮")
        parts.append("")
        parts.append(f"- 估值状态：{valuation_status}")
        parts.append(f"- 估值摘要：{valuation_summary}")
        prefill_notes = round_item.get("prefill_notes", []) or []
        data_needs = round_item.get("data_needs", []) or []
        notes = round_item.get("notes", []) or []
        if prefill_notes:
            parts.append(f"- 预填信息：{_sanitize_markdown_cell('；'.join(prefill_notes))}")
        if data_needs:
            parts.append(f"- 数据诉求：{_sanitize_markdown_cell('、'.join(data_needs))}")
        if notes:
            parts.append(f"- 本轮备注：{_sanitize_markdown_cell('；'.join(notes))}")

        acquisition_attempts = round_item.get("acquisition_attempts", []) or []
        if acquisition_attempts:
            parts.append("")
            parts.append("| 诉求 | provider | 状态 | 证据数 | 查询 | 说明 |")
            parts.append("| --- | --- | --- | --- | --- | --- |")
            for attempt in acquisition_attempts:
                parts.append(
                    "| "
                    + " | ".join(
                        [
                            _sanitize_markdown_cell(attempt.get("need_title", "—")),
                            _sanitize_markdown_cell(attempt.get("provider_name", "—")),
                            _sanitize_markdown_cell(attempt.get("status", "—")),
                            _sanitize_markdown_cell(attempt.get("evidence_count", "—")),
                            _sanitize_markdown_cell(attempt.get("query", "")),
                            _sanitize_markdown_cell(attempt.get("message", "")),
                        ]
                    )
                    + " |"
                )
        parts.append("")

    return "\n".join(parts)


def render_report_markdown(
    report_date: str,
    latest_trade_date: str,
    tushare_data: dict[str, float],
    eastmoney_data: dict[str, float] | None,
    signal_data: dict[str, list[str]] | None = None,
    pig_cycle_metrics: list[dict[str, Any]] | None = None,
    analysis: dict[str, Any] | None = None,
    valuation_request: ValuationRequest | None = None,
    valuation_result: ValuationResult | None = None,
    valuation_trace: list[dict[str, Any]] | None = None,
) -> str:
    """生成完整 Markdown 日报正文。"""
    signal_data = signal_data or {}
    pig_cycle_metrics = pig_cycle_metrics or []
    analysis = analysis or {}
    focus_changes = analysis.get("focus_changes", []) or []
    current_status = str(analysis.get("current_status", "持有"))
    conclusion = str(analysis.get("conclusion", "暂无结论"))
    status_changed = str(analysis.get("status_changed", "否"))
    change_reason = str(analysis.get("change_reason", ""))
    em_total_mv = (
        f"{eastmoney_data['total_mv_billion']:.2f} 亿元"
        if eastmoney_data and eastmoney_data.get("total_mv_billion") is not None
        else "东方财富校验暂未获取成功"
    )
    em_pe = (
        f"{eastmoney_data['pe_ttm']:.2f} 倍"
        if eastmoney_data and eastmoney_data.get("pe_ttm") is not None
        else "东方财富校验暂未获取成功"
    )
    em_turnover = (
        f"{eastmoney_data['turnover_rate']:.3f}%"
        if eastmoney_data and eastmoney_data.get("turnover_rate") is not None
        else "东方财富校验暂未获取成功"
    )

    validation_note = (
        "东方财富校验已获取。"
        if eastmoney_data
        else "东方财富校验暂未获取成功，本次先以 Tushare 主数据生成日报。"
    )
    announcement_text = _render_signal_lines(
        signal_data.get("announcements", []),
        "本次未自动获取到新的公告摘要，需补查交易所/公司公告。",
    )
    sales_brief_text = _render_signal_lines(
        signal_data.get("sales_brief", []),
        "本次未自动获取到新的月度销售简报摘要。",
    )
    pig_cycle_text = _render_signal_lines(
        render_hog_cycle_lines(pig_cycle_metrics),
        "本次未自动获取到新的猪周期 API 数据。",
    )
    focus_changes_text = render_focus_changes_markdown(focus_changes)
    valuation_text = (
        render_valuation_markdown(valuation_request, valuation_result)
        if valuation_request and valuation_result
        else f"""## 4. 估值分析

- 估值状态：暂无
- 估值结论：本次未执行估值 Agent。
- 估值方法：暂无
- 当前市值：{tushare_data['total_mv_billion']:.2f} 亿元
- 参考区间：暂无
"""
    )
    valuation_trace_text = render_valuation_trace_markdown(valuation_trace)

    return f"""# {report_date} 牧原股份 {_report_clock_label()} 日复盘

## 1. 今日核心结论

- 一句话结论：{conclusion}
- 当前状态：{current_status}
{f'- 是否较昨日变化：{status_changed}' if status_changed == '是' else ''}
{f'- 变化原因：{change_reason}' if change_reason and status_changed == '是' else ''}

## 2. 个股异动

{focus_changes_text}

## 3. 关键数据快照

| 指标 | 数值 | 主来源 | 校验来源 | 备注 |
| --- | --- | --- | --- | --- |
| 收盘价 | {tushare_data['close']:.2f} 元 | Tushare | - | 交易日 {latest_trade_date} |
| 涨跌幅 | {tushare_data['pct_chg']:.2f}% | Tushare | - | 交易日 {latest_trade_date} |
| PE(TTM) | {tushare_data['pe_ttm']:.2f} 倍 | Tushare | {em_pe} |  |
| PB | {tushare_data['pb']:.3f} 倍 | Tushare | - |  |
| 换手率 | {tushare_data['turnover_rate']:.3f}% | Tushare | {em_turnover} |  |
| 总市值 | {tushare_data['total_mv_billion']:.2f} 亿元 | Tushare | {em_total_mv} | 若差异存在，按口径差异保留展示 |

{valuation_text}

{valuation_trace_text}

## 5. 猪周期核心数据

- 猪周期 API 数据：
{pig_cycle_text}

## 6. 行业与周期变化

- 行业去产能 / 补产能信号：待补充公开信源检索结果。
- 当前周期位置判断：本日报先输出价格与估值快照，周期位置信号后续继续自动化补齐。

## 7. 公司经营变化

- 月度销售简报：
{sales_brief_text}
- 成本变化线索：待补充财报/公告/公开纪要。
- 重大公告：
{announcement_text}
- 是否出现逻辑强化 / 弱化信号：暂无新增自动判断，需结合后续公告与行业数据。

## 8. 热度与交易层观察

- 换手率与成交额是否异常：换手率 {tushare_data['turnover_rate']:.3f}%，需继续结合近 20 日均值观察是否抬升。
- 市场情绪是否过热 / 过冷：当前仅做快照，不做单日情绪结论。
- 估值是否接近历史极端区间：待补充历史估值分位对照表。

## 9. 当前五档状态判断

- 当前状态：持有
- 保持 / 调整原因：公司仍在好公司池中，交易层暂未出现足以触发状态切换的明确信号。
- 若调整状态，触发信号是什么：后续重点观察猪价、出栏、成本、资产负债率和热度共振变化。

## 10. 明日建议

- 明天最值得看的 3 个点：
  1. 是否有新的公司公告或月度经营数据。
  2. 是否出现更明确的猪周期位置变化信号。
  3. 估值与热度是否继续抬升或回落。

## 11. 指标有效性检查

- 今天最有解释力的指标：收盘价、PE(TTM)、PB、换手率、总市值快照。
- 今天噪音较大的指标：单日价格波动本身。
- 是否需要补充新指标：需要继续补齐猪价、能繁母猪存栏、月度销售简报和公告自动化。

## 12. 数据来源与校验说明

- 主来源：Tushare
- 校验来源：东方财富 `mx-data`
- 校验状态：{validation_note}
"""


def render_email_html(
    subject: str,
    markdown_body: str,
    key_metrics: dict[str, str],
    trend_metrics: list[dict[str, Any]] | None = None,
    analysis: dict[str, Any] | None = None,
    valuation_result: ValuationResult | None = None,
) -> str:
    """生成 HTML 邮件正文。

    当前状态、个股异动、趋势卡片靠前展示，便于手机端快速扫读。
    """
    analysis = analysis or {}
    focus_changes = analysis.get("focus_changes", []) or []
    current_status = str(analysis.get("current_status", "持有"))
    conclusion = str(analysis.get("conclusion", "暂无结论"))
    status_changed = str(analysis.get("status_changed", "否"))
    change_reason = str(analysis.get("change_reason", ""))
    status_detail_html = (
        f"<div style=\"font-size:13px;color:#475569;\">是否较昨日变化：{html_escape(status_changed)}｜变化原因：{html_escape(change_reason)}</div>"
        if status_changed == "是" and change_reason
        else ""
    )
    key_metrics_html = render_key_metrics_html(key_metrics)
    focus_html = render_focus_change_cards_html(focus_changes)
    valuation_html = render_valuation_card_html(valuation_result)
    trend_cards = render_metric_trend_cards(trend_metrics)
    body_html = markdown_to_basic_html(markdown_body)
    return (
        "<html><body style=\"margin:0;padding:24px;background:#f3f4f6;"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#111827;\">"
        "<div style=\"max-width:900px;margin:0 auto;background:#ffffff;border-radius:16px;padding:28px 32px;"
        "box-shadow:0 8px 24px rgba(15,23,42,0.08);\">"
        f"<h1 style=\"margin:0 0 8px 0;font-size:28px;\">{html_escape(subject)}</h1>"
        "<p style=\"margin:0 0 20px 0;color:#6b7280;\">自动生成的牧原股份夜间复盘邮件，已按主数据+校验数据输出。</p>"
        "<h2 style=\"font-size:18px;margin:0 0 12px 0;\">当前状态</h2>"
        "<div style=\"border:1px solid #dbeafe;background:#eff6ff;border-radius:14px;padding:16px 18px;margin-bottom:20px;\">"
        f"<div style=\"font-size:20px;font-weight:700;color:#0f172a;margin-bottom:6px;\">{html_escape(current_status)}</div>"
        f"<div style=\"font-size:15px;line-height:1.7;color:#1e293b;margin-bottom:8px;\">{html_escape(conclusion)}</div>"
        f"{status_detail_html}"
        "</div>"
        "<h2 style=\"font-size:18px;margin:0 0 12px 0;\">关键指标</h2>"
        f"<div style=\"margin-bottom:20px;\">{key_metrics_html}</div>"
        "<h2 style=\"font-size:18px;margin:0 0 12px 0;\">估值判断</h2>"
        f"<div style=\"margin-bottom:20px;\">{valuation_html}</div>"
        "<h2 style=\"font-size:18px;margin:0 0 12px 0;\">个股异动</h2>"
        f"<div style=\"margin-bottom:20px;\">{focus_html}</div>"
        "<h2 style=\"font-size:18px;margin:0 0 12px 0;\">关键指标趋势</h2>"
        f"<div style=\"margin-bottom:20px;\">{trend_cards}</div>"
        "<h2 style=\"font-size:18px;margin:0 0 12px 0;\">完整复盘正文</h2>"
        f"<div style=\"line-height:1.75;font-size:14px;color:#1f2937;\">{body_html}</div>"
        "</div></body></html>"
    )


def markdown_to_basic_html(markdown_body: str) -> str:
    """把项目内受控 Markdown 转成基础 HTML。

    这里只覆盖日报模板实际使用的标题、列表和表格语法。
    """
    lines = markdown_body.splitlines()
    html_parts: list[str] = []
    in_list = False
    in_table = False
    table_headers: list[str] = []

    def close_list() -> None:
        """关闭当前 HTML 列表。"""
        nonlocal in_list
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    def close_table() -> None:
        """关闭当前 HTML 表格。"""
        nonlocal in_table, table_headers
        if in_table:
            html_parts.append("</tbody></table>")
            in_table = False
            table_headers = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            close_list()
            close_table()
            continue
        if stripped.startswith("# "):
            close_list()
            close_table()
            html_parts.append(f"<h1 style=\"font-size:24px;margin:18px 0 10px;\">{html_escape(stripped[2:])}</h1>")
            continue
        if stripped.startswith("## "):
            close_list()
            close_table()
            html_parts.append(f"<h2 style=\"font-size:18px;margin:18px 0 10px;\">{html_escape(stripped[3:])}</h2>")
            continue
        if stripped.startswith("### "):
            close_list()
            close_table()
            html_parts.append(f"<h3 style=\"font-size:16px;margin:16px 0 8px;\">{html_escape(stripped[4:])}</h3>")
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(set(cell) <= {"-"} for cell in cells):
                continue
            close_list()
            if not in_table:
                table_headers = cells
                html_parts.append("<table style=\"border-collapse:collapse;width:100%;margin:12px 0 18px;\"><thead><tr>")
                for header in table_headers:
                    html_parts.append(
                        f"<th style=\"border:1px solid #e5e7eb;background:#f8fafc;padding:8px 10px;text-align:left;\">{html_escape(header)}</th>"
                    )
                html_parts.append("</tr></thead><tbody>")
                in_table = True
            else:
                html_parts.append("<tr>")
                for cell in cells:
                    html_parts.append(
                        f"<td style=\"border:1px solid #e5e7eb;padding:8px 10px;vertical-align:top;\">{html_escape(cell)}</td>"
                    )
                html_parts.append("</tr>")
            continue
        close_table()
        if stripped.startswith("- "):
            if not in_list:
                html_parts.append("<ul style=\"margin:8px 0 14px 20px;padding:0;\">")
                in_list = True
            html_parts.append(f"<li style=\"margin:4px 0;\">{html_escape(stripped[2:])}</li>")
            continue
        close_list()
        html_parts.append(f"<p style=\"margin:8px 0;\">{html_escape(stripped)}</p>")

    close_list()
    close_table()
    return "".join(html_parts)


def build_email_message(
    recipient: str,
    subject: str,
    text_body: str,
    html_body: str,
    *,
    sender: str | None = None,
) -> str:
    """构造 multipart 邮件，同时保留纯文本和 HTML 两种正文。"""
    boundary = f"===============_{uuid.uuid4().hex}"
    from_header = sender or recipient
    return (
        f"From: {from_header}\n"
        f"To: {recipient}\n"
        f"Subject: {subject}\n"
        "MIME-Version: 1.0\n"
        f"Content-Type: multipart/alternative; boundary=\"{boundary}\"\n"
        "\n"
        f"--{boundary}\n"
        "Content-Type: text/plain; charset=UTF-8\n"
        "\n"
        f"{text_body}\n"
        f"--{boundary}\n"
        "Content-Type: text/html; charset=UTF-8\n"
        "\n"
        f"{html_body}\n"
        f"--{boundary}--\n"
    )


def render_launchd_plist(
    python_path: str,
    project_root: str,
    recipient: str,
    hour: int,
    minute: int,
    label: str,
) -> str:
    """生成 macOS launchd 定时任务配置。"""
    script_path = f"{project_root}/product/app/backend/application/reports/muyuan_nightly.py"
    log_path = f"{project_root}/product/app/backend/application/reports/muyuan_nightly.log"
    xml_items = "\n".join(
        [
            "    <key>ProgramArguments</key>",
            "    <array>",
            f"        <string>{escape(python_path)}</string>",
            f"        <string>{escape(script_path)}</string>",
            "        <string>--send-email</string>",
            f"        <string>--recipient</string>",
            f"        <string>{escape(recipient)}</string>",
            "    </array>",
        ]
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{escape(label)}</string>
{xml_items}
    <key>WorkingDirectory</key>
    <string>{escape(project_root)}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{escape(log_path)}</string>
    <key>StandardErrorPath</key>
    <string>{escape(log_path)}</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""


def get_preferred_python_path() -> str:
    """选择定时任务使用的 Python 解释器。

    优先使用项目后端虚拟环境，确保 Tushare、AkShare 等项目依赖与部署脚本一致；
    妙想虚拟环境只作为兼容旧运行方式的兜底。
    """
    runtime_python = PROJECT_CONFIG.runtime.python_path.strip()
    if runtime_python:
        configured_path = Path(runtime_python)
        return str(configured_path if configured_path.is_absolute() else ROOT / configured_path)
    project_python = ROOT / "product" / "app" / "backend" / ".venv" / "bin" / "python"
    if project_python.exists():
        return str(project_python)
    miaoxiang_python = Path.home() / ".miaoxiang-venv" / "bin" / "python"
    if miaoxiang_python.exists():
        return str(miaoxiang_python)
    return sys.executable


def write_report(report_date: str, content: str, force: bool = False) -> Path:
    """写入日报 Markdown 文件。"""
    output_path = REPORT_DIR / f"{report_date}-muyuan.md"
    if output_path.exists() and not force:
        return output_path
    output_path.write_text(content, encoding="utf-8")
    return output_path


def send_email(recipient: str, subject: str, text_body: str, html_body: str) -> None:
    """通过仓库内私密配置发送日报邮件。"""
    private_config = load_private_config()
    smtp_config = PROJECT_CONFIG.smtp
    message = build_email_message(
        recipient=recipient,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        sender=smtp_config.from_addr,
    )
    smtp_client: smtplib.SMTP | smtplib.SMTP_SSL | None = None
    try:
        if smtp_config.port == 465:
            smtp_client = smtplib.SMTP_SSL(smtp_config.host, smtp_config.port, timeout=30)
        else:
            smtp_client = smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=30)
            smtp_client.ehlo()
            if smtp_config.port == 587:
                smtp_client.starttls()
                smtp_client.ehlo()
        smtp_client.login(smtp_config.user, private_config.smtp_password)
        smtp_client.sendmail(smtp_config.from_addr, [recipient], message.encode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"SMTP send failed: {exc}") from exc
    finally:
        if smtp_client is not None:
            try:
                smtp_client.quit()
            except Exception:
                smtp_client.close()


def install_launch_agent(
    python_path: str,
    project_root: Path,
    recipient: str,
    hour: int,
    minute: int,
    label: str,
) -> Path:
    """安装本机每日定时任务配置文件。"""
    launch_agents = Path.home() / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True, exist_ok=True)
    plist_path = launch_agents / f"{label}.plist"
    plist_path.write_text(
        render_launchd_plist(
            python_path=python_path,
            project_root=str(project_root),
            recipient=recipient,
            hour=hour,
            minute=minute,
            label=label,
        ),
        encoding="utf-8",
    )
    return plist_path


def generate_report(report_date: str, force: bool = False) -> tuple[Path, str, dict[str, Any]]:
    """生成牧原股份日报。

    数据获取、趋势卡片和邮件渲染由代码负责；
    当前状态、个股异动和影响判断由模型负责。
    """
    private_config = load_private_config()
    latest_trade_date, tushare_data = get_tushare_snapshot(
        token=private_config.secrets.tushare_token,
        ts_code=PROJECT_CONFIG.tushare.ts_code,
        as_of_date=report_date,
    )
    eastmoney_data = get_eastmoney_snapshot()
    signal_data = get_signal_data()
    trend_metrics = get_tushare_trend_metrics(
        token=private_config.secrets.tushare_token,
        ts_code=PROJECT_CONFIG.tushare.ts_code,
        as_of_date=report_date,
    )
    pig_cycle_metrics = get_hog_cycle_metrics()
    combined_trend_metrics = trend_metrics + pig_cycle_metrics
    model_service = ModelService.from_project_config()
    valuation_request = build_valuation_request(
        report_date=report_date,
        latest_trade_date=latest_trade_date,
        tushare_data=tushare_data,
        eastmoney_data=eastmoney_data,
        signal_data=signal_data,
        trend_metrics=combined_trend_metrics,
        pig_cycle_metrics=pig_cycle_metrics,
    )
    analysis_context = build_report_context(
        report_date=report_date,
        latest_trade_date=latest_trade_date,
        tushare_data=tushare_data,
        eastmoney_data=eastmoney_data,
        signal_data=signal_data,
        trend_metrics=combined_trend_metrics,
        pig_cycle_metrics=pig_cycle_metrics,
    )
    analysis = analyze_report_with_model(analysis_context, model_service=model_service)
    valuation_result, valuation_trace, valuation_termination_reason = analyze_valuation_with_trace(
        valuation_request,
        model_service=model_service,
    )
    content = render_report_markdown(
        report_date=report_date,
        latest_trade_date=latest_trade_date,
        tushare_data=tushare_data,
        eastmoney_data=eastmoney_data,
        signal_data=signal_data,
        pig_cycle_metrics=pig_cycle_metrics,
        analysis=analysis,
        valuation_request=valuation_request,
        valuation_result=valuation_result,
        valuation_trace=valuation_trace,
    )
    output_path = write_report(report_date, content, force=force)
    return output_path, content, {
        "latest_trade_date": latest_trade_date,
        "tushare_data": tushare_data,
        "eastmoney_data": eastmoney_data,
        "signal_data": signal_data,
        "trend_metrics": combined_trend_metrics,
        "pig_cycle_metrics": pig_cycle_metrics,
        "analysis": analysis,
        "valuation_request": valuation_request,
        "valuation_result": valuation_result,
        "valuation_trace": valuation_trace,
        "valuation_termination_reason": valuation_termination_reason,
    }


async def run_report_workflow_async(
    report_date: str,
    *,
    force: bool = False,
    recipient: str | None = None,
    email_callback: Any | None = None,
) -> tuple[Path, str, dict[str, Any]]:
    """异步执行日报工作流。

    先在后台线程完成模型分析和报告生成，再在成功后触发邮件回调。
    回调可由调度器、API 或 CLI 注入；未注入时默认使用本地 SMTP 发送。
    """
    output_path, content, report_context = await asyncio.to_thread(generate_report, report_date, force)
    subject = build_email_subject(report_date)
    html_body = render_email_html(
        subject=subject,
        markdown_body=content,
        key_metrics={
            "收盘价": f"{report_context['tushare_data']['close']:.2f} 元",
            "PE(TTM)": f"{report_context['tushare_data']['pe_ttm']:.2f} 倍",
            "PB": f"{report_context['tushare_data']['pb']:.3f} 倍",
            "换手率": f"{report_context['tushare_data']['turnover_rate']:.3f}%",
            "总市值": f"{report_context['tushare_data']['total_mv_billion']:.2f} 亿元",
        },
        trend_metrics=report_context["trend_metrics"],
        analysis=report_context["analysis"],
        valuation_result=report_context["valuation_result"],
    )

    if email_callback is not None:
        callback_result = email_callback(
            recipient=recipient,
            subject=subject,
            text_body=content,
            html_body=html_body,
            report_date=report_date,
            report_context=report_context,
            output_path=output_path,
        )
        if inspect.isawaitable(callback_result):
            await callback_result
    elif recipient is not None:
        await asyncio.to_thread(send_email, recipient, subject, content, html_body)

    return output_path, content, report_context


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="Generate and mail Muyuan nightly review.")
    parser.add_argument("--date", default=None, help="Report date in YYYY-MM-DD format.")
    parser.add_argument("--recipient", default=DEFAULT_RECIPIENT, help="Mail recipient.")
    parser.add_argument("--send-email", action="store_true", help="Send report by email.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing report.")
    parser.add_argument("--install-launchd", action="store_true", help="Write launchd plist.")
    parser.add_argument("--hour", type=int, default=DEFAULT_HOUR, help="launchd hour.")
    parser.add_argument("--minute", type=int, default=DEFAULT_MINUTE, help="launchd minute.")
    parser.add_argument("--label", default=DEFAULT_LABEL, help="launchd label.")
    return parser.parse_args()


def main() -> int:
    """命令行入口。

    若当前解释器不是配置里的 Python，会自动切换一次，
    保证定时任务和手动执行使用同一套依赖环境。
    """
    preferred_python = get_preferred_python_path()
    if (
        os.getenv(PROJECT_CONFIG.runtime.reexec_flag) != "1"
        and os.path.abspath(sys.executable) != os.path.abspath(preferred_python)
    ):
        env = os.environ.copy()
        env[PROJECT_CONFIG.runtime.reexec_flag] = "1"
        result = subprocess.run([preferred_python, __file__, *sys.argv[1:]], env=env)
        return result.returncode

    args = parse_args()
    if args.date:
        report_date = args.date
    else:
        from datetime import date

        report_date = date.today().isoformat()

    if args.send_email:
        async def _send() -> None:
            return await run_report_workflow_async(
                report_date=report_date,
                force=args.force,
                recipient=args.recipient,
            )

        output_path, _, report_context = asyncio.run(_send())
        print(f"generated: {output_path}")
        print(f"sent email to: {args.recipient}")
        valuation_trace = report_context.get("valuation_trace", []) or []
        print(f"valuation rounds: {len(valuation_trace)}")
        for item in valuation_trace:
            print(
                "round "
                f"{item['round_index']}: "
                f"{item['valuation_status']} | "
                f"{item['valuation_summary']} | "
                f"data_needs={item['data_needs']} | "
                f"added_evidence={len(item['added_evidence'])}"
            )
            for attempt in item.get("acquisition_attempts", []):
                print(
                    "  "
                    f"need={attempt['need_title']} | "
                    f"provider={attempt['provider_name']} | "
                    f"status={attempt['status']} | "
                    f"count={attempt['evidence_count']} | "
                    f"message={attempt['message']}"
                )
    else:
        output_path, _, _ = generate_report(report_date=report_date, force=args.force)
        print(f"generated: {output_path}")

    if args.install_launchd:
        plist_path = install_launch_agent(
            python_path=preferred_python,
            project_root=ROOT,
            recipient=args.recipient,
            hour=args.hour,
            minute=args.minute,
            label=args.label,
        )
        print(f"launchd plist written: {plist_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
