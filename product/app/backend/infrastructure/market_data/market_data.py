"""后端市场数据服务兼容入口。

职责：
- 属于表达层后端服务入口，只负责把历史导入路径继续暴露给 API 和既有测试。
- 实际数据获取、清洗、缓存和确定性计算已经统一迁移到 `product.data.fetchers.market_data`。

职责边界：
- 本文件不再承载外部取数实现。
- 后续新增市场数据源时，应优先在数据层实现，再由这里按需导出。
"""

from product.data.fetchers.market_data import _calculate_wilder_rsi, _trigger_deviation, get_etf_buy_decision


__all__ = ["_calculate_wilder_rsi", "_trigger_deviation", "get_etf_buy_decision"]
