"""猪周期指标后端兼容服务。

职责：
- 为既有后端和测试保留原导入路径。
- 将实际数据获取和指标构造委托给 `product.data.fetchers.hog_cycle`。

边界：
- 本文件不再承载数据获取实现。
- 新增猪周期数据能力应优先在数据层实现。
"""

from product.data.fetchers.hog_cycle import (
    build_hog_cycle_metrics,
    get_hog_cycle_metrics,
    render_hog_cycle_lines,
    _monthly_last_points,
)

__all__ = [
    "_monthly_last_points",
    "build_hog_cycle_metrics",
    "get_hog_cycle_metrics",
    "render_hog_cycle_lines",
]
