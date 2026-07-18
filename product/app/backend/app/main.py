"""A Stock 后端 API 入口。

职责：
- 创建 FastAPI 应用。
- 从全局配置读取服务元信息和 CORS 白名单。
- 在应用生命周期内挂载日报调度器和 MySQL 连接，完成服务装配。
- 暴露健康检查、欢迎接口和 ETF 买入决策模块接口。

边界：
- 本文件只负责 HTTP 路由和服务装配。
- 具体数据获取、缓存、数据库连接和规则计算下沉到基础设施层。
"""

from contextlib import asynccontextmanager
from pathlib import Path

from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from product.app.backend.infrastructure.market_data.market_data import get_etf_buy_decision
from product.app.backend.infrastructure.database import build_mysql_client
from product.app.backend.infrastructure.config.private_config import load_private_config
from product.app.backend.infrastructure.scheduling.report_scheduler import (
    DailyReportScheduler,
    DailySchedule,
    build_daily_report_runner,
)
from product.app.backend.infrastructure.config.project_config import load_project_config


PROJECT_CONFIG = load_project_config()


class DatabaseDemoRequest(BaseModel):
    """数据库示例请求体。"""

    note: str = "hello"


def _resolve_project_root() -> Path:
    """解析项目根目录，用于调度器锁文件和运行时路径。"""
    return Path(__file__).resolve().parents[4]


REPORT_SCHEDULER_LOCK = _resolve_project_root() / "product" / "app" / "backend" / "infrastructure" / "scheduling" / ".muyuan_nightly.scheduler.lock"


def create_report_scheduler() -> DailyReportScheduler:
    """构造后端内置的日报调度器。"""
    return DailyReportScheduler(
        runner=build_daily_report_runner(PROJECT_CONFIG.email.recipient),
        schedule=DailySchedule(hour=PROJECT_CONFIG.launchd.hour, minute=PROJECT_CONFIG.launchd.minute),
        lock_path=REPORT_SCHEDULER_LOCK,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """后端应用生命周期。

    启动时挂载日报调度器和数据库客户端，关闭时释放文件锁、后台任务和数据库连接。
    """
    scheduler = create_report_scheduler()
    database = build_mysql_client(PROJECT_CONFIG, load_private_config())
    app.state.report_scheduler = scheduler
    app.state.database = database
    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()
        database.close()

# FastAPI 应用元信息全部来自全局配置，避免部署环境和页面展示出现多套口径。
app = FastAPI(
    title=PROJECT_CONFIG.backend.title,
    description=PROJECT_CONFIG.backend.description,
    version=PROJECT_CONFIG.backend.version,
    lifespan=lifespan,
)

# CORS 白名单由 product/app/config/app.toml 统一管理；
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
async def health(request: Request) -> dict[str, str]:
    """返回服务健康状态。"""
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(status_code=503, detail="Database client is not initialized")
    return {"status": "ok", "database": "deferred" if not getattr(database, "connected", False) else "connected"}


@app.get("/api/database/ping")
async def database_ping(request: Request) -> dict[str, str]:
    """在请求时主动连通 MySQL，并返回探活结果。"""
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(status_code=503, detail="Database client is not initialized")
    try:
        database.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc
    return {"status": "ok", "database": "connected"}


@app.post("/api/database/demo")
async def database_demo(payload: DatabaseDemoRequest, request: Request) -> dict[str, int]:
    """演示对 MySQL 执行一次写入和一次查询。"""
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(status_code=503, detail="Database client is not initialized")
    try:
        return database.run_demo_round_trip(note=payload.note)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database demo failed: {exc}") from exc


@app.get("/api/modules/etf-buy-decision")
async def etf_buy_decision(refresh: bool = False) -> dict:
    """返回美股 ETF 买入决策模块数据。

    参数：
    - refresh：为 true 时绕过缓存重新拉取数据，用于人工刷新校验。
    """
    # refresh=true 用于人工验证或页面强制刷新；默认走服务层缓存，降低外部数据源压力。
    return await get_etf_buy_decision(force_refresh=refresh)
