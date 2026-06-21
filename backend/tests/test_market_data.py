import unittest

from app.services.market_data import _calculate_wilder_rsi


class WilderRsiTests(unittest.TestCase):
    def test_classic_fourteen_period_sample(self) -> None:
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
        points = [
            {"date": f"2026-02-{index + 1:02d}", "close": float(index)}
            for index in range(15)
        ]

        result = _calculate_wilder_rsi(points)

        self.assertEqual(result[-1]["value"], 100.0)


if __name__ == "__main__":
    unittest.main()
