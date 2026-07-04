"""数据层统一取数能力测试。

职责：
- 验证通用数据层可以按参数提供个股快照、趋势指标、东方财富校验解析和信号摘要。
- 保护“任务层不直接实现取数逻辑，统一从 product/data 获取数据”的边界。
"""

from __future__ import annotations

import json
import unittest

from product.data.fetchers.hog_cycle import build_hog_cycle_metrics
from product.data.fetchers.market_data import _calculate_wilder_rsi, _trigger_deviation
from product.data.fetchers.signals import summarize_mx_search_output
from product.data.fetchers.stock import (
    build_stock_snapshot,
    build_stock_trend_metrics,
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
