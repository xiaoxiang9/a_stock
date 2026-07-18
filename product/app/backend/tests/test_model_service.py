"""模型服务公共层测试。

职责：
- 验证 ModelService 能按配置路由到 DeepSeek 或 Codex CLI。
- 验证外部模型返回内容会被解析为 JSON 对象。
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from product.app.backend.infrastructure.model_service import ModelService
from product.app.backend.infrastructure.config.project_config import load_project_config


class ModelServiceRoutingTests(unittest.TestCase):
    """模型路由和 JSON 输出解析测试。"""

    def test_deepseek_route_parses_api_response(self) -> None:
        """验证 DeepSeek API 响应能被解析为业务 JSON。"""
        toml_text = """
[model]
provider = "deepseek"
profile = "external"
name = "deepseek-v4-pro"
api_key_env = "DEEPSEEK_API_KEY"
base_url = "https://api.deepseek.com"
thinking = true
reasoning_effort = "high"

[smtp]
host = "smtp.example.com"
port = 465
user = "sender@example.com"
from_addr = "sender@example.com"
""".strip()

        fake_response_payload = {
            "choices": [
                {"message": {"content": json.dumps({"ok": True}, ensure_ascii=False)}},
            ]
        }

        class FakeResponse:
            """模拟 urllib 返回的 HTTP 响应对象。"""

            def __init__(self, payload: dict) -> None:
                """保存待返回的模拟响应内容。"""
                self._payload = payload

            def read(self) -> bytes:
                """返回 JSON 字节流，模拟真实 HTTP 响应体。"""
                return json.dumps(self._payload, ensure_ascii=False).encode("utf-8")

            def __enter__(self) -> "FakeResponse":
                """支持 with 上下文管理协议。"""
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                """退出上下文时不吞掉异常。"""
                return False

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "project.toml"
            config_path.write_text(toml_text, encoding="utf-8")
            config = load_project_config(config_path)
            service = ModelService.from_project_config(config)

        with (
            patch.dict("os.environ", {"DEEPSEEK_API_KEY": "sk-test"}, clear=False),
            patch("product.app.backend.infrastructure.model_service.urllib_request.urlopen", return_value=FakeResponse(fake_response_payload)) as mock_urlopen,
        ):
            output = service.complete_json("请输出 JSON")

        self.assertEqual(output, {"ok": True})
        self.assertTrue(mock_urlopen.called)

    def test_external_profile_routes_to_deepseek(self) -> None:
        """验证 external + deepseek 配置会路由到 DeepSeek。"""
        toml_text = """
[model]
provider = "deepseek"
profile = "external"
name = "deepseek-v4-pro"
api_key_env = "DEEPSEEK_API_KEY"
base_url = "https://api.deepseek.com"
thinking = true
reasoning_effort = "high"

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

        with patch.object(service, "_run_deepseek", return_value=json.dumps({"ok": True})) as mock_deepseek:
            output = service.complete_json("请输出 JSON")

        self.assertEqual(output, {"ok": True})
        mock_deepseek.assert_called_once()

    def test_current_profile_routes_to_codex(self) -> None:
        """验证 current profile 会路由到 Codex CLI。"""
        toml_text = """
[model]
provider = "codex"
profile = "current"
use_oss = false
local_provider = ""

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

        with patch.object(service, "_run_codex", return_value=json.dumps({"ok": True})) as mock_codex:
            output = service.complete_json("请输出 JSON")

        self.assertEqual(output, {"ok": True})
        mock_codex.assert_called_once()

    def test_complete_json_repairs_invalid_json_and_writes_audit_log(self) -> None:
        """验证 JSON 解析失败时会写审计日志并尝试修复。"""
        toml_text = """
[model]
provider = "deepseek"
profile = "external"
name = "deepseek-v4-pro"
api_key_env = "DEEPSEEK_API_KEY"
base_url = "https://api.deepseek.com"
thinking = true
reasoning_effort = "high"

[smtp]
host = "smtp.example.com"
port = 465
user = "sender@example.com"
from_addr = "sender@example.com"
""".strip()

        invalid_json = '{"ok": true, "broken": "x" "y"}'
        repaired_json = json.dumps({"ok": True}, ensure_ascii=False)

        class FakeResponse:
            def __init__(self, payload: dict) -> None:
                self._payload = payload

            def read(self) -> bytes:
                return json.dumps(self._payload, ensure_ascii=False).encode("utf-8")

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "project.toml"
            config_path.write_text(toml_text, encoding="utf-8")
            config = load_project_config(config_path)
            service = ModelService.from_project_config(config)

            audit_dir = Path(tmpdir) / "audit"
            with (
                patch.dict("os.environ", {"DEEPSEEK_API_KEY": "sk-test", "ASTOCK_MODEL_AUDIT_DIR": str(audit_dir)}, clear=False),
                patch.object(service, "_run", side_effect=[invalid_json, repaired_json]) as mock_run,
            ):
                output = service.complete_json("请输出 JSON")

            audit_files = list(audit_dir.glob("model-audit-*.jsonl"))
            self.assertTrue(audit_files)
            audit_text = audit_files[0].read_text(encoding="utf-8")

        self.assertEqual(output, {"ok": True})
        self.assertEqual(mock_run.call_count, 2)
        self.assertIn("json-parse-failed", audit_text)
        self.assertIn("json-repaired", audit_text)


if __name__ == "__main__":
    unittest.main()
