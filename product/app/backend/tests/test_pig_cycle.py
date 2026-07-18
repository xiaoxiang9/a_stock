"""猪周期数据服务测试。

职责：
- 验证月度趋势取值规则。
- 验证现货、期货和基差指标统一为元/公斤后输出。
"""

import unittest

from product.app.backend.infrastructure.market_data.pig_cycle import build_hog_cycle_metrics, _monthly_last_points


class PigCycleMonthlyTrendTests(unittest.TestCase):
    """猪周期月度趋势卡片测试。"""

    def test_monthly_last_points_keeps_latest_point_per_month(self) -> None:
        """验证每个月只保留最后一个可用观测点。"""
        points = [
            {"date": "2025-01-02", "value": 10.0},
            {"date": "2025-01-31", "value": 11.0},
            {"date": "2025-02-10", "value": 12.0},
            {"date": "2025-02-28", "value": 13.0},
            {"date": "2025-03-05", "value": 14.0},
        ]

        result = _monthly_last_points(points, months=12)

        self.assertEqual(
            result,
            [
                {"date": "2025-01-31", "value": 11.0},
                {"date": "2025-02-28", "value": 13.0},
                {"date": "2025-03-05", "value": 14.0},
            ],
        )

    def test_build_hog_cycle_metrics_uses_monthly_basis_series(self) -> None:
        """验证三类猪周期指标按月度序列和统一单位生成。"""
        spot_points = [
            {"date": "2025-01-02", "value": 10.0},
            {"date": "2025-01-31", "value": 11.0},
            {"date": "2025-02-10", "value": 12.0},
            {"date": "2025-02-28", "value": 13.0},
            {"date": "2025-03-05", "value": 14.0},
        ]
        futures_points = [
            {"date": "2025-01-03", "value": 10000.0},
            {"date": "2025-01-30", "value": 11000.0},
            {"date": "2025-02-10", "value": 12000.0},
            {"date": "2025-02-28", "value": 13000.0},
            {"date": "2025-03-31", "value": 14000.0},
        ]

        metrics = build_hog_cycle_metrics(spot_points, futures_points)

        self.assertEqual([metric["name"] for metric in metrics], ["现货生猪", "生猪期货", "现货基差"])
        self.assertEqual(metrics[0]["latest"], "14.00 元/公斤")
        self.assertEqual(metrics[1]["latest"], "14.00 元/公斤")
        self.assertEqual(metrics[1]["values"], [11.0, 13.0, 14.0])
        self.assertEqual(metrics[2]["latest"], "0.00 元/公斤")
        self.assertEqual(metrics[2]["values"], [0.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
