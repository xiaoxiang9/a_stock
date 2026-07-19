"""子系统配置加载器测试。

职责：
- 验证 app、data、agents 三套配置加载器各自只读取自己的配置目录。
- 保护“子系统配置与配置加载器相互独立”的目录边界。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from product.agents.config.agents_config import load_agents_config
from product.agents.config.private_config import load_private_agents_config
from product.data.config.data_config import load_data_config
from product.data.config.private_config import load_private_data_config


class DataConfigLoaderTests(unittest.TestCase):
    """data 子系统配置加载测试。"""

    def test_load_data_config_reads_data_toml(self) -> None:
        """验证 data 配置只读取 data 子系统自己的 TOML。"""
        config = load_data_config()

        self.assertEqual(config.market_data.vix_source_url, "https://www.cboe.com/tradable_products/vix/vix_historical_data/")
        self.assertEqual(config.market_data.cache_ttl_seconds, 300)
        self.assertEqual(config.tushare.ts_code, "002714.SZ")
        self.assertEqual(config.mysql.host, "192.168.3.166")
        self.assertEqual(config.mysql.database, "astock")
        self.assertEqual(config.api.port, 8010)
        self.assertEqual(config.monthly_refresh.label, "com.astock.data-monthly-refresh")
        self.assertEqual(config.monthly_refresh.day, 3)
        self.assertEqual(config.monthly_refresh.hour, 1)
        self.assertEqual(config.monthly_refresh.minute, 12)

    def test_load_private_data_config_reads_local_file(self) -> None:
        """验证 data 私密配置可独立读取，不依赖 app 私密配置。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "private.local.toml"
            config_path.write_text(
                """
[secrets]
foo = "bar"

[mysql]
user = "data-user"
password = "data-pass"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            config = load_private_data_config(config_path)

        self.assertEqual(config.secrets, {"foo": "bar"})
        self.assertEqual(config.mysql, {"user": "data-user", "password": "data-pass"})


class AgentsConfigLoaderTests(unittest.TestCase):
    """agents 子系统配置加载测试。"""

    def test_load_agents_config_reads_agents_toml(self) -> None:
        """验证 agents 配置只读取 agents 子系统自己的 TOML。"""
        config = load_agents_config()

        self.assertEqual(config.model.provider, "deepseek")
        self.assertEqual(config.model.profile, "external")
        self.assertEqual(config.workflow.default_graph, "research")
        self.assertTrue(config.workflow.enable_evidence_collection)
        self.assertEqual(config.search.websearch_command, "websearch-deepseek")
        self.assertTrue(config.search.websearch_enabled)

    def test_load_private_agents_config_reads_local_file(self) -> None:
        """验证 agents 私密配置可独立读取，不依赖 app 私密配置。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "private.local.toml"
            config_path.write_text(
                """
[secrets]
api_key = "agent-key"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            config = load_private_agents_config(config_path)

        self.assertEqual(config.secrets, {"api_key": "agent-key"})


if __name__ == "__main__":
    unittest.main()
