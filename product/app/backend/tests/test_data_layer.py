"""数据层统一取数能力测试。

职责：
- 验证通用数据层可以按参数提供个股快照、趋势指标、东方财富校验解析和信号摘要。
- 保护“任务层不直接实现取数逻辑，统一从 product/data 获取数据”的边界。
"""

from __future__ import annotations

import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from product.data.adapters.mx_skills import _extract_search_summary_lines, extract_mx_finance_snapshot_from_workbook
from product.data.fetchers.hog_cycle import build_hog_cycle_metrics
from product.data.fetchers.market_data import _calculate_wilder_rsi, _trigger_deviation
from product.data.fetchers.signals import get_signal_data
from product.data.processors.stock_valuation_monthly import (
    build_monthly_valuation_payload,
    build_monthly_valuation_points,
    summarize_monthly_valuation_points,
)
from product.data.services.stock_valuation_monthly import StockValuationMonthlyService
from product.data.fetchers.signals import summarize_mx_search_output
from product.data.fetchers.stock import (
    build_stock_snapshot,
    build_stock_trend_metrics,
    _resolve_tushare_window,
    parse_eastmoney_stdout,
)


class StockDataFetcherTests(unittest.TestCase):
    """A 股个股数据能力测试。"""

    def test_build_stock_snapshot_uses_latest_trade_date(self) -> None:
        """验证个股快照按最新交易日合并行情和估值数据。"""
        daily_rows = [
            {"ts_code": "002714.SZ", "trade_date": "20260628", "close": 32.0, "pct_chg": 1.0},
            {"ts_code": "002714.SZ", "trade_date": "20260630", "close": 34.99, "pct_chg": -2.78},
        ]
        basic_rows = [
            {
                "ts_code": "002714.SZ",
                "trade_date": "20260630",
                "pe_ttm": 20.65,
                "pb": 2.342,
                "turnover_rate": 2.15,
                "total_mv": 20199700.0,
            }
        ]

        trade_date, snapshot = build_stock_snapshot(daily_rows, basic_rows)

        self.assertEqual(trade_date, "2026-06-30")
        self.assertEqual(snapshot["close"], 34.99)
        self.assertEqual(snapshot["pct_chg"], -2.78)
        self.assertEqual(snapshot["pe_ttm"], 20.65)
        self.assertEqual(snapshot["pb"], 2.342)
        self.assertEqual(snapshot["turnover_rate"], 2.15)
        self.assertEqual(snapshot["total_mv_billion"], 2019.97)

    def test_build_stock_trend_metrics_returns_current_report_cards(self) -> None:
        """验证个股趋势能力输出日报当前使用的五张趋势卡片。"""
        daily_rows = [
            {"ts_code": "002714.SZ", "trade_date": "20260627", "close": 33.56},
            {"ts_code": "002714.SZ", "trade_date": "20260630", "close": 34.99},
        ]
        basic_rows = [
            {
                "ts_code": "002714.SZ",
                "trade_date": "20260627",
                "pe_ttm": 19.81,
                "pb": 2.246,
                "turnover_rate": 2.759,
                "total_mv": 19374200.0,
            },
            {
                "ts_code": "002714.SZ",
                "trade_date": "20260630",
                "pe_ttm": 20.65,
                "pb": 2.342,
                "turnover_rate": 2.15,
                "total_mv": 20199700.0,
            },
        ]

        metrics = build_stock_trend_metrics(daily_rows, basic_rows)

        self.assertEqual([metric["name"] for metric in metrics], ["收盘价", "PE(TTM)", "PB", "换手率", "总市值"])
        self.assertEqual(metrics[0]["latest"], "34.99 元")
        self.assertEqual(metrics[3]["latest"], "2.150%")
        self.assertEqual(metrics[4]["latest"], "2019.97 亿元")

    def test_parse_eastmoney_stdout_is_generic_for_stock_table(self) -> None:
        """验证东方财富表格解析不绑定具体股票名称。"""
        stdout = """
**麦格米特(002851.SZ)的总市值、市净率PB等** (前20行预览):

| date | 总市值 | 市净率PB | 市盈率PE(TTM) | 换手率 |
| --- | --- | --- | --- | --- |
| 2026-06-30(日) | 310亿 | 4.2倍 | 28.5倍 | 1.23% |
"""

        parsed = parse_eastmoney_stdout(stdout)

        self.assertEqual(parsed, {"total_mv_billion": 310.0, "pe_ttm": 28.5, "turnover_rate": 1.23})

    def test_extract_mx_finance_snapshot_from_workbook_reads_latest_sheet(self) -> None:
        """验证 mx-finance-data 产出的工作簿可以提取最新交易日快照。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            xlsx_path = Path(tmpdir) / "mx_finance_data.xlsx"
            frame = pd.DataFrame(
                {
                    "指标": ["市盈率PE(TTM)", "市净率PB", "换手率", "总市值"],
                    "2026-07-17": ["23.51倍", "2.88倍", "2.777%", "2299亿"],
                }
            )
            with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
                frame.to_excel(writer, index=False)

            trade_date, snapshot = extract_mx_finance_snapshot_from_workbook(xlsx_path)

        self.assertEqual(trade_date, "2026-07-17")
        self.assertEqual(snapshot["pe_ttm"], 23.51)
        self.assertEqual(snapshot["pb"], 2.88)
        self.assertEqual(snapshot["turnover_rate"], 2.777)
        self.assertEqual(snapshot["total_mv_billion"], 2299.0)

    def test_resolve_tushare_window_uses_dynamic_as_of_date(self) -> None:
        """验证 Tushare 查询窗口会按业务时点动态计算。"""
        start_date, end_date = _resolve_tushare_window("2026-07-06", lookback_days=180)

        self.assertEqual(end_date, "20260706")
        self.assertEqual(start_date, "20260107")

    def test_build_monthly_valuation_points_keeps_last_trade_day_of_each_month(self) -> None:
        """验证月度 PE/PB 序列会按月份保留最后一个交易日的数据。"""
        rows = [
            {"ts_code": "002714.SZ", "trade_date": "20260528", "pe_ttm": 10.0, "pb": 1.0},
            {"ts_code": "002714.SZ", "trade_date": "20260530", "pe_ttm": 11.0, "pb": 1.1},
            {"ts_code": "002714.SZ", "trade_date": "20260627", "pe_ttm": 12.0, "pb": 1.2},
            {"ts_code": "002714.SZ", "trade_date": "20260630", "pe_ttm": 13.0, "pb": 1.3},
        ]

        points = build_monthly_valuation_points(rows)

        self.assertEqual([point["month"] for point in points], ["2026-05", "2026-06"])
        self.assertEqual([point["pe_ttm"] for point in points], [11.0, 13.0])
        self.assertEqual([point["pb"] for point in points], [1.1, 1.3])

    def test_build_monthly_valuation_points_accepts_hyphenated_trade_dates(self) -> None:
        """验证月度估值序列也能兼容带连字符的交易日格式。"""
        rows = [
            {"ts_code": "002714.SZ", "trade_date": "2026-06-28", "pe_ttm": 10.0, "pb": 1.0},
            {"ts_code": "002714.SZ", "trade_date": "2026-06-30", "pe_ttm": 12.0, "pb": 1.2},
        ]

        points = build_monthly_valuation_points(rows)

        self.assertEqual([point["month"] for point in points], ["2026-06"])
        self.assertEqual(points[0]["trade_date"], "2026-06-30")

    def test_summarize_monthly_valuation_points_returns_percentiles(self) -> None:
        """验证月度估值汇总会返回最新值和历史百分位。"""
        points = [
            {"month": "2025-01", "trade_date": "20250131", "pe_ttm": 10.0, "pb": 1.0},
            {"month": "2025-02", "trade_date": "20250228", "pe_ttm": 12.0, "pb": 1.5},
            {"month": "2025-03", "trade_date": "20250331", "pe_ttm": 8.0, "pb": 1.2},
            {"month": "2025-04", "trade_date": "20250430", "pe_ttm": 14.0, "pb": 1.8},
        ]

        summary = summarize_monthly_valuation_points(points)

        self.assertEqual(summary["latest_month"], "2025-04")
        self.assertEqual(summary["latest_pe_ttm"], 14.0)
        self.assertEqual(summary["latest_pb"], 1.8)
        self.assertEqual(summary["pe_percentile"], 1.0)
        self.assertEqual(summary["pb_percentile"], 1.0)

    def test_build_monthly_valuation_payload_includes_series_and_latest_snapshot(self) -> None:
        """验证月度估值 payload 会保留完整序列与最新快照。"""
        points = [
            {"month": "2025-01", "trade_date": "20250131", "pe_ttm": 10.0, "pb": 1.0},
            {"month": "2025-02", "trade_date": "20250228", "pe_ttm": 12.0, "pb": 1.5},
        ]

        payload = build_monthly_valuation_payload(
            ts_code="002714.SZ",
            stock_name="牧原股份",
            listed_date="2014-01-28",
            points=points,
        )

        self.assertEqual(payload["ts_code"], "002714.SZ")
        self.assertEqual(payload["stock_name"], "牧原股份")
        self.assertEqual(payload["latest_month"], "2025-02")
        self.assertEqual(payload["months"], ["2025-01", "2025-02"])
        self.assertEqual(payload["pe_values"], [10.0, 12.0])
        self.assertEqual(payload["pb_values"], [1.0, 1.5])
        self.assertEqual(payload["latest_pe_ttm"], 12.0)
        self.assertEqual(payload["latest_pb"], 1.5)

    def test_bootstrap_all_continues_after_single_stock_failure(self) -> None:
        """验证批量初始化遇到单只股票失败时不会中断后续股票。"""
        service = object.__new__(StockValuationMonthlyService)
        service._token = "token"

        input_stocks = [
            {"ts_code": "002714.SZ", "stock_name": "牧原股份", "listed_date": "2014-01-28"},
            {"ts_code": "002851.SZ", "stock_name": "麦格米特", "listed_date": "2017-03-20"},
        ]

        with patch.object(
            StockValuationMonthlyService,
            "bootstrap_stock",
            side_effect=[{"ok": True}, RuntimeError("boom")],
        ) as mock_bootstrap:
            result = StockValuationMonthlyService.bootstrap_all(service, input_stocks, as_of_date="2026-07-06")

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["failed"][0]["ts_code"], "002851.SZ")
        self.assertEqual(mock_bootstrap.call_count, 2)

    def test_bootstrap_all_rejects_empty_input(self) -> None:
        """验证批量初始化必须显式提供股票输入。"""
        service = object.__new__(StockValuationMonthlyService)

        with self.assertRaises(ValueError):
            StockValuationMonthlyService.bootstrap_all(service, [], as_of_date="2026-07-06")

    def test_refresh_all_uses_tracked_records_only(self) -> None:
        """验证月度保鲜只刷新数据库中已维护的股票列表。"""
        service = object.__new__(StockValuationMonthlyService)
        service._token = "token"
        service._store = __import__("types").SimpleNamespace(
            fetch_tracked_records=lambda: [
                {"ts_code": "002714.SZ", "stock_name": "牧原股份", "listed_date": "2014-01-28"},
                {"ts_code": "002851.SZ", "stock_name": "麦格米特", "listed_date": "2017-03-20"},
            ]
        )

        with patch.object(
            StockValuationMonthlyService,
            "refresh_stock",
            side_effect=[{"ok": True}, {"ok": True}],
        ) as mock_refresh:
            result = StockValuationMonthlyService.refresh_all(service, as_of_date="2026-07-06")

        self.assertEqual(result["processed"], 2)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(mock_refresh.call_count, 2)

    def test_bootstrap_stock_uses_listed_month_floor_as_start_date(self) -> None:
        """验证初始化历史时会从上市月第一天开始追溯。"""
        service = object.__new__(StockValuationMonthlyService)
        service._token = "token"
        service._store = __import__("types").SimpleNamespace(upsert_record=lambda payload: None)

        with patch("product.data.services.stock_valuation_monthly.fetch_monthly_valuation_points", return_value=[{"month": "2014-01", "trade_date": "20140131", "pe_ttm": 10.0, "pb": 1.0}]) as mock_fetch:
            StockValuationMonthlyService.bootstrap_stock(
                service,
                ts_code="002714.SZ",
                stock_name="牧原股份",
                listed_date="2014-01-28",
                as_of_date="2026-06-27",
            )

        mock_fetch.assert_called_once()
        self.assertEqual(mock_fetch.call_args.kwargs["start_date"], "20140101")

    def test_render_launchd_plist_uses_data_subsystem_schedule(self) -> None:
        """验证月更 launchd 配置使用 data 子系统自己的调度与脚本入口。"""
        service = object.__new__(StockValuationMonthlyService)
        service._config = __import__("types").SimpleNamespace(
            monthly_refresh=__import__("types").SimpleNamespace(
                label="com.astock.data-monthly-refresh",
                day=3,
                hour=1,
                minute=12,
            )
        )

        repo_root = Path(__file__).resolve().parents[4]
        expected_script = repo_root / "product" / "data" / "scripts" / "refresh.sh"
        expected_log = repo_root / "product" / "data" / "scripts" / "monthly_refresh.log"

        with patch("product.data.services.stock_valuation_monthly._runtime_python_path", return_value="/usr/bin/python3"):
            plist = StockValuationMonthlyService.render_launchd_plist(service)

        self.assertIn("<string>com.astock.data-monthly-refresh</string>", plist)
        self.assertIn("<integer>3</integer>", plist)
        self.assertIn("<integer>1</integer>", plist)
        self.assertIn("<integer>12</integer>", plist)
        self.assertIn("<string>/usr/bin/python3</string>", plist)
        self.assertIn(f"<string>{expected_script}</string>", plist)
        self.assertIn("--refresh-all", plist)
        self.assertIn(f"<string>{expected_log}</string>", plist)

    def test_refresh_script_uses_data_virtualenv(self) -> None:
        """验证刷新脚本只依赖 data 子系统自己的虚拟环境。"""
        script_path = Path(__file__).resolve().parents[4] / "product" / "data" / "scripts" / "refresh.sh"
        script_text = script_path.read_text(encoding="utf-8")

        self.assertIn("product/data/.venv/bin/python", script_text)
        self.assertNotIn("product/app/backend/.venv/bin/python", script_text)


class SignalDataFetcherTests(unittest.TestCase):
    """公告和经营数据检索能力测试。"""

    def test_summarize_mx_search_output_reads_json_payload(self) -> None:
        """验证 mx-search JSON 输出能按标题关键词过滤。"""
        raw = json.dumps(
            {
                "data": [
                    {"title": "麦格米特：2026年半年度业绩预告", "date": "2026-07-10 00:00:00", "source": "巨潮资讯"},
                    {"title": "无关新闻", "date": "2026-07-09", "source": "新闻源"},
                ]
            },
            ensure_ascii=False,
        )

        lines = summarize_mx_search_output(raw, limit=3, title_keywords=["业绩预告"])

        self.assertEqual(lines, ["2026-07-10｜巨潮资讯｜麦格米特：2026年半年度业绩预告"])

    def test_get_signal_data_prefers_mx_finance_search(self) -> None:
        """验证信号抓取优先调用新 skill，再回退到本地缓存。"""
        with patch("product.data.fetchers.signals.query_mx_finance_news_summary", return_value=["2026-07-10｜巨潮资讯｜牧原股份公告"]):
            with patch("product.data.fetchers.signals._load_latest_cached_signal_lines", return_value=[]):
                result = get_signal_data(company_name="牧原股份")

        self.assertEqual(result["announcements"], ["2026-07-10｜巨潮资讯｜牧原股份公告"])

    def test_extract_search_summary_lines_reads_nested_llm_search_response(self) -> None:
        """验证 mx-finance-search 的嵌套返回结构能正确提取标题、日期和来源。"""
        raw_result = {
            "raw": {
                "data": {
                    "llmSearchResponse": {
                        "data": [
                            {
                                "title": "牧原股份:关于公司董事和高级管理人员加快实施增持股份计划暨实施结果公告",
                                "date": "2026-07-21 00:17:18",
                                "informationType": "NOTICE",
                            }
                        ]
                    }
                }
            }
        }

        lines = _extract_search_summary_lines(raw_result, limit=3)

        self.assertEqual(
            lines,
            [
                "2026-07-21｜NOTICE｜牧原股份:关于公司董事和高级管理人员加快实施增持股份计划暨实施结果公告",
            ],
        )


class HogCycleDataFetcherTests(unittest.TestCase):
    """生猪行业数据能力测试。"""

    def test_build_hog_cycle_metrics_keeps_existing_card_contract(self) -> None:
        """验证猪周期数据层保持日报当前趋势卡片结构。"""
        metrics = build_hog_cycle_metrics(
            spot_points=[{"date": "2026-05-31", "value": 9.4}, {"date": "2026-06-30", "value": 9.89}],
            futures_points=[{"date": "2026-05-31", "value": 12000.0}, {"date": "2026-06-30", "value": 12350.0}],
        )

        self.assertEqual([metric["name"] for metric in metrics], ["现货生猪", "生猪期货", "现货基差"])
        self.assertEqual(metrics[0]["latest"], "9.89 元/公斤")
        self.assertEqual(metrics[1]["latest"], "12.35 元/公斤")
        self.assertEqual(metrics[2]["latest"], "-2.46 元/公斤")


class MarketDataFetcherTests(unittest.TestCase):
    """海外市场指标数据能力测试。"""

    def test_market_indicator_helpers_live_in_data_layer(self) -> None:
        """验证 ETF 市场指标的确定性计算由数据层承载。"""
        points = [{"date": f"2026-06-{day:02d}", "close": float(day)} for day in range(1, 17)]

        rsi_points = _calculate_wilder_rsi(points)

        self.assertEqual(rsi_points[-1]["value"], 100.0)
        self.assertEqual(_trigger_deviation(35, 28, ">"), 25.0)


if __name__ == "__main__":
    unittest.main()
