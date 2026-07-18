"""部署检查工具测试。

职责：
- 验证私密配置、公开配置和部署前检查函数的返回口径。
- 保护安装脚本和启动脚本共用的检查逻辑。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from product.app.backend.infrastructure.deployment_checks import (
    collect_private_config_problems,
    collect_public_config_problems,
)


class DeploymentChecksTests(unittest.TestCase):
    """部署检查测试。"""

    def test_collect_private_config_problems_reports_blank_required_values(self) -> None:
        """验证私密配置缺少必填值时会返回明确原因。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "private.local.toml"
            config_path.write_text(
                """
[smtp]
password = "smtp-secret"

[secrets]
deepseek_api_key = "secret"
tushare_token = "token"

[mysql]
user = "astock"
password = ""
""".strip()
                + "\n",
                encoding="utf-8",
            )

            problems = collect_private_config_problems(config_path)

        self.assertEqual(
            problems,
            ["Private config missing mysql.password"],
        )

    def test_collect_public_config_problems_reports_missing_file(self) -> None:
        """验证公开配置缺失时会返回明确原因。"""
        problems = collect_public_config_problems("/tmp/not-exist-project.toml")

        self.assertEqual(problems, ["Public config not found: /tmp/not-exist-project.toml"])


if __name__ == "__main__":
    unittest.main()
