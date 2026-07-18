"""data 子系统 HTTP API 入口。

职责：
- 对外提供月度 PE/PB 历史查询和刷新接口。
- 仅作为 data 子系统的 HTTP 门面，不承载 app 业务逻辑。

边界：
- 不直接做估值判断。
- 不依赖 app 子系统的配置、路由或服务对象。
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query

from product.data.config.data_config import load_data_config
from product.data.services.stock_valuation_monthly import build_service


app = FastAPI(title="A Stock Data API", version="0.1.0")


def _service():
    """获取并缓存 data 服务对象。"""
    service = getattr(app.state, "valuation_service", None)
    if service is None:
        service = build_service()
        app.state.valuation_service = service
    return service


@app.get("/health")
def health() -> dict[str, str]:
    """返回 data 子系统健康状态。"""
    config = load_data_config()
    return {
        "status": "ok",
        "api_prefix": config.api.prefix,
        "database": config.mysql.database,
    }


@app.get("/api/valuation/pepb/{ts_code}")
def query_monthly_valuation(ts_code: str, refresh_if_missing: bool = Query(False)) -> dict[str, object]:
    """查询单只股票的月度 PE/PB 百分位结果。"""
    result = _service().query_stock(ts_code, refresh_if_missing=refresh_if_missing)
    if result is None:
        raise HTTPException(status_code=404, detail=f"未找到 {ts_code} 的月度估值记录")
    return result


@app.post("/api/valuation/pepb/bootstrap/{ts_code}")
def bootstrap_monthly_valuation(ts_code: str) -> dict[str, object]:
    """初始化单只股票的全量月度 PE/PB 记录。"""
    return _service().bootstrap_stock(ts_code)


@app.post("/api/valuation/pepb/refresh/{ts_code}")
def refresh_monthly_valuation(ts_code: str) -> dict[str, object]:
    """刷新单只股票的当前月度 PE/PB 记录。"""
    return _service().refresh_stock(ts_code)


@app.post("/api/valuation/pepb/bootstrap-all")
def bootstrap_all_monthly_valuation(stocks: list[dict[str, Any]]) -> dict[str, object]:
    """批量初始化输入股票列表的月度 PE/PB 记录。"""
    return _service().bootstrap_all(stocks)


@app.post("/api/valuation/pepb/refresh-all")
def refresh_all_monthly_valuation(limit: int = Query(0, ge=0)) -> dict[str, object]:
    """批量刷新全部上市股票的当前月度 PE/PB 记录。"""
    return _service().refresh_all(limit=limit or None)
