"""日报后台调度服务。

职责：
- 在后端进程内按日常固定时间触发复盘任务。
- 通过跨进程文件锁避免多 worker 重复发送。
- 只负责调度和编排，不承载投研分析逻辑。

边界：
- 具体日报生成与邮件发送复用 `product.app.backend.application.reports.muyuan_nightly`。
- 调度器不判断分析结果，只决定何时执行任务。
"""

from __future__ import annotations

import asyncio
import fcntl
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from ...application.reports.muyuan_nightly import run_report_workflow_async


LOGGER = logging.getLogger(__name__)
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class ScheduledReportRunner(Protocol):
    """日报执行器协议。

    调度器只关心“执行一次日报”的能力，不关心内部怎么取数、渲染和发信。
    """

    async def __call__(self, report_date: str) -> None: ...


@dataclass(frozen=True)
class DailySchedule:
    """每日固定执行时间。

    这个配置来源于项目全局配置的时间字段，名称保留历史兼容，但语义已经
    约束为“每日定时执行时间”。
    """

    hour: int
    minute: int


def compute_next_run_at(now: datetime, schedule: DailySchedule) -> datetime:
    """计算下一次触发时间。

    参数：
    - now：当前时间，建议传入带时区的时间。
    - schedule：每日执行小时和分钟。
    """
    current = now.astimezone(SHANGHAI_TZ)
    candidate = current.replace(
        hour=schedule.hour,
        minute=schedule.minute,
        second=0,
        microsecond=0,
    )
    if candidate <= current:
        candidate += timedelta(days=1)
    return candidate


def _today_in_shanghai(now: datetime | None = None) -> str:
    """返回上海时区下的自然日字符串。"""
    current = now or datetime.now(timezone.utc)
    return current.astimezone(SHANGHAI_TZ).date().isoformat()


class _ProcessLock:
    """跨进程文件锁。

    仅用于保证同一台机器上同时只有一个调度器实例在工作。
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle = None

    def acquire(self) -> bool:
        """尝试获取锁，成功返回 True，失败返回 False。"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self._path, "a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        """释放锁。"""
        if self._handle is None:
            return
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None


class DailyReportScheduler:
    """后端内置的日报调度器。"""

    def __init__(
        self,
        runner: ScheduledReportRunner,
        schedule: DailySchedule,
        lock_path: Path,
        *,
        timezone_name: str = "Asia/Shanghai",
    ) -> None:
        self._runner = runner
        self._schedule = schedule
        self._lock = _ProcessLock(lock_path)
        self._timezone = ZoneInfo(timezone_name)
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    @property
    def running(self) -> bool:
        """当前是否已经启动后台任务。"""
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """启动调度器。

        如果锁已被其他进程持有，则直接跳过，不影响 API 服务启动。
        """
        if self.running:
            return
        if not self._lock.acquire():
            LOGGER.info("日报调度器未获得锁，当前进程跳过后台调度。")
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run_loop(), name="daily-report-scheduler")
        LOGGER.info("日报调度器已启动，执行时间 %02d:%02d。", self._schedule.hour, self._schedule.minute)

    async def stop(self) -> None:
        """停止调度器并释放锁。"""
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None
        self._lock.release()

    async def run_once(self, report_date: str | None = None) -> None:
        """执行一次日报任务。"""
        target_date = report_date or _today_in_shanghai()
        await self._runner(target_date)

    async def _run_loop(self) -> None:
        """后台循环：等待到点、执行日报、进入下一轮。"""
        while not self._stopping.is_set():
            now = datetime.now(self._timezone)
            next_run = compute_next_run_at(now, self._schedule)
            wait_seconds = max((next_run - now).total_seconds(), 0.0)
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=wait_seconds)
                return
            except asyncio.TimeoutError:
                pass

            report_date = next_run.astimezone(SHANGHAI_TZ).date().isoformat()
            try:
                await self._runner(report_date)
                LOGGER.info("日报任务执行完成：%s。", report_date)
            except Exception:
                LOGGER.exception("日报任务执行失败：%s。", report_date)


def build_daily_report_runner(
    recipient: str,
    *,
    force: bool = False,
) -> ScheduledReportRunner:
    """构造调度器可消费的日报执行器。

    执行器会在后台线程里完成取数、渲染和发信，避免阻塞 FastAPI 事件循环。
    """

    async def _runner(report_date: str) -> None:
        await run_report_workflow_async(report_date=report_date, force=force, recipient=recipient)

    return _runner
