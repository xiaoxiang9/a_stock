"""市场数据服务单元测试。

职责：
- 验证 QQQ RSI(14) 的 Wilder 平滑算法。
- 验证阈值偏离度按触发方向计算。
"""

import unittest

from product.app.backend.infrastructure.market_data.market_data import _calculate_wilder_rsi, _trigger_deviation


class WilderRsiTests(unittest.TestCase):
    """RSI 计算逻辑测试。"""

    def test_classic_fourteen_period_sample(self) -> None:
        """验证经典 14 周期样本能得到预期 RSI。"""
        closes = [
            54.80,
            56.80,
            57.85,
            59.85,
            60.57,
            61.10,
            62.17,
            60.60,
            62.35,
            62.15,
            62.35,
            61.45,
            62.80,
            61.37,
            62.50,
        ]
        points = [
            {"date": f"2026-01-{index + 1:02d}", "close": close}
            for index, close in enumerate(closes)
        ]

        result = _calculate_wilder_rsi(points)

        self.assertEqual(result, [{"date": "2026-01-15", "value": 74.21}])

    def test_continuous_gains_return_one_hundred(self) -> None:
        """验证连续上涨且无损失时 RSI 返回 100。"""
        points = [
            {"date": f"2026-02-{index + 1:02d}", "close": float(index)}
            for index in range(15)
        ]

        result = _calculate_wilder_rsi(points)

        self.assertEqual(result[-1]["value"], 100.0)


class TriggerDeviationTests(unittest.TestCase):
    """触发阈值偏离度测试。"""

    def test_greater_than_condition_uses_upward_direction(self) -> None:
        """验证大于阈值条件按向上突破方向计算偏离度。"""
        self.assertEqual(_trigger_deviation(21, 28, ">"), -25.0)
        self.assertEqual(_trigger_deviation(35, 28, ">"), 25.0)

    def test_less_than_condition_uses_downward_direction(self) -> None:
        """验证小于阈值条件按向下跌破方向计算偏离度。"""
        self.assertEqual(_trigger_deviation(27, 18, "<"), -50.0)
        self.assertEqual(_trigger_deviation(9, 18, "<"), 50.0)


if __name__ == "__main__":
    unittest.main()
