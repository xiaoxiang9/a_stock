"""MySQL 数据库接入测试。

职责：
- 验证 MySQL 连接参数能从公开配置和私密配置中正确拼装。
- 验证最小 ping 和关闭协议会按预期发送命令包。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from product.app.backend.app.main import app
from product.app.backend.infrastructure.database import (
    MysqlClient,
    MysqlConnectionSettings,
    build_mysql_connection_settings,
)


class _FakeSocket:
    """用于模拟 MySQL socket 的最小测试替身。"""

    def __init__(self, packets: list[bytes]) -> None:
        self._packets = [bytearray(packet) for packet in packets]
        self.sent_packets: list[bytes] = []
        self.closed = False

    def settimeout(self, timeout: float) -> None:  # noqa: D401
        """兼容 socket 接口。"""
        self.timeout = timeout

    def recv(self, size: int) -> bytes:
        """按需返回预置响应。"""
        if not self._packets:
            return b""
        packet = self._packets[0]
        chunk = bytes(packet[:size])
        del packet[:size]
        if not packet:
            self._packets.pop(0)
        return chunk

    def sendall(self, data: bytes) -> None:
        """记录发送出去的协议包。"""
        self.sent_packets.append(data)

    def close(self) -> None:
        """记录关闭动作。"""
        self.closed = True


class MysqlConfigTests(unittest.TestCase):
    """MySQL 连接配置测试。"""

    def test_build_mysql_connection_settings_uses_public_and_private_configs(self) -> None:
        """验证 MySQL 连接参数能从两份配置中正确拼装。"""
        public_toml = """
[smtp]
host = "smtp.example.com"
port = 465
user = "sender@example.com"
from_addr = "sender@example.com"

[mysql]
host = "127.0.0.1"
port = 3306
database = "astock"
connect_timeout_seconds = 7.5
""".strip()
        private_toml = """
[smtp]
password = "smtp-secret"

[secrets]
deepseek_api_key = "secret"
tushare_token = "token"

[mysql]
user = "astock"
password = "astock-local-password"
""".strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            public_path = Path(tmpdir) / "app.toml"
            private_path = Path(tmpdir) / "private.local.toml"
            public_path.write_text(public_toml, encoding="utf-8")
            private_path.write_text(private_toml, encoding="utf-8")

            settings = build_mysql_connection_settings(public_path, private_path)

        self.assertEqual(settings.host, "127.0.0.1")
        self.assertEqual(settings.port, 3306)
        self.assertEqual(settings.database, "astock")
        self.assertEqual(settings.user, "astock")
        self.assertEqual(settings.password, "astock-local-password")
        self.assertEqual(settings.connect_timeout_seconds, 7.5)

    def test_ping_sends_com_ping_and_close_sends_com_quit(self) -> None:
        """验证 ping 和 close 的命令包内容。"""
        client = MysqlClient(
            settings=MysqlConnectionSettings(
                host="127.0.0.1",
                port=3306,
                database="astock",
                user="astock",
                password="astock-local-password",
            ),
        )
        fake_socket = _FakeSocket([b"\x01\x00\x00\x00\x00"])
        client._socket = fake_socket  # type: ignore[attr-defined]

        client.ping()
        client.close()

        self.assertTrue(client._socket is None)
        self.assertEqual(fake_socket.sent_packets[0][-1], 0x0E)
        self.assertEqual(fake_socket.sent_packets[-1][-1], 0x01)
        self.assertTrue(fake_socket.closed)

    def test_fastapi_lifespan_does_not_connect_database_during_startup(self) -> None:
        """验证应用启动时只装配数据库客户端，不强制建立连接。"""
        fake_scheduler = type(
            "FakeScheduler",
            (),
            {
                "running": False,
                "start": AsyncMock(),
                "stop": AsyncMock(),
            },
        )()
        fake_database = type(
            "FakeDatabase",
            (),
            {
                "connect": unittest.mock.Mock(),
                "ping": unittest.mock.Mock(),
                "close": unittest.mock.Mock(),
            },
        )()

        with patch("product.app.backend.app.main.create_report_scheduler", return_value=fake_scheduler), patch(
            "product.app.backend.app.main.build_mysql_client", return_value=fake_database
        ):
            async def _run() -> None:
                async with app.router.lifespan_context(app):
                    self.assertTrue(fake_scheduler.start.await_count >= 1)

            import asyncio

            asyncio.run(_run())

        fake_database.connect.assert_not_called()
        fake_database.ping.assert_not_called()
        fake_database.close.assert_called_once()

    def test_database_ping_endpoint_checks_connection_on_demand(self) -> None:
        """验证数据库接口会在请求时再执行 ping。"""
        fake_database = type(
            "FakeDatabase",
            (),
            {
                "connected": False,
                "connect": unittest.mock.Mock(),
                "ping": unittest.mock.Mock(),
                "run_demo_round_trip": unittest.mock.Mock(return_value={"inserted": 1, "total_rows": 1}),
                "close": unittest.mock.Mock(),
            },
        )()

        with patch("product.app.backend.app.main.build_mysql_client", return_value=fake_database), patch(
            "product.app.backend.app.main.create_report_scheduler"
        ) as create_report_scheduler:
            create_report_scheduler.return_value = type(
                "FakeScheduler",
                (),
                {
                    "running": False,
                    "start": AsyncMock(),
                    "stop": AsyncMock(),
                },
            )()
            with TestClient(app) as client:
                app.state.database = fake_database
                response = client.get("/api/database/ping")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        fake_database.ping.assert_called_once()

    def test_database_demo_endpoint_performs_write_then_read(self) -> None:
        """验证示例接口会触发一次写入并返回可读结果。"""
        fake_database = type(
            "FakeDatabase",
            (),
            {
                "connected": False,
                "connect": unittest.mock.Mock(),
                "ping": unittest.mock.Mock(),
                "run_demo_round_trip": unittest.mock.Mock(return_value={"inserted": 1, "total_rows": 3}),
                "close": unittest.mock.Mock(),
            },
        )()

        with patch("product.app.backend.app.main.build_mysql_client", return_value=fake_database), patch(
            "product.app.backend.app.main.create_report_scheduler"
        ) as create_report_scheduler:
            create_report_scheduler.return_value = type(
                "FakeScheduler",
                (),
                {
                    "running": False,
                    "start": AsyncMock(),
                    "stop": AsyncMock(),
                },
            )()
            with TestClient(app) as client:
                app.state.database = fake_database
                response = client.post("/api/database/demo", json={"note": "hello"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["inserted"], 1)
        self.assertEqual(response.json()["total_rows"], 3)
        fake_database.run_demo_round_trip.assert_called_once_with(note="hello")

    def test_run_demo_round_trip_uses_mysql_cli_and_parses_count(self) -> None:
        """验证示例写入会通过 mysql CLI 执行并解析查询结果。"""
        client = MysqlClient(
            settings=MysqlConnectionSettings(
                host="127.0.0.1",
                port=3306,
                database="astock",
                user="astock",
                password="astock-local-password",
            ),
        )

        completed = type(
            "CompletedProcess",
            (),
            {
                "returncode": 0,
                "stdout": "4\n",
                "stderr": "",
            },
        )()

        with patch("product.app.backend.infrastructure.database.mysql.subprocess.run", return_value=completed) as run:
            result = client.run_demo_round_trip(note="O'Reilly")

        self.assertEqual(result, {"inserted": 1, "total_rows": 4})
        args, kwargs = run.call_args
        self.assertIn("--protocol=tcp", args[0])
        self.assertIn("--database", args[0])
        self.assertEqual(kwargs["env"]["MYSQL_PWD"], "astock-local-password")
        self.assertIn("O''Reilly", kwargs["input"])


class ManualDailyReportApiTests(unittest.TestCase):
    """手动触发每日复盘邮件接口测试。"""

    def test_daily_report_defaults_endpoint_returns_today_and_recipient(self) -> None:
        """验证默认值接口会返回日期和默认收件人。"""
        fake_scheduler = type(
            "FakeScheduler",
            (),
            {
                "running": False,
                "start": AsyncMock(),
                "stop": AsyncMock(),
            },
        )()
        fake_database = type(
            "FakeDatabase",
            (),
            {
                "connected": False,
                "connect": unittest.mock.Mock(),
                "ping": unittest.mock.Mock(),
                "run_demo_round_trip": unittest.mock.Mock(return_value={"inserted": 1, "total_rows": 1}),
                "close": unittest.mock.Mock(),
            },
        )()

        with patch("product.app.backend.app.main.create_report_scheduler", return_value=fake_scheduler), patch(
            "product.app.backend.app.main.build_mysql_client", return_value=fake_database
        ):
            with TestClient(app) as client:
                response = client.get("/api/reports/muyuan/daily/defaults")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertRegex(payload["report_date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue(payload["recipient"])

    def test_daily_report_send_endpoint_triggers_workflow_with_user_selection(self) -> None:
        """验证手动发送接口会把用户选择传给日报工作流。"""
        fake_scheduler = type(
            "FakeScheduler",
            (),
            {
                "running": False,
                "start": AsyncMock(),
                "stop": AsyncMock(),
            },
        )()
        fake_database = type(
            "FakeDatabase",
            (),
            {
                "connected": False,
                "connect": unittest.mock.Mock(),
                "ping": unittest.mock.Mock(),
                "run_demo_round_trip": unittest.mock.Mock(return_value={"inserted": 1, "total_rows": 1}),
                "close": unittest.mock.Mock(),
            },
        )()

        workflow_result = (
            Path("/tmp/muyuan-daily.md"),
            "markdown body",
            {
                "valuation_trace": [
                    {
                        "round_index": 1,
                        "valuation_status": "need_more_data",
                        "valuation_summary": "first round",
                        "data_needs": ["PE", "PB"],
                        "prefill_notes": ["prefill"],
                        "notes": ["need more"],
                        "acquisition_attempts": [
                            {
                                "need_title": "PE",
                                "provider_name": "tushare",
                                "status": "success",
                                "evidence_count": 2,
                                "query": "PE",
                                "message": "ok",
                            }
                        ],
                    },
                    {
                        "round_index": 2,
                        "valuation_status": "converged",
                        "valuation_summary": "second round",
                        "data_needs": [],
                        "prefill_notes": [],
                        "notes": [],
                        "acquisition_attempts": [],
                    }
                ],
                "valuation_termination_reason": "complete",
            },
        )

        with patch("product.app.backend.app.main.create_report_scheduler", return_value=fake_scheduler), patch(
            "product.app.backend.app.main.build_mysql_client", return_value=fake_database
        ), patch(
            "product.app.backend.app.main.run_report_workflow_async", AsyncMock(return_value=workflow_result)
        ) as mock_workflow:
            with TestClient(app) as client:
                response = client.post(
                    "/api/reports/muyuan/daily/send",
                    json={"report_date": "2026-07-18", "recipient": "alice@example.com"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["report_date"], "2026-07-18")
        self.assertEqual(payload["recipient"], "alice@example.com")
        self.assertEqual(payload["valuation_rounds"], 2)
        self.assertEqual(payload["valuation_trace"][0]["acquisition_attempts"][0]["provider_name"], "tushare")
        mock_workflow.assert_awaited_once_with(
            report_date="2026-07-18",
            force=True,
            recipient="alice@example.com",
        )


if __name__ == "__main__":
    unittest.main()
