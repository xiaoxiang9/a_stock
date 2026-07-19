"""app 启动脚本回归测试。

职责：
- 验证 `product/app/scripts/start.sh` 的端口释放逻辑能够真正回收监听进程。
- 保护“启动前先释放端口，再进入后续启动流程”的部署边界。
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path


class AppStartScriptTests(unittest.TestCase):
    """app 启动脚本测试。"""

    def test_force_release_listening_port_kills_listener(self) -> None:
        """验证启动脚本的端口释放逻辑会在检测到占用后完成兜底释放。"""
        start_script = Path(__file__).resolve().parents[2] / "scripts" / "start.sh"
        env = os.environ.copy()
        env["ASTOCK_APP_START_SH_SOURCE_ONLY"] = "1"
        command = (
            f'source "{start_script}" '
            f'&& mock_released=0 '
            f'&& list_listening_pids() {{ [ "$mock_released" = "1" ] || echo 8000; }} '
            f'&& kill_process_tree() {{ mock_released=1; }} '
            f'&& force_release_listening_port "测试" 8000 '
            f'&& [ "$mock_released" = "1" ]'
        )
        result = subprocess.run(["bash", "-lc", command], env=env, capture_output=True, text=True, check=False)

        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
