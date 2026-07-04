"""牧原股份夜间复盘任务测试。

职责：
- 验证日报 Markdown、HTML 邮件、模型分析、launchd 配置和东方财富解析。
- 保护“代码做确定性流转，分析判断由模型驱动”的任务链路边界。
"""

import unittest
import json
import os
from unittest.mock import patch

from product.jobs.muyuan_nightly import (
    build_email_subject,
    build_email_message,
    build_codex_exec_command,
    build_focus_changes,
    build_sparkline_svg,
    analyze_report_with_model,
    build_report_context,
    generate_report,
    load_model_runtime_config,
    parse_eastmoney_stdout,
    render_email_html,
    render_launchd_plist,
    render_report_markdown,
    summarize_mx_search_output,
)


class MuyuanNightlyReportTests(unittest.TestCase):
    """Markdown 日报渲染测试。"""

    def test_render_report_includes_key_metrics_and_sources(self) -> None:
        """验证日报包含关键指标、主来源和校验来源。"""
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

        self.assertIn("# 2026-06-27 牧原股份 21:00 日复盘", markdown)
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
            subject="牧原股份 2026-06-27 21:00 日复盘",
            markdown_body=(
                "# 2026-06-27 牧原股份 21:00 日复盘\n\n"
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
        )

        self.assertIn("<html>", html)
        self.assertIn("牧原股份 2026-06-27 21:00 日复盘", html)
        self.assertIn("个股异动", html)
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

    def test_build_email_message_creates_multipart_alternative(self) -> None:
        """验证邮件同时包含纯文本和 HTML 两种正文。"""
        message = build_email_message(
            recipient="376597874@qq.com",
            subject="牧原股份 2026-06-27 21:00 日复盘",
            text_body="纯文本版本",
            html_body="<html><body><h1>HTML版本</h1></body></html>",
        )

        self.assertIn("Content-Type: multipart/alternative;", message)
        self.assertIn("Content-Type: text/plain; charset=UTF-8", message)
        self.assertIn("Content-Type: text/html; charset=UTF-8", message)
        self.assertIn("HTML版本", message)

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
            patch("product.jobs.muyuan_nightly.get_tushare_snapshot", return_value=("2026-06-27", {"close": 1.0, "pct_chg": 2.0, "pe_ttm": 3.0, "pb": 4.0, "turnover_rate": 5.0, "total_mv_billion": 6.0})),
            patch("product.jobs.muyuan_nightly.get_eastmoney_snapshot", return_value=None),
            patch("product.jobs.muyuan_nightly.get_signal_data", return_value={}),
            patch("product.jobs.muyuan_nightly.get_tushare_trend_metrics", return_value=[]),
            patch("product.jobs.muyuan_nightly.get_hog_cycle_metrics", return_value=[]),
            patch("product.jobs.muyuan_nightly.ModelService.from_project_config", return_value=fake_service) as mock_from_project_config,
            patch("product.jobs.muyuan_nightly.analyze_report_with_model", return_value=fake_context["analysis"]) as mock_analyze,
            patch("product.jobs.muyuan_nightly.write_report", return_value=__import__("pathlib").Path("/tmp/fake.md")),
        ):
            output_path, content, report_context = generate_report("2026-06-27", force=True)

        self.assertEqual(output_path.as_posix(), "/tmp/fake.md")
        self.assertIn("保持持有", content)
        self.assertEqual(report_context["analysis"]["current_status"], "持有")
        self.assertIs(mock_analyze.call_args.kwargs["model_service"], fake_service)
        mock_from_project_config.assert_called_once()


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
            hour=21,
            minute=0,
            label="com.astock.muyuan-nightly",
        )

        self.assertIn("<string>com.astock.muyuan-nightly</string>", plist)
        self.assertIn("<integer>21</integer>", plist)
        self.assertIn("<integer>0</integer>", plist)
        self.assertIn("<string>/usr/bin/python3</string>", plist)
        self.assertIn("<string>/tmp/a_stock/product/jobs/muyuan_nightly.py</string>", plist)
        self.assertIn("<string>376597874@qq.com</string>", plist)

    def test_build_email_subject(self) -> None:
        """验证日报邮件标题包含标的、日期和复盘时间。"""
        self.assertEqual(
            build_email_subject("2026-06-27"),
            "牧原股份 2026-06-27 21:00 日复盘",
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
