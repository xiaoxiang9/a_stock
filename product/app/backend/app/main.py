"""A Stock 后端 API 入口。

职责：
- 创建 FastAPI 应用。
- 从全局配置读取服务元信息和 CORS 白名单。
- 暴露健康检查、欢迎接口和 ETF 买入决策模块接口。

边界：
- 本文件只负责 HTTP 路由和服务装配。
- 具体数据获取、缓存和规则计算下沉到 service 层。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from product.core.project_config import load_project_config

from product.app.backend.app.services.market_data import get_etf_buy_decision


PROJECT_CONFIG = load_project_config()

# FastAPI 应用元信息全部来自全局配置，避免部署环境和页面展示出现多套口径。
app = FastAPI(
    title=PROJECT_CONFIG.backend.title,
    description=PROJECT_CONFIG.backend.description,
    version=PROJECT_CONFIG.backend.version,
)

# CORS 白名单由 product/config/project.toml 统一管理；
# 后续前端域名变化时只改配置，不改业务代码。
app.add_middleware(
    CORSMiddleware,
    allow_origins=PROJECT_CONFIG.backend.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    """返回后端根路径欢迎信息。"""
    return {"message": "Welcome to A Stock API"}


@app.get("/api/welcome")
async def welcome() -> dict[str, str]:
    """返回前后端联通状态文案。"""
    return {
        "title": "欢迎来到 A Stock",
        "message": "Python 与 Vue 已经连接成功，可以开始构建你的应用了。",
        "status": "online",
    }


@app.get("/api/health")
async def health() -> dict[str, str]:
    """返回服务健康状态。"""
    return {"status": "ok"}


@app.get("/api/modules/etf-buy-decision")
async def etf_buy_decision(refresh: bool = False) -> dict:
    """返回美股 ETF 买入决策模块数据。

    参数：
    - refresh：为 true 时绕过缓存重新拉取数据，用于人工刷新校验。
    """
    # refresh=true 用于人工验证或页面强制刷新；默认走服务层缓存，降低外部数据源压力。
    return await get_etf_buy_decision(force_refresh=refresh)
