"""牧原股份夜间复盘任务测试。

职责：
- 验证日报 Markdown、HTML 邮件、模型分析、launchd 配置和东方财富解析。
- 保护“代码做确定性流转，分析判断由模型驱动”的任务链路边界。
"""

import asyncio
import unittest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from product.agents.agents.valuation import (
    AkShareEvidenceProvider,
    DataAcquisitionAgent,
    MxDataEvidenceProvider,
    ValuationAgent,
    ValuationDataNeed,
    ValuationRequest,
    ValuationResearchCoordinator,
    MxSearchEvidenceProvider,
    WebSearchDeepseekEvidenceProvider,
)
from product.app.backend.application.reports.muyuan_nightly import (
    analyze_valuation_with_model,
    build_email_subject,
    build_email_message,
    build_codex_exec_command,
    build_focus_changes,
    build_valuation_request,
    build_sparkline_svg,
    analyze_report_with_model,
    build_report_context,
    generate_report,
    load_private_config,
    load_model_runtime_config,
    parse_eastmoney_stdout,
    _sync_private_secrets_to_runtime_env,
    render_email_html,
    render_launchd_plist,
    render_report_markdown,
    render_valuation_markdown,
    summarize_mx_search_output,
)
from product.app.backend.infrastructure.config.project_config import load_project_config


class MuyuanNightlyReportTests(unittest.TestCase):
    """Markdown 日报渲染测试。"""

    def test_render_report_includes_key_metrics_and_sources(self) -> None:
        """验证日报包含关键指标、主来源和校验来源。"""
        project_config = load_project_config()
        expected_clock = f"{project_config.launchd.hour:02d}:{project_config.launchd.minute:02d}"
        markdown = render_report_markdown(
            report_date="2026-06-27",
            latest_trade_date="2026-06-26",
            tushare_data={
                "close": 33.56,
                "pct_chg": 3.7083,
                "pe_ttm": 19.81,
                "pb": 2.246,
                "turnover_rate": 2.759,
                "total_mv_billion": 1937.42,
            },
            eastmoney_data={
                "total_mv_billion": 1912.0,
                "pe_ttm": 19.81,
                "turnover_rate": 2.759,
            },
        )

        self.assertIn(f"# 2026-06-27 牧原股份 {expected_clock} 日复盘", markdown)
        self.assertIn("33.56 元", markdown)
        self.assertIn("19.81 倍", markdown)
        self.assertIn("2.246 倍", markdown)
        self.assertIn("1937.42 亿元", markdown)
        self.assertIn("东方财富", markdown)
        self.assertIn("Tushare", markdown)

    def test_render_report_marks_validation_failure_when_missing(self) -> None:
        """验证东方财富校验缺失时，日报会显式说明校验失败。"""
        markdown = render_report_markdown(
            report_date="2026-06-27",
            latest_trade_date="2026-06-26",
            tushare_data={
                "close": 33.56,
                "pct_chg": 3.7083,
                "pe_ttm": 19.81,
                "pb": 2.246,
                "turnover_rate": 2.759,
                "total_mv_billion": 1937.42,
            },
            eastmoney_data=None,
        )

        self.assertIn("东方财富校验暂未获取成功", markdown)

    def test_render_report_includes_signal_summaries(self) -> None:
        """验证公告、销售简报和猪周期信号会进入日报正文。"""
        markdown = render_report_markdown(
            report_date="2026-06-27",
            latest_trade_date="2026-06-26",
            tushare_data={
                "close": 33.56,
                "pct_chg": 3.7083,
                "pe_ttm": 19.81,
                "pb": 2.246,
                "turnover_rate": 2.759,
                "total_mv_billion": 1937.42,
            },
            eastmoney_data=None,
            signal_data={
                "announcements": ["2026-06-25：披露月度销售简报（来源：巨潮资讯/公告检索）"],
                "sales_brief": ["2026-06-25：月度销售简报已披露，待进一步抽取出栏量与均价。"],
            },
            pig_cycle_metrics=[
                {
                    "name": "现货生猪",
                    "latest": "9.37 元/公斤",
                    "updated_at": "2026-06-28",
                    "source": {"name": "AkShare spot_hog_year_trend_soozhu()"},
                    "explanation": "现货生猪今年以来（月度）明显回落，最新值为9.37。",
                }
            ],
        )

        self.assertIn("披露月度销售简报", markdown)
        self.assertIn("猪周期核心数据", markdown)
        self.assertIn("现货生猪：9.37 元/公斤", markdown)

    def test_render_report_includes_valuation_trace_details(self) -> None:
        """验证日报正文会写入估值多轮补数路径和 provider 明细。"""
        markdown = render_report_markdown(
            report_date="2026-06-27",
            latest_trade_date="2026-06-26",
            tushare_data={
                "close": 33.56,
                "pct_chg": 3.7083,
                "pe_ttm": 19.81,
                "pb": 2.246,
                "turnover_rate": 2.759,
                "total_mv_billion": 1937.42,
            },
            eastmoney_data=None,
            valuation_trace=[
                {
                    "round_index": 1,
                    "valuation_status": "need_more_data",
                    "valuation_summary": "首轮需要补充 PE 与 PB。",
                    "prefill_notes": ["已预填市值"],
                    "data_needs": ["PE", "PB"],
                    "notes": ["第三轮后全渠道展开"],
                    "acquisition_attempts": [
                        {
                            "need_title": "PE",
                            "provider_name": "tushare",
                            "status": "success",
                            "evidence_count": 2,
                            "query": "PE",
                            "message": "补充 2 条证据",
                        },
                        {
                            "need_title": "PB",
                            "provider_name": "mx-data",
                            "status": "success",
                            "evidence_count": 1,
                            "query": "PB",
                            "message": "补充 1 条证据",
                        },
                    ],
                }
            ],
        )

        self.assertIn("数据获取轮次与路径", markdown)
        self.assertIn("第 1 轮", markdown)
        self.assertIn("tushare", markdown)
        self.assertIn("mx-data", markdown)
        self.assertIn("首轮需要补充 PE 与 PB", markdown)


class EmailRenderingTests(unittest.TestCase):
    """模型配置、HTML 邮件和报告生成链路测试。"""

    def test_load_model_runtime_config_defaults_to_external_profile(self) -> None:
        """验证默认运行模型配置指向外部模型档位。"""
        with patch.dict(os.environ, {}, clear=True):
            config = load_model_runtime_config()

        self.assertEqual(config.profile, "external")
        self.assertEqual(config.provider, "deepseek")
        self.assertEqual(config.name, "deepseek-v4-pro")
        self.assertFalse(config.use_oss)
        self.assertIsNone(config.local_provider)

    def test_build_codex_exec_command_uses_external_profile_by_default(self) -> None:
        """验证 Codex CLI 命令默认带上 external profile 和模型名。"""
        with patch.dict(os.environ, {}, clear=True):
            command = build_codex_exec_command("请输出 JSON")

        self.assertIn("--profile", command)
        self.assertIn("external", command)
        self.assertIn("--model", command)
        self.assertIn("deepseek-v4-pro", command)
        self.assertIn("--output-last-message", command)
        self.assertIn("请输出 JSON", command)

    def test_build_codex_exec_command_honors_runtime_overrides(self) -> None:
        """验证运行时模型配置覆盖能反映到 Codex CLI 命令。"""
        config = load_model_runtime_config()
        overridden = type(config)(
            provider="codex",
            profile="current",
            name="gpt-5.5",
            api_key_env="DEEPSEEK_API_KEY",
            base_url="https://api.deepseek.com",
            thinking=False,
            reasoning_effort="high",
            use_oss=True,
            local_provider="openai",
        )

        command = build_codex_exec_command("请输出 JSON", config=overridden)

        self.assertIn("--profile", command)
        self.assertIn("current", command)
        self.assertIn("--model", command)
        self.assertIn("gpt-5.5", command)
        self.assertIn("--oss", command)
        self.assertIn("--local-provider", command)
        self.assertIn("openai", command)

    def test_build_sparkline_svg_creates_line_chart(self) -> None:
        """验证邮件内联折线图会生成 SVG 和折线元素。"""
        svg = build_sparkline_svg([10, 12, 11, 15, 14], stroke="#111827")

        self.assertIn("<svg", svg)
        self.assertIn("<polyline", svg)
        self.assertIn("111827", svg)

    def test_analyze_report_with_model_uses_injected_client(self) -> None:
        """验证模型分析支持注入客户端，并保留模型输出的个股异动。"""
        analysis = {
            "current_status": "持有",
            "conclusion": "牧原股份当前继续维持“持有”框架。",
            "status_changed": "否",
            "change_reason": "",
            "focus_changes": [
                {
                    "name": "5月商品猪销售收入同比下降30.13%",
                    "info": "2026-06-05｜证券时报网｜牧原股份：5月商品猪销售收入85.65亿元 同比下降30.13%",
                    "impact": "收入下滑会影响市场对盈利修复节奏的判断。",
                    "source_link": "",
                }
            ],
        }

        def fake_client(prompt: str) -> str:
            """模拟模型客户端，验证提示词包含原始数据并返回 JSON。"""
            self.assertIn("原始数据", prompt)
            self.assertIn("5月商品猪销售收入85.65亿元 同比下降30.13%", prompt)
            return json.dumps(analysis, ensure_ascii=False)

        context = build_report_context(
            report_date="2026-06-28",
            latest_trade_date="2026-06-27",
            tushare_data={
                "close": 33.56,
                "pct_chg": 3.7083,
                "pe_ttm": 19.81,
                "pb": 2.246,
                "turnover_rate": 2.759,
                "total_mv_billion": 1937.42,
            },
            eastmoney_data=None,
            signal_data={
                "sales_brief": ["2026-06-05｜证券时报网｜牧原股份：5月商品猪销售收入85.65亿元 同比下降30.13%"],
            },
            trend_metrics=[],
            pig_cycle_metrics=[],
        )
        output = analyze_report_with_model(context, analysis_client=fake_client)

        self.assertEqual(output["current_status"], "持有")
        self.assertEqual(output["focus_changes"][0]["name"], "5月商品猪销售收入同比下降30.13%")

    def test_render_email_html_contains_readable_sections(self) -> None:
        """验证 HTML 邮件包含当前状态、个股异动、趋势卡片和完整正文。"""
        analysis = {
            "current_status": "持有",
            "conclusion": "牧原股份当前继续维持“持有”框架。",
            "status_changed": "否",
            "change_reason": "",
            "focus_changes": [
                {
                    "name": "5月商品猪销售收入同比下降30.13%",
                    "info": "2026-06-05｜证券时报网｜牧原股份：5月商品猪销售收入85.65亿元 同比下降30.13%",
                    "impact": "收入下滑会影响市场对盈利修复节奏的判断。",
                    "source_link": "",
                }
            ],
        }
        html = render_email_html(
            subject="牧原股份 2026-06-27 01:32 日复盘",
            markdown_body=(
                "# 2026-06-27 牧原股份 01:32 日复盘\n\n"
                "## 1. 今日核心结论\n\n"
                "- 一句话结论：牧原股份当前继续维持“持有”框架。\n"
                "- 当前状态：持有\n\n"
                "## 3. 行业与周期变化\n\n"
                "- 猪价变化：全国农产品批发市场猪肉平均价格较昨日上行。\n"
                "- 能繁母猪存栏趋势：供给端仍需持续观察。\n\n"
                "## 4. 公司经营变化\n\n"
                "- 月度销售简报：5月商品猪销售收入85.65亿元。\n\n"
                "## 5. 热度与交易层观察\n\n"
                "- 换手率与成交额是否异常：换手率 2.759%。\n"
            ),
            key_metrics={
                "收盘价": "33.56 元",
                "PE(TTM)": "19.81 倍",
                "PB": "2.246 倍",
                "换手率": "2.759%",
            },
            trend_metrics=[
                {
                    "name": "收盘价",
                    "period": "近20交易日",
                    "latest": "33.56 元",
                    "values": [31.1, 31.8, 32.2, 33.0, 33.56],
                    "explanation": "收盘价近20个交易日温和抬升。",
                },
            ],
            analysis=analysis,
            valuation_result=__import__("types").SimpleNamespace(
                valuation_status="合理",
                valuation_summary="当前估值处于合理区间。",
                valuation_method="PE(TTM)+PB+市值快照",
                current_market_cap_billion=1937.42,
                fair_value_range="1800-2100 亿元",
                key_evidence=["Tushare 主数据", "东方财富校验"],
                risk_points=["猪周期波动仍在"],
                missing_data=["历史估值分位"],
                next_questions=["补齐 3 年估值序列"],
                source_list=["Tushare", "东方财富 mx-data"],
            ),
        )

        self.assertIn("<html>", html)
        self.assertIn("牧原股份 2026-06-27 01:32 日复盘", html)
        self.assertIn("个股异动", html)
        self.assertIn("关键指标", html)
        self.assertIn("估值判断", html)
        self.assertIn("当前状态", html)
        self.assertIn("持有", html)
        self.assertIn("5月商品猪销售收入同比下降30.13%", html)
        self.assertIn("异动信息", html)
        self.assertIn("异动影响", html)
        self.assertIn("近20交易日", html)
        self.assertIn("收盘价近20个交易日温和抬升", html)
        self.assertIn("<svg", html)
        self.assertIn("完整复盘正文", html)
        self.assertNotIn("<br>", html)
        self.assertNotIn("关键数据快照", html)

    def test_build_valuation_request_collects_key_evidence(self) -> None:
        """验证估值请求会收集当前市值和外部证据摘要。"""
        request = build_valuation_request(
            report_date="2026-06-28",
            latest_trade_date="2026-06-27",
            tushare_data={
                "close": 33.56,
                "pct_chg": 3.7083,
                "pe_ttm": 19.81,
                "pb": 2.246,
                "turnover_rate": 2.759,
                "total_mv_billion": 1937.42,
            },
            eastmoney_data={
                "total_mv_billion": 1912.0,
                "pe_ttm": 19.81,
                "turnover_rate": 2.759,
            },
            signal_data={
                "announcements": ["2026-06-25：披露月度销售简报"],
                "sales_brief": ["2026-06-25：月度销售简报已披露。"],
            },
            trend_metrics=[],
            pig_cycle_metrics=[
                {
                    "name": "现货生猪",
                    "latest": "9.37 元/公斤",
                    "updated_at": "2026-06-28",
                    "source": {"name": "AkShare"},
                    "explanation": "现货生猪回落。",
                }
            ],
        )

        self.assertIsInstance(request, ValuationRequest)
        self.assertEqual(request.company_name, "牧原股份")
        self.assertEqual(request.current_market_cap_billion, 1937.42)
        self.assertGreaterEqual(len(request.evidence_items), 3)
        self.assertIn("价格与估值快照", request.evidence_items[0].title)

    def test_analyze_valuation_with_model_uses_injected_service(self) -> None:
        """验证估值分析会调用注入的模型服务。"""
        request = ValuationRequest(
            symbol="002714.SZ",
            company_name="牧原股份",
            as_of_date="2026-06-28",
            current_market_cap_billion=1937.42,
            evidence_items=[],
        )
        fake_service = __import__("types").SimpleNamespace(
            complete_json=lambda prompt: {
                "valuation_status": "合理",
                "valuation_summary": "估值处于合理区间。",
                "valuation_method": "快照法",
                "current_market_cap_billion": 1937.42,
                "fair_value_range": "1800-2100 亿元",
                "key_evidence": ["Tushare 主数据"],
                "risk_points": ["猪周期波动"],
                "missing_data": ["历史估值序列"],
                "next_questions": ["补齐历史区间"],
                "source_list": ["Tushare"],
            }
        )

        result = analyze_valuation_with_model(request, model_service=fake_service)

        self.assertEqual(result.valuation_status, "合理")
        self.assertEqual(result.current_market_cap_billion, 1937.42)
        self.assertIn("Tushare 主数据", result.key_evidence)

    def test_render_valuation_markdown_includes_market_cap(self) -> None:
        """验证估值 Markdown 会展示当前市值和关键依据。"""
        request = ValuationRequest(
            symbol="002714.SZ",
            company_name="牧原股份",
            as_of_date="2026-06-28",
            current_market_cap_billion=1937.42,
            evidence_items=[],
        )
        result = __import__("types").SimpleNamespace(
            valuation_status="合理",
            valuation_summary="当前估值处于合理区间。",
            valuation_method="快照法",
            current_market_cap_billion=1937.42,
            fair_value_range="1800-2100 亿元",
            key_evidence=["Tushare 主数据"],
            risk_points=["猪周期波动仍在"],
            missing_data=["历史估值分位"],
            next_questions=["补齐 3 年估值序列"],
            source_list=["Tushare"],
        )

        markdown = render_valuation_markdown(request, result)

        self.assertIn("## 4. 估值分析", markdown)
        self.assertIn("当前市值：1937.42 亿元", markdown)
        self.assertIn("Tushare 主数据", markdown)

    def test_valuation_agent_prefills_snapshot_fields_before_prompt(self) -> None:
        """验证估值 Agent 会先预填稳定快照字段，再交给模型分析。"""
        request = ValuationRequest(
            symbol="002714.SZ",
            company_name="牧原股份",
            as_of_date="2026-06-28",
            evidence_items=[
                __import__("product.agents.agents.valuation.schemas", fromlist=["dummy"]).ValuationEvidenceItem(
                    title="牧原股份价格与估值快照",
                    source="Tushare",
                    date="2026-06-27",
                    content="收盘价 33.56 元，PE(TTM) 19.81 倍，PB 2.246 倍，换手率 2.759%，总市值 1937.42 亿元。",
                )
            ],
        )

        def fake_runner(prompt: str) -> dict[str, object]:
            self.assertIn("Tushare", prompt)
            self.assertIn("33.56 元", prompt)
            self.assertIn('"current_price": 33.56', prompt)
            self.assertIn('"current_market_cap_billion": 1937.42', prompt)
            self.assertNotIn("妙想公开证据", prompt)
            return {
                "valuation_status": "合理",
                "valuation_summary": "估值处于合理区间。",
                "valuation_method": "快照法",
                "current_market_cap_billion": 1937.42,
                "fair_value_range": "1800-2100 亿元",
                "key_evidence": ["Tushare 价格与估值快照"],
                "risk_points": [],
                "missing_data": [],
                "next_questions": [],
                "source_list": ["Tushare"],
            }

        agent = ValuationAgent(model_runner=fake_runner)
        prepared = agent.prepare_request(request)
        self.assertEqual(prepared.request.current_price, 33.56)
        self.assertEqual(prepared.request.pe_ttm, 19.81)
        self.assertEqual(prepared.request.pb, 2.246)
        self.assertEqual(prepared.request.turnover_rate, 2.759)
        self.assertEqual(prepared.request.current_market_cap_billion, 1937.42)
        self.assertTrue(any("预填快照来自 Tushare" in note for note in prepared.notes))
        result = agent.run(request)

        self.assertEqual(result.valuation_status, "合理")

    def test_valuation_research_coordinator_runs_multi_round_loop(self) -> None:
        """验证多 Agent 协调器会在补数后进入收敛轮次。"""
        sequence = [
            {
                "valuation_status": "数据不足",
                "valuation_summary": "缺少历史估值分位。",
                "valuation_method": "快照法",
                "current_market_cap_billion": 1937.42,
                "fair_value_range": "暂无",
                "key_evidence": ["Tushare 快照"],
                "risk_points": [],
                "missing_data": ["历史估值分位"],
                "next_questions": ["补充历史估值分位"],
                "source_list": ["Tushare"],
                "data_needs": [
                    {
                        "title": "历史估值分位",
                        "query": "牧原股份近三年PE TTM PB历史区间",
                        "required": True,
                        "preferred_sources": ["websearch-deepseek"],
                        "rationale": "判断当前估值位置",
                        "fallback_queries": ["牧原股份 估值 历史区间"],
                    }
                ],
                "can_conclude": False,
                "blocked_reason": "",
            },
            {
                "valuation_status": "合理",
                "valuation_summary": "历史估值分位已补充，当前处于合理区间。",
                "valuation_method": "快照法 + 历史分位对照",
                "current_market_cap_billion": 1937.42,
                "fair_value_range": "1800-2100 亿元",
                "key_evidence": ["Tushare 快照", "网页搜索证据"],
                "risk_points": [],
                "missing_data": [],
                "next_questions": [],
                "source_list": ["Tushare", "网页搜索"],
                "data_needs": [],
                "can_conclude": True,
                "blocked_reason": "",
            },
        ]

        def fake_runner(prompt: str) -> dict[str, object]:
            return sequence.pop(0)

        valuation_agent = ValuationAgent(model_runner=fake_runner)
        data_agent = DataAcquisitionAgent(
            providers=[
                __import__("product.agents.agents.valuation.providers", fromlist=["dummy"]).WebSearchDeepseekEvidenceProvider(
                    command="websearch-deepseek",
                    api_key="deepseek-key",
                    timeout_seconds=5,
                )
            ]
        )
        coordinator = ValuationResearchCoordinator(
            valuation_agent=valuation_agent,
            data_agent=data_agent,
            max_rounds=5,
        )

        with patch(
            "product.agents.agents.valuation.providers._call_websearch_deepseek",
            return_value=[
                "## Search Results Summary\n牧原股份近三年估值处于区间中部。\n\n### Sources (1):\n1. [历史估值区间](https://example.com/valuation)",
                [{"title": "历史估值区间", "url": "https://example.com/valuation"}],
            ],
        ):
            outcome = coordinator.run(
                ValuationRequest(
                    symbol="002714.SZ",
                    company_name="牧原股份",
                    as_of_date="2026-06-28",
                )
            )

        self.assertEqual(outcome.final_result.valuation_status, "合理")
        self.assertEqual(len(outcome.rounds), 2)
        self.assertEqual(outcome.termination_reason, "估值结论已收敛")
        self.assertEqual(outcome.rounds[0].acquisition_attempts[0].provider_name, "websearch-deepseek")
        self.assertEqual(outcome.rounds[0].acquisition_attempts[0].status, "success")
        self.assertEqual(outcome.rounds[0].request_snapshot["round_index"], 1)
        self.assertEqual(outcome.rounds[0].request_snapshot["company_name"], "牧原股份")

    def test_mx_search_provider_is_registered_as_independent_source(self) -> None:
        """验证 mx-search 会作为独立 provider 命中，而不是映射到 mx-data。"""
        sequence = [
            {
                "valuation_status": "数据不足",
                "valuation_summary": "仍需资讯补充",
                "valuation_method": "快照法",
                "current_market_cap_billion": 1.0,
                "fair_value_range": "暂无",
                "key_evidence": [],
                "risk_points": [],
                "missing_data": [],
                "next_questions": [],
                "source_list": [],
                "data_needs": [
                    {
                        "title": "公告资讯",
                        "query": "牧原股份最新公告",
                        "required": True,
                        "preferred_sources": ["mx-search"],
                        "rationale": "验证资讯搜索链路",
                        "fallback_queries": [],
                    }
                ],
                "can_conclude": False,
                "blocked_reason": "",
            },
            {
                "valuation_status": "合理",
                "valuation_summary": "资讯已补充。",
                "valuation_method": "快照法",
                "current_market_cap_billion": 1.0,
                "fair_value_range": "暂无",
                "key_evidence": [],
                "risk_points": [],
                "missing_data": [],
                "next_questions": [],
                "source_list": ["资讯"],
                "data_needs": [],
                "can_conclude": True,
                "blocked_reason": "",
            },
        ]

        def fake_runner(prompt: str) -> dict[str, object]:
            return sequence.pop(0)

        valuation_agent = ValuationAgent(model_runner=fake_runner)
        data_agent = DataAcquisitionAgent(providers=[MxSearchEvidenceProvider(api_key="mx")])
        coordinator = ValuationResearchCoordinator(
            valuation_agent=valuation_agent,
            data_agent=data_agent,
            max_rounds=5,
        )

        with patch(
            "product.data.adapters.mx_skills.query_mx_finance_news_summary",
            return_value=["2026-07-05｜资讯｜牧原股份最新公告"],
        ):
            outcome = coordinator.run(
                ValuationRequest(
                    symbol="002714.SZ",
                    company_name="牧原股份",
                    as_of_date="2026-07-05",
                    evidence_items=[],
                    peer_notes=[],
                    round_index=1,
                    max_rounds=5,
                )
            )

        self.assertEqual(outcome.rounds[0].acquisition_attempts[0].provider_name, "mx-search")
        self.assertEqual(outcome.rounds[0].acquisition_attempts[0].status, "success")
        self.assertEqual(outcome.rounds[0].added_evidence[0].source, "资讯")
        self.assertEqual(outcome.rounds[0].added_evidence[0].date, "2026-07-05")

    def test_mx_data_provider_uses_released_skill_snapshot_wrapper(self) -> None:
        """验证 mx-data provider 会复用仓库固化的快照 wrapper。"""
        data_agent = DataAcquisitionAgent(providers=[MxDataEvidenceProvider(api_key="mx")])
        request = ValuationRequest(
            symbol="002714.SZ",
            company_name="牧原股份",
            as_of_date="2026-07-22",
            evidence_items=[],
            peer_notes=[],
            round_index=1,
            max_rounds=5,
        )
        need = ValuationDataNeed(
            title="最新一致市值与PE",
            query="牧原股份最新PE PB 换手率 总市值",
            required=True,
            preferred_sources=["mx-data"],
            rationale="验证 snapshot wrapper",
            fallback_queries=[],
        )

        with patch(
            "product.data.adapters.mx_skills.query_mx_finance_snapshot",
            return_value=("2026-07-15", {
                "pe_ttm": 17.74,
                "pb": 2.654,
                "turnover_rate": 0.66,
                "total_mv_billion": 1934.0,
            }),
        ):
            batch = data_agent.collect(request, [need], full_channel_expansion=False)

        self.assertEqual(batch.attempts[0].provider_name, "mx-data")
        self.assertEqual(batch.attempts[0].status, "success")
        self.assertEqual(batch.items[0].source, "东方财富妙想 mx-data")
        self.assertIn("17.74 倍", batch.items[0].content)

    def test_mx_search_provider_uses_released_skill_news_wrapper(self) -> None:
        """验证 mx-search provider 会复用仓库固化的新闻 wrapper。"""
        data_agent = DataAcquisitionAgent(providers=[MxSearchEvidenceProvider(api_key="mx")])
        request = ValuationRequest(
            symbol="002714.SZ",
            company_name="牧原股份",
            as_of_date="2026-07-22",
            evidence_items=[],
            peer_notes=[],
            round_index=1,
            max_rounds=5,
        )
        need = ValuationDataNeed(
            title="公告资讯",
            query="牧原股份 最新公告 重大事项",
            required=True,
            preferred_sources=["mx-search"],
            rationale="验证 news wrapper",
            fallback_queries=[],
        )

        with patch(
            "product.data.adapters.mx_skills.query_mx_finance_news_summary",
            return_value=[
                "2026-07-21｜NOTICE｜牧原股份:关于公司董事和高级管理人员加快实施增持股份计划暨实施结果公告",
                "2026-07-18｜NOTICE｜牧原股份:关于2026年度第四期科技创新债券(乡村振兴)发行结果的公告",
            ],
        ):
            batch = data_agent.collect(request, [need], full_channel_expansion=False)

        self.assertEqual(batch.attempts[0].provider_name, "mx-search")
        self.assertEqual(batch.attempts[0].status, "success")
        self.assertEqual([item.source for item in batch.items], ["NOTICE", "NOTICE"])
        self.assertEqual(batch.items[0].date, "2026-07-21")

    def test_akshare_provider_is_registered_as_independent_source(self) -> None:
        """验证 akshare 会作为独立 provider 命中，而不是依赖 data 层。"""
        sequence = [
            {
                "valuation_status": "数据不足",
                "valuation_summary": "仍需 AkShare 补充",
                "valuation_method": "快照法",
                "current_market_cap_billion": 1.0,
                "fair_value_range": "暂无",
                "key_evidence": [],
                "risk_points": [],
                "missing_data": [],
                "next_questions": [],
                "source_list": [],
                "data_needs": [
                    {
                        "title": "历史股价与市值",
                        "query": "牧原股份股价市值历史走势",
                        "required": True,
                        "preferred_sources": ["akshare"],
                        "rationale": "验证 AkShare 链路",
                        "fallback_queries": [],
                    }
                ],
                "can_conclude": False,
                "blocked_reason": "",
            },
            {
                "valuation_status": "合理",
                "valuation_summary": "AkShare 数据已补充。",
                "valuation_method": "快照法",
                "current_market_cap_billion": 1.0,
                "fair_value_range": "暂无",
                "key_evidence": [],
                "risk_points": [],
                "missing_data": [],
                "next_questions": [],
                "source_list": ["AkShare"],
                "data_needs": [],
                "can_conclude": True,
                "blocked_reason": "",
            },
        ]

        def fake_runner(prompt: str) -> dict[str, object]:
            return sequence.pop(0)

        valuation_agent = ValuationAgent(model_runner=fake_runner)
        data_agent = DataAcquisitionAgent(providers=[AkShareEvidenceProvider()])
        coordinator = ValuationResearchCoordinator(
            valuation_agent=valuation_agent,
            data_agent=data_agent,
            max_rounds=5,
        )

        with patch(
            "product.agents.agents.valuation.providers._extract_stock_history_points",
            return_value=[{"date": "2026-07-05", "close": 36.9, "pct_chg": -1.2}],
        ), patch(
            "product.agents.agents.valuation.providers._extract_stock_individual_info",
            return_value={"总市值": "2130.24亿元", "流通市值": "1850.00亿元", "行业": "农林牧渔"},
        ):
            outcome = coordinator.run(
                ValuationRequest(
                    symbol="002714.SZ",
                    company_name="牧原股份",
                    as_of_date="2026-07-05",
                    evidence_items=[],
                    peer_notes=[],
                    round_index=1,
                    max_rounds=5,
                )
            )

        self.assertEqual(outcome.rounds[0].acquisition_attempts[0].provider_name, "akshare")
        self.assertEqual(outcome.rounds[0].acquisition_attempts[0].status, "success")
        self.assertEqual([item.source for item in outcome.rounds[0].added_evidence], ["AkShare stock_zh_a_hist", "AkShare stock_individual_info_em"])
        self.assertEqual([item.title for item in outcome.rounds[0].added_evidence], ["牧原股份 AkShare 行情", "牧原股份 AkShare 概览"])

    def test_websearch_deepseek_provider_is_registered_as_independent_source(self) -> None:
        """验证 websearch-deepseek 会作为独立 provider 命中，而不是回退到通用网页搜索。"""
        sequence = [
            {
                "valuation_status": "数据不足",
                "valuation_summary": "仍需联网补充",
                "valuation_method": "快照法",
                "current_market_cap_billion": 1.0,
                "fair_value_range": "暂无",
                "key_evidence": [],
                "risk_points": [],
                "missing_data": [],
                "next_questions": [],
                "source_list": [],
                "data_needs": [
                    {
                        "title": "实时公告",
                        "query": "牧原股份 最新公告 研报",
                        "required": True,
                        "preferred_sources": ["websearch-deepseek"],
                        "rationale": "验证 websearch-deepseek 链路",
                        "fallback_queries": [],
                    }
                ],
                "can_conclude": False,
                "blocked_reason": "",
            },
            {
                "valuation_status": "合理",
                "valuation_summary": "联网补充完成。",
                "valuation_method": "快照法",
                "current_market_cap_billion": 1.0,
                "fair_value_range": "暂无",
                "key_evidence": [],
                "risk_points": [],
                "missing_data": [],
                "next_questions": [],
                "source_list": ["联网搜索"],
                "data_needs": [],
                "can_conclude": True,
                "blocked_reason": "",
            },
        ]

        def fake_runner(prompt: str) -> dict[str, object]:
            return sequence.pop(0)

        valuation_agent = ValuationAgent(model_runner=fake_runner)
        data_agent = DataAcquisitionAgent(
            providers=[
                WebSearchDeepseekEvidenceProvider(
                    command="websearch-deepseek",
                    api_key="deepseek-key",
                    timeout_seconds=5,
                )
            ]
        )
        coordinator = ValuationResearchCoordinator(
            valuation_agent=valuation_agent,
            data_agent=data_agent,
            max_rounds=5,
        )

        with patch(
            "product.agents.agents.valuation.providers._call_websearch_deepseek",
            return_value=(
                "## Search Results Summary\n牧原股份最新公告显示经营数据持续披露。\n\n### Sources (1):\n1. [牧原股份公告](https://example.com/muyuan-news)",
                [{"title": "牧原股份公告", "url": "https://example.com/muyuan-news"}],
            ),
        ):
            outcome = coordinator.run(
                ValuationRequest(
                    symbol="002714.SZ",
                    company_name="牧原股份",
                    as_of_date="2026-07-05",
                    evidence_items=[],
                    peer_notes=[],
                    round_index=1,
                    max_rounds=5,
                )
            )

        self.assertEqual(outcome.rounds[0].acquisition_attempts[0].provider_name, "websearch-deepseek")
        self.assertEqual(outcome.rounds[0].acquisition_attempts[0].status, "success")
        self.assertEqual(outcome.rounds[0].added_evidence[0].source, "websearch-deepseek")
        self.assertEqual(outcome.rounds[0].added_evidence[0].url, "https://example.com/muyuan-news")

    def test_data_acquisition_agent_collects_multiple_sources_for_same_need(self) -> None:
        """验证同一数据诉求可同时收集多个 provider 的证据。"""

        class FakeProvider:
            """用于验证采集器多源累积逻辑的假 provider。"""

            def __init__(self, name: str, content: str) -> None:
                self.name = name
                self.content = content

            def fetch(self, request: ValuationRequest, need: ValuationDataNeed):
                """返回一条固定证据，模拟多源并行补数。"""
                from product.agents.agents.valuation.schemas import ValuationEvidenceItem

                return [
                    ValuationEvidenceItem(
                        title=need.title,
                        source=self.name,
                        date=request.as_of_date,
                        content=self.content,
                    )
                ]

        agent = DataAcquisitionAgent(
            providers=[
                FakeProvider("source-a", "A 证据"),
                FakeProvider("source-b", "B 证据"),
            ]
        )
        request = ValuationRequest(
            symbol="002714.SZ",
            company_name="牧原股份",
            as_of_date="2026-07-05",
            evidence_items=[],
            peer_notes=[],
            round_index=1,
            max_rounds=5,
        )
        need = ValuationDataNeed(
            title="同一数据项",
            query="牧原股份当前估值",
            required=True,
            preferred_sources=["source-a", "source-b"],
            rationale="验证多源累积",
            fallback_queries=[],
        )

        batch = agent.collect(request, [need], full_channel_expansion=False)

        self.assertEqual(len(batch.items), 2)
        self.assertEqual([item.source for item in batch.items], ["source-a", "source-b"])
        self.assertEqual(len(batch.attempts), 2)
        self.assertEqual(batch.attempts[0].provider_name, "source-a")
        self.assertEqual(batch.attempts[1].provider_name, "source-b")
        self.assertEqual(batch.failed_sources, [])

    def test_data_acquisition_agent_enables_full_scan_from_third_round(self) -> None:
        """验证第三轮及之后会自动补齐剩余 provider，进入全渠道扫描。"""

        class FakeProvider:
            """用于验证第三轮全渠道扫描的假 provider。"""

            def __init__(self, name: str) -> None:
                self.name = name

            def fetch(self, request: ValuationRequest, need: ValuationDataNeed):
                """返回一条固定证据，便于确认所有渠道都会被调用。"""
                from product.agents.agents.valuation.schemas import ValuationEvidenceItem

                return [
                    ValuationEvidenceItem(
                        title=need.title,
                        source=self.name,
                        date=request.as_of_date,
                        content=f"{self.name} 证据",
                    )
                ]

        agent = DataAcquisitionAgent(
            providers=[
                FakeProvider("source-a"),
                FakeProvider("source-b"),
                FakeProvider("source-c"),
            ]
        )
        request = ValuationRequest(
            symbol="002714.SZ",
            company_name="牧原股份",
            as_of_date="2026-07-05",
            evidence_items=[],
            peer_notes=[],
            round_index=3,
            max_rounds=5,
        )
        need = ValuationDataNeed(
            title="全渠道扫描",
            query="牧原股份历史估值分位",
            required=True,
            preferred_sources=["source-a"],
            rationale="验证第三轮全渠道补数",
            fallback_queries=[],
        )

        batch = agent.collect(request, [need], full_channel_expansion=True)

        self.assertEqual([item.source for item in batch.items], ["source-a", "source-b", "source-c"])
        self.assertEqual([attempt.provider_name for attempt in batch.attempts], ["source-a", "source-b", "source-c"])
        self.assertEqual(batch.failed_sources, [])

    def test_data_acquisition_agent_preserves_duplicate_metrics_as_raw_evidence(self) -> None:
        """验证同一指标在多渠道取数后会保留为原始证据，交由模型统一处理。"""

        class FakeProvider:
            """返回固定证据的假 provider。"""

            def __init__(self, name: str, source_name: str, content: str) -> None:
                self.name = name
                self.source_name = source_name
                self.content = content

            def fetch(self, request: ValuationRequest, need: ValuationDataNeed):
                """返回一条同时包含多个指标的证据。"""
                return [
                    __import__("product.agents.agents.valuation.schemas", fromlist=["dummy"]).ValuationEvidenceItem(
                        title=need.title,
                        source=self.source_name,
                        date=request.as_of_date,
                        content=self.content,
                    )
                ]

        agent = DataAcquisitionAgent(
            providers=[
                FakeProvider(
                    "source-a",
                    "Tushare",
                    "收盘价 33.56 元，PE(TTM) 21.78 倍，PB 2.47 倍，换手率 2.10%，总市值 2130.00 亿元。",
                ),
                FakeProvider(
                    "source-b",
                    "AkShare stock_zh_a_hist",
                    "收盘价 33.58 元，PE(TTM) 21.80 倍，PB 2.46 倍，换手率 2.08%，总市值 2131.50 亿元。",
                ),
                FakeProvider(
                    "source-c",
                    "东方财富妙想 mx-search",
                    "收盘价 33.57 元，PE(TTM) 21.79 倍，PB 2.48 倍，换手率 2.11%，总市值 2129.20 亿元（来源：牧原股份公告）。",
                ),
            ]
        )
        request = ValuationRequest(
            symbol="002714.SZ",
            company_name="牧原股份",
            as_of_date="2026-07-05",
            evidence_items=[],
            peer_notes=[],
            round_index=1,
            max_rounds=5,
        )
        need = ValuationDataNeed(
            title="价格与估值快照",
            query="牧原股份 PE PB 收盘价 总市值",
            required=True,
            preferred_sources=["source-a", "source-b", "source-c"],
            rationale="验证汇总逻辑",
            fallback_queries=[],
        )

        batch = agent.collect(request, [need], full_channel_expansion=False)
        self.assertEqual(len(batch.items), 3)
        self.assertEqual([item.source for item in batch.items], ["Tushare", "AkShare stock_zh_a_hist", "东方财富妙想 mx-search"])
        self.assertEqual([item.title for item in batch.items], ["价格与估值快照", "价格与估值快照", "价格与估值快照"])
        self.assertTrue(any("原始证据已保留" in note for note in batch.notes))

    def test_data_acquisition_agent_keeps_conflicting_metrics_as_raw_evidence(self) -> None:
        """验证发生冲突时也只保留原始证据，不在代码层做裁决。"""

        class FakeProvider:
            """返回固定证据的假 provider。"""

            def __init__(self, name: str, source_name: str, content: str) -> None:
                self.name = name
                self.source_name = source_name
                self.content = content

            def fetch(self, request: ValuationRequest, need: ValuationDataNeed):
                """返回一条固定证据。"""
                return [
                    __import__("product.agents.agents.valuation.schemas", fromlist=["dummy"]).ValuationEvidenceItem(
                        title=need.title,
                        source=self.source_name,
                        date=request.as_of_date,
                        content=self.content,
                    )
                ]

        agent = DataAcquisitionAgent(
            providers=[
                FakeProvider(
                    "source-a",
                    "Tushare",
                    "PE(TTM) 21.78 倍，收盘价 33.56 元，总市值 2130.00 亿元。",
                ),
                FakeProvider(
                    "source-b",
                    "websearch-deepseek",
                    "PE(TTM) 28.90 倍，收盘价 37.20 元，总市值 2400.00 亿元（来源：证券时报）。",
                ),
            ]
        )
        request = ValuationRequest(
            symbol="002714.SZ",
            company_name="牧原股份",
            as_of_date="2026-07-05",
            evidence_items=[],
            peer_notes=[],
            round_index=1,
            max_rounds=5,
        )
        need = ValuationDataNeed(
            title="冲突数据",
            query="牧原股份 PE 收盘价 总市值",
            required=True,
            preferred_sources=["source-a", "source-b"],
            rationale="验证冲突优先级",
            fallback_queries=[],
        )

        batch = agent.collect(request, [need], full_channel_expansion=False)
        self.assertEqual(len(batch.items), 2)
        self.assertEqual([item.source for item in batch.items], ["Tushare", "websearch-deepseek"])
        self.assertEqual([item.title for item in batch.items], ["冲突数据", "冲突数据"])
        self.assertTrue(any("原始证据已保留" in note for note in batch.notes))

    def test_run_report_workflow_async_invokes_email_callback_after_success(self) -> None:
        """验证异步日报工作流会在模型成功后触发邮件回调。"""
        from product.app.backend.application.reports.muyuan_nightly import run_report_workflow_async

        fake_report_context = {
            "latest_trade_date": "2026-06-27",
            "tushare_data": {
                "close": 1.0,
                "pct_chg": 2.0,
                "pe_ttm": 3.0,
                "pb": 4.0,
                "turnover_rate": 5.0,
                "total_mv_billion": 6.0,
            },
            "eastmoney_data": None,
            "signal_data": {},
            "trend_metrics": [],
            "pig_cycle_metrics": [],
            "analysis": {
                "current_status": "持有",
                "conclusion": "保持持有",
                "status_changed": "否",
                "change_reason": "",
                "focus_changes": [],
            },
            "valuation_request": __import__("types").SimpleNamespace(),
            "valuation_result": __import__("types").SimpleNamespace(
                valuation_status="合理",
                valuation_summary="估值处于合理区间。",
                valuation_method="快照法",
                current_market_cap_billion=6.0,
                fair_value_range="5-7 亿元",
                key_evidence=[],
                risk_points=[],
                missing_data=[],
                next_questions=[],
                source_list=[],
            ),
        }

        callback_calls: list[dict[str, str]] = []

        def fake_generate_report(report_date: str, force: bool = False):
            return __import__("pathlib").Path("/tmp/fake.md"), "markdown-body", fake_report_context

        async def runner() -> tuple[Path, str, dict[str, object]]:
            with (
                patch("product.app.backend.application.reports.muyuan_nightly.generate_report", side_effect=fake_generate_report),
            ):
                async def callback(**kwargs: object) -> None:
                    callback_calls.append({"recipient": str(kwargs["recipient"]), "subject": str(kwargs["subject"])})

                return await run_report_workflow_async(
                    report_date="2026-06-27",
                    recipient="demo@example.com",
                    email_callback=callback,
                )

        output_path, content, report_context = asyncio.run(runner())

        self.assertEqual(output_path.as_posix(), "/tmp/fake.md")
        self.assertEqual(content, "markdown-body")
        self.assertEqual(report_context["analysis"]["current_status"], "持有")
        self.assertEqual(callback_calls[0]["recipient"], "demo@example.com")
        self.assertIn("牧原股份", callback_calls[0]["subject"])


class PrivateConfigTests(unittest.TestCase):
    """私密配置读取测试。"""

    def test_load_private_config_reads_repo_local_toml(self) -> None:
        """验证仓库内的 private.local.toml 能被直接读取。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "private.local.toml"
            config_path.write_text(
                """
[smtp]
password = "secret-value"

[secrets]
deepseek_api_key = "hidden-key"
tushare_token = "token-value"

[mysql]
user = "db-user"
password = "db-password"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            config = load_private_config(config_path=config_path)

        self.assertEqual(config.smtp_password, "secret-value")
        self.assertEqual(config.secrets.deepseek_api_key, "hidden-key")
        self.assertEqual(config.secrets.tushare_token, "token-value")
        self.assertEqual(config.mysql.user, "db-user")
        self.assertEqual(config.mysql.password, "db-password")
        self.assertEqual(config.raw["secrets"]["deepseek_api_key"], "hidden-key")

    def test_load_private_config_rejects_blank_required_values(self) -> None:
        """验证私密配置的必填项留空时会直接报错并阻断启动。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "private.local.toml"
            config_path.write_text(
                """
[smtp]
password = ""

[secrets]
deepseek_api_key = ""
tushare_token = "token-value"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "smtp.password"):
                load_private_config(config_path=config_path)

    def test_build_email_message_includes_from_header(self) -> None:
        """验证邮件内容会写入 From 头，便于 SMTP 账号和发件人保持一致。"""
        message = build_email_message(
            recipient="376597874@qq.com",
            subject="牧原股份 2026-06-27 01:32 日复盘",
            text_body="纯文本版本",
            html_body="<html><body><h1>HTML版本</h1></body></html>",
        )

        self.assertIn("From:", message)
        self.assertIn("Content-Type: multipart/alternative;", message)
        self.assertIn("Content-Type: text/plain; charset=UTF-8", message)
        self.assertIn("Content-Type: text/html; charset=UTF-8", message)
        self.assertIn("HTML版本", message)

    def test_send_email_uses_smtp_settings_from_private_config(self) -> None:
        """验证发信逻辑会走 Python SMTP 客户端，而不是依赖环境变量或 msmtp。"""
        smtp_mock = patch("product.app.backend.application.reports.muyuan_nightly.load_private_config").start()
        smtp_mock.return_value = __import__("types").SimpleNamespace(
            smtp_password="secret-value",
            raw={},
        )
        self.addCleanup(patch.stopall)

        with patch("product.app.backend.application.reports.muyuan_nightly.smtplib.SMTP_SSL") as mock_smtp_ssl:
            smtp_instance = mock_smtp_ssl.return_value
            with patch(
                "product.app.backend.application.reports.muyuan_nightly.PROJECT_CONFIG",
                __import__("types").SimpleNamespace(
                    smtp=__import__("types").SimpleNamespace(
                        host="smtp.example.com",
                        port=465,
                        user="sender@example.com",
                        from_addr="sender@example.com",
                    )
                ),
            ):
                from product.app.backend.application.reports.muyuan_nightly import send_email

                send_email(
                    recipient="376597874@qq.com",
                    subject="牧原股份 2026-06-27 01:32 日复盘",
                    text_body="纯文本版本",
                    html_body="<html><body><h1>HTML版本</h1></body></html>",
                )

        mock_smtp_ssl.assert_called_once_with("smtp.example.com", 465, timeout=30)
        smtp_instance.login.assert_called_once_with("sender@example.com", "secret-value")
        smtp_instance.sendmail.assert_called_once()

    def test_generate_report_uses_runtime_model_config(self) -> None:
        """验证生成日报时会使用项目配置构建模型服务。"""
        fake_context = {
            "analysis": {
                "current_status": "持有",
                "conclusion": "保持持有",
                "status_changed": "否",
                "change_reason": "",
                "focus_changes": [],
            }
        }

        fake_service = type(
            "FakeModelService",
            (),
            {"runtime": type("Runtime", (), {"profile": "current", "provider": "codex"})()},
        )()

        with (
            patch("product.app.backend.application.reports.muyuan_nightly.get_tushare_snapshot", return_value=("2026-06-27", {"close": 1.0, "pct_chg": 2.0, "pe_ttm": 3.0, "pb": 4.0, "turnover_rate": 5.0, "total_mv_billion": 6.0})),
            patch("product.app.backend.application.reports.muyuan_nightly.get_eastmoney_snapshot", return_value=None),
            patch("product.app.backend.application.reports.muyuan_nightly.get_signal_data", return_value={}),
            patch("product.app.backend.application.reports.muyuan_nightly.get_tushare_trend_metrics", return_value=[]),
            patch("product.app.backend.application.reports.muyuan_nightly.get_hog_cycle_metrics", return_value=[]),
            patch("product.app.backend.application.reports.muyuan_nightly.ModelService.from_project_config", return_value=fake_service) as mock_from_project_config,
            patch("product.app.backend.application.reports.muyuan_nightly.analyze_report_with_model", return_value=fake_context["analysis"]) as mock_analyze,
            patch("product.app.backend.application.reports.muyuan_nightly.analyze_valuation_with_model", return_value=__import__("types").SimpleNamespace(
                valuation_status="合理",
                valuation_summary="保持合理区间。",
                valuation_method="快照法",
                current_market_cap_billion=6.0,
                fair_value_range="5-7 亿元",
                key_evidence=[],
                risk_points=[],
                missing_data=[],
                next_questions=[],
                source_list=[],
            )) as mock_valuation,
            patch("product.app.backend.application.reports.muyuan_nightly.write_report", return_value=__import__("pathlib").Path("/tmp/fake.md")),
        ):
            output_path, content, report_context = generate_report("2026-06-27", force=True)

        self.assertEqual(output_path.as_posix(), "/tmp/fake.md")
        self.assertIn("保持持有", content)
        self.assertEqual(report_context["analysis"]["current_status"], "持有")
        self.assertEqual(report_context["valuation_result"].valuation_status, "合理")
        self.assertIs(mock_analyze.call_args.kwargs["model_service"], fake_service)
        mock_from_project_config.assert_called_once()
        mock_valuation.assert_called_once()

    def test_sync_private_secrets_to_runtime_env_exports_agents_keys(self) -> None:
        """验证日报流程会把 app 私密配置中的可复用密钥同步到进程环境。"""
        private_config = __import__("types").SimpleNamespace(
            raw={
                "secrets": {
                    "deepseek_api_key": "deepseek-secret",
                    "tushare_token": "tushare-secret",
                    "mx_api_key": "mx-secret",
                    "websearch_api_key": "websearch-secret",
                }
            }
        )

        with patch.dict(os.environ, {"WEBSEARCH_API_KEY": "keep-existing"}, clear=True):
            synced_env_names = _sync_private_secrets_to_runtime_env(private_config)

            self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "deepseek-secret")
            self.assertEqual(os.environ["TUSHARE_TOKEN"], "tushare-secret")
            self.assertEqual(os.environ["TS_TOKEN"], "tushare-secret")
            self.assertEqual(os.environ["MX_APIKEY"], "mx-secret")
            self.assertEqual(os.environ["WEBSEARCH_API_KEY"], "keep-existing")

        self.assertEqual(
            synced_env_names,
            ["DEEPSEEK_API_KEY", "TUSHARE_TOKEN", "TS_TOKEN", "MX_APIKEY"],
        )


class MxSearchSummaryTests(unittest.TestCase):
    """妙想搜索结果摘要解析测试。"""

    def test_summarize_mx_search_output_extracts_titles_and_sources(self) -> None:
        """验证文本格式搜索结果能提取日期、来源和标题。"""
        raw = """
标题：牧原股份：关于2026年5月份生猪销售情况的简报
来源：巨潮资讯
日期：2026-06-05
内容：公司披露月度销售情况。

标题：农业农村部发布生猪生产有关情况
来源：农业农村部
日期：2026-06-20
内容：行业供给仍需观察。
"""
        lines = summarize_mx_search_output(raw, limit=2)
        self.assertEqual(
            lines,
            [
                "2026-06-05｜巨潮资讯｜牧原股份：关于2026年5月份生猪销售情况的简报",
                "2026-06-20｜农业农村部｜农业农村部发布生猪生产有关情况",
            ],
        )

    def test_summarize_mx_search_output_reads_json_payload(self) -> None:
        """验证 JSON 格式搜索结果能提取日期、来源和标题。"""
        raw = """
{"data":[{"title":"牧原股份:2026年5月份销售简报","date":"2026-06-06 00:00:00","source":"上海证券报"},{"title":"农业农村部：全国农产品批发市场猪肉平均价格为14.48元/公斤 比昨天上升0.3%","date":"2026-06-26 14:45:54","source":"每日经济新闻"}]}
"""
        lines = summarize_mx_search_output(raw, limit=2)
        self.assertEqual(
            lines,
            [
                "2026-06-06｜上海证券报｜牧原股份:2026年5月份销售简报",
                "2026-06-26｜每日经济新闻｜农业农村部：全国农产品批发市场猪肉平均价格为14.48元/公斤 比昨天上升0.3%",
            ],
        )


class MuyuanNightlyLaunchdTests(unittest.TestCase):
    """日报定时任务配置测试。"""

    def test_render_launchd_plist_contains_schedule_and_command(self) -> None:
        """验证 launchd plist 包含调度时间、脚本路径和收件人。"""
        plist = render_launchd_plist(
            python_path="/usr/bin/python3",
            project_root="/tmp/a_stock",
            recipient="376597874@qq.com",
            hour=23,
            minute=20,
            label="com.astock.muyuan-nightly",
        )

        self.assertIn("<string>com.astock.muyuan-nightly</string>", plist)
        self.assertIn("<integer>23</integer>", plist)
        self.assertIn("<integer>20</integer>", plist)
        self.assertIn("<string>/usr/bin/python3</string>", plist)
        self.assertIn("<string>/tmp/a_stock/product/app/backend/application/reports/muyuan_nightly.py</string>", plist)
        self.assertIn("<string>376597874@qq.com</string>", plist)

    def test_build_email_subject(self) -> None:
        """验证日报邮件标题包含标的、日期和复盘时间。"""
        project_config = load_project_config()
        expected_clock = f"{project_config.launchd.hour:02d}:{project_config.launchd.minute:02d}"
        self.assertEqual(
            build_email_subject("2026-06-27"),
            f"牧原股份 2026-06-27 {expected_clock} 日复盘",
        )


class EastmoneyParsingTests(unittest.TestCase):
    """东方财富 mx-data 输出解析测试。"""

    def test_parse_eastmoney_stdout_uses_first_a_share_table_row(self) -> None:
        """验证解析器使用第一条 A 股表格数据作为校验快照。"""
        stdout = """
**牧原股份(002714.SZ)的总市值(证监会算法)、市盈率PE(TTM)等** (前20行预览):

| date | 总市值(证监会算法) | 市盈率PE(TTM) | 换手率 |
| --- | --- | --- | --- |
| 2026-06-26(日) | 1912亿 | 19.81倍 | 2.759% |
| 2026-06-25(日) | 1843亿 | 19.1倍 | 1.162% |
"""
        parsed = parse_eastmoney_stdout(stdout)
        self.assertEqual(
            parsed,
            {
                "total_mv_billion": 1912.0,
                "pe_ttm": 19.81,
                "turnover_rate": 2.759,
            },
        )

    def test_parse_eastmoney_stdout_supports_table_with_pb_column(self) -> None:
        """验证包含 PB 列的表格仍能正确定位 PE、换手率和市值。"""
        stdout = """
**牧原股份(002714.SZ)的总市值、市净率PB等** (前20行预览):

| date | 总市值 | 市净率PB | 市盈率PE(TTM) | 换手率 |
| --- | --- | --- | --- | --- |
| 2026-06-26(日) | 1937亿 | 2.246倍 | 19.81倍 | 2.759% |
"""
        parsed = parse_eastmoney_stdout(stdout)
        self.assertEqual(
            parsed,
            {
                "total_mv_billion": 1937.0,
                "pe_ttm": 19.81,
                "turnover_rate": 2.759,
            },
        )


if __name__ == "__main__":
    unittest.main()
