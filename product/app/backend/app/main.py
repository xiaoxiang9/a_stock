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
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from product.app.backend.application.reports.muyuan_nightly import build_email_subject, run_report_workflow_async
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
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class DatabaseDemoRequest(BaseModel):
    """数据库示例请求体。"""

    note: str = "hello"


class ManualDailyReportRequest(BaseModel):
    """手动复盘邮件触发请求体。"""

    report_date: str = ""
    recipient: str = ""


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


def _today_in_shanghai() -> str:
    """返回上海时区的自然日字符串。"""
    return datetime.now(timezone.utc).astimezone(SHANGHAI_TZ).date().isoformat()


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


@app.get("/api/reports/muyuan/daily/defaults")
async def daily_report_defaults() -> dict[str, str]:
    """返回手动触发每日复盘邮件时的默认参数。"""
    return {
        "report_date": _today_in_shanghai(),
        "recipient": PROJECT_CONFIG.email.recipient,
    }


@app.post("/api/reports/muyuan/daily/send")
async def send_daily_report(payload: ManualDailyReportRequest) -> dict[str, object]:
    """手动触发一次牧原股份每日复盘邮件。

    这里直接复用日报工作流，代码只负责接收用户选择、调用工作流并返回执行结果。
    """
    report_date = payload.report_date.strip() or _today_in_shanghai()
    recipient = payload.recipient.strip() or PROJECT_CONFIG.email.recipient
    if not recipient:
        raise HTTPException(status_code=400, detail="Recipient is required")
    try:
        output_path, _, report_context = await run_report_workflow_async(
            report_date=report_date,
            force=True,
            recipient=recipient,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Daily report send failed: {exc}") from exc

    valuation_trace = report_context.get("valuation_trace", []) or []
    return {
        "status": "ok",
        "report_date": report_date,
        "recipient": recipient,
        "subject": build_email_subject(report_date),
        "output_path": str(output_path),
        "valuation_rounds": len(valuation_trace),
        "valuation_termination_reason": report_context.get("valuation_termination_reason", ""),
    }


@app.get("/api/modules/etf-buy-decision")
async def etf_buy_decision(refresh: bool = False) -> dict:
    """返回美股 ETF 买入决策模块数据。

    参数：
    - refresh：为 true 时绕过缓存重新拉取数据，用于人工刷新校验。
    """
    # refresh=true 用于人工验证或页面强制刷新；默认走服务层缓存，降低外部数据源压力。
    return await get_etf_buy_decision(force_refresh=refresh)
