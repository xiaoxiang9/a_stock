"""后台日报调度测试。

职责：
- 验证每日执行时间计算、跨进程锁和 FastAPI 生命周期挂载。
- 保护后端进程自动触发复盘报告的执行链路。
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from product.app.backend.infrastructure.scheduling.report_scheduler import (
    DailyReportScheduler,
    DailySchedule,
    compute_next_run_at,
)


class DailyReportScheduleTests(unittest.TestCase):
    """每日执行时间计算测试。"""

    def test_compute_next_run_at_uses_next_day_after_cutoff(self) -> None:
        """验证当当前时间已过执行点时，会顺延到次日。"""
        now = datetime(2026, 7, 4, 15, 30, tzinfo=timezone.utc)
        next_run = compute_next_run_at(now, DailySchedule(hour=1, minute=32))

        self.assertEqual(next_run.isoformat(), "2026-07-05T01:32:00+08:00")

    def test_compute_next_run_at_keeps_same_day_before_cutoff(self) -> None:
        """验证当当前时间未到执行点时，仍保留当天。"""
        now = datetime(2026, 7, 3, 16, 0, tzinfo=timezone.utc)
        next_run = compute_next_run_at(now, DailySchedule(hour=1, minute=32))

        self.assertEqual(next_run.isoformat(), "2026-07-04T01:32:00+08:00")


class DailyReportSchedulerTests(unittest.IsolatedAsyncioTestCase):
    """日报调度器生命周期测试。"""

    async def test_scheduler_starts_and_stops_with_file_lock(self) -> None:
        """验证调度器能获取锁、启动后台任务并在停止时释放锁。"""
        runner = AsyncMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "scheduler.lock"
            scheduler = DailyReportScheduler(
                runner=runner,
                schedule=DailySchedule(hour=23, minute=59),
                lock_path=lock_path,
            )

            await scheduler.start()
            self.assertTrue(scheduler.running)

            await scheduler.stop()
            self.assertFalse(scheduler.running)

    async def test_scheduler_skips_when_lock_is_held_by_another_process(self) -> None:
        """验证同一锁文件被占用时，后来的调度器会跳过启动。"""
        runner = AsyncMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "scheduler.lock"
            first = DailyReportScheduler(
                runner=runner,
                schedule=DailySchedule(hour=23, minute=59),
                lock_path=lock_path,
            )
            second = DailyReportScheduler(
                runner=runner,
                schedule=DailySchedule(hour=23, minute=59),
                lock_path=lock_path,
            )

            await first.start()
            await second.start()

            self.assertTrue(first.running)
            self.assertFalse(second.running)

            await first.stop()

    async def test_fastapi_lifespan_starts_and_stops_scheduler(self) -> None:
        """验证后端应用启动时会挂载调度器，关闭时会回收调度器。"""
        fake_scheduler = type(
            "FakeScheduler",
            (),
            {
                "running": False,
                "start": AsyncMock(),
                "stop": AsyncMock(),
            },
        )()

        with patch("product.app.backend.app.main.create_report_scheduler", return_value=fake_scheduler):
            from product.app.backend.app.main import app

            async with app.router.lifespan_context(app):
                self.assertTrue(fake_scheduler.start.await_count >= 1)

        self.assertTrue(fake_scheduler.stop.await_count >= 1)


if __name__ == "__main__":
    unittest.main()
