"""项目全局配置测试。

职责：
- 验证 TOML 配置能被正确读取为类型化配置对象。
- 验证模型服务能从项目配置中构建运行时参数。
"""

import tempfile
import unittest
from pathlib import Path

from product.app.backend.infrastructure.config.project_config import load_project_config
from product.app.backend.infrastructure.model_service import ModelService


class ProjectConfigTests(unittest.TestCase):
    """项目配置读取测试。"""

    def test_load_project_config_reads_documented_values(self) -> None:
        """验证配置文件中的关键字段都能按文档口径读取。"""
        toml_text = """
[backend]
title = "A Stock API"
description = "Python + Vue starter API"
version = "0.1.0"
cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
public_base_url = "http://127.0.0.1:8000"

[runtime]
python_path = "/custom/python"
reexec_flag = "MUYUAN_REEXEC"

[model]
provider = "deepseek"
profile = "external"
name = "deepseek-v4-pro"
api_key_env = "DEEPSEEK_API_KEY"
base_url = "https://api.deepseek.com"
thinking = true
reasoning_effort = "high"
use_oss = false
local_provider = ""

[smtp]
host = "smtp.example.com"
port = 465
user = "sender@example.com"
from_addr = "sender@example.com"

[email]
recipient = "376597874@qq.com"

[launchd]
label = "com.astock.muyuan-nightly"
hour = 1
minute = 12

[tushare]
token_env = "TUSHARE_TOKEN"
ts_code = "002714.SZ"

[report]
output_dir = "product/reports/daily"

[frontend]
dev_host = "0.0.0.0"
dev_port = 5173
api_base_path = "/api"
docs_url = "http://127.0.0.1:8000/docs"

[market_data]
vix_data_url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
vix_source_url = "https://www.cboe.com/tradable_products/vix/vix_historical_data/"
cnn_data_url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
cnn_source_url = "https://www.cnn.com/markets/fear-and-greed"
nasdaq_data_url = "https://api.nasdaq.com/api/quote/QQQ/historical"
nasdaq_source_url = "https://www.nasdaq.com/market-activity/etf/qqq/historical"
request_user_agent = "Test-UA"
request_accept = "application/json"
request_accept_language = "zh-CN"
cache_ttl_seconds = 123
request_timeout_seconds = 11.5
connect_timeout_seconds = 4.5

[mysql]
host = "127.0.0.1"
port = 3306
database = "astock"
connect_timeout_seconds = 6.0
""".strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "project.toml"
            config_path.write_text(toml_text, encoding="utf-8")

            config = load_project_config(config_path)

        self.assertEqual(config.backend.title, "A Stock API")
        self.assertEqual(config.backend.version, "0.1.0")
        self.assertEqual(config.backend.cors_origins, ["http://localhost:5173", "http://127.0.0.1:5173"])
        self.assertEqual(config.backend.public_base_url, "http://127.0.0.1:8000")
        self.assertEqual(config.runtime.python_path, "/custom/python")
        self.assertEqual(config.runtime.reexec_flag, "MUYUAN_REEXEC")
        self.assertEqual(config.model.profile, "external")
        self.assertEqual(config.model.provider, "deepseek")
        self.assertEqual(config.model.name, "deepseek-v4-pro")
        self.assertEqual(config.model.api_key_env, "DEEPSEEK_API_KEY")
        self.assertEqual(config.model.base_url, "https://api.deepseek.com")
        self.assertTrue(config.model.thinking)
        self.assertEqual(config.model.reasoning_effort, "high")
        self.assertEqual(config.smtp.host, "smtp.example.com")
        self.assertEqual(config.smtp.port, 465)
        self.assertEqual(config.smtp.user, "sender@example.com")
        self.assertEqual(config.smtp.from_addr, "sender@example.com")
        self.assertEqual(config.email.recipient, "376597874@qq.com")
        self.assertEqual(config.launchd.hour, 1)
        self.assertEqual(config.launchd.minute, 12)
        self.assertEqual(config.tushare.ts_code, "002714.SZ")
        self.assertEqual(config.report.output_dir, "product/reports/daily")
        self.assertEqual(config.frontend.dev_host, "0.0.0.0")
        self.assertEqual(config.frontend.dev_port, 5173)
        self.assertEqual(config.frontend.api_base_path, "/api")
        self.assertEqual(config.frontend.docs_url, "http://127.0.0.1:8000/docs")
        self.assertEqual(config.market_data.request_user_agent, "Test-UA")
        self.assertEqual(config.market_data.cache_ttl_seconds, 123)
        self.assertEqual(config.mysql.host, "127.0.0.1")
        self.assertEqual(config.mysql.port, 3306)
        self.assertEqual(config.mysql.database, "astock")
        self.assertEqual(config.mysql.connect_timeout_seconds, 6.0)


class ModelServiceTests(unittest.TestCase):
    """模型服务与项目配置集成测试。"""

    def test_model_service_builds_from_project_config(self) -> None:
        """验证 ModelService 能使用传入的 ProjectConfig 初始化。"""
        toml_text = """
[model]
provider = "codex"
profile = "current"
name = "deepseek-v4-pro"
use_oss = true
local_provider = "openai"

[smtp]
host = "smtp.example.com"
port = 465
user = "sender@example.com"
from_addr = "sender@example.com"
""".strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "project.toml"
            config_path.write_text(toml_text, encoding="utf-8")

            config = load_project_config(config_path)
            service = ModelService.from_project_config(config)

        self.assertEqual(service.runtime.profile, "current")
        self.assertEqual(service.runtime.provider, "codex")
        self.assertEqual(service.runtime.name, "deepseek-v4-pro")
        self.assertTrue(service.runtime.use_oss)
        self.assertEqual(service.runtime.local_provider, "openai")


if __name__ == "__main__":
    unittest.main()
