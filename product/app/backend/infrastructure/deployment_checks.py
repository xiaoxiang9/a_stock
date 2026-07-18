#!/usr/bin/env python3
"""部署前检查工具。

职责：
- 校验公开配置和私密配置是否齐全。
- 校验后端 Python 依赖和前端 Node 依赖是否存在。
- 为安装脚本和启动脚本提供同一套确定性检查口径。

边界：
- 本文件只做检查与报告，不执行安装和不启动服务。
- 如果发现缺失项，直接返回可读原因，便于脚本层阻断。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from product.app.backend.infrastructure.config.private_config import load_private_config
from product.app.backend.infrastructure.config.project_config import DEFAULT_CONFIG_PATH, load_project_config
from product.app.backend.infrastructure.database import build_mysql_client


DEFAULT_BACKEND_PYTHON = ROOT / "product" / "app" / "backend" / ".venv" / "bin" / "python"
DEFAULT_FRONTEND_DIR = ROOT / "product" / "app" / "frontend"


def collect_private_config_problems(config_path: str | Path | None = None) -> list[str]:
    """读取私密配置，并返回可读的配置问题列表。"""
    try:
        load_private_config(config_path)
    except Exception as exc:
        return [str(exc)]
    return []


def collect_public_config_problems(config_path: str | Path | None = None) -> list[str]:
    """读取公开配置，并返回可读的配置问题列表。"""
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    if not path.exists():
        return [f"Public config not found: {path}"]
    try:
        load_project_config(path)
    except Exception as exc:
        return [str(exc)]
    return []


def collect_backend_dependency_problems(python_path: str | Path | None = None) -> list[str]:
    """检查后端 Python 依赖是否就绪。"""
    interpreter = Path(python_path) if python_path is not None else DEFAULT_BACKEND_PYTHON
    if not interpreter.exists():
        return [f"Backend Python not found: {interpreter}"]
    command = [
        str(interpreter),
        "-c",
        "import fastapi, httpx, akshare, tushare, uvicorn; print('ok')",
    ]
    result = subprocess.run(command, capture_output=True, text=True, cwd=str(ROOT))
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "backend dependency check failed"
        return [stderr]
    return []


def collect_frontend_dependency_problems(frontend_dir: str | Path | None = None) -> list[str]:
    """检查前端运行依赖是否就绪。"""
    directory = Path(frontend_dir) if frontend_dir is not None else DEFAULT_FRONTEND_DIR
    if not directory.exists():
        return [f"Frontend directory not found: {directory}"]
    if not shutil_which("node"):
        return ["node is not installed"]
    if not shutil_which("npm"):
        return ["npm is not installed"]
    if not (directory / "node_modules").exists():
        return [f"Frontend dependencies not installed: {directory / 'node_modules'}"]
    return []


def collect_installation_problems() -> list[str]:
    """汇总安装前必须通过的检查。"""
    problems: list[str] = []
    problems.extend(collect_public_config_problems())
    problems.extend(collect_private_config_problems())
    return problems


def collect_database_connection_problems(
    project_config_path: str | Path | None = None,
    private_config_path: str | Path | None = None,
) -> list[str]:
    """检查 MySQL 连接是否可用。"""
    try:
        project_config = load_project_config(project_config_path)
        private_config = load_private_config(private_config_path)
        client = build_mysql_client(project_config, private_config)
        try:
            client.connect()
            client.ping()
        finally:
            client.close()
    except Exception as exc:
        return [str(exc)]
    return []


def collect_startup_problems() -> list[str]:
    """汇总启动前必须通过的检查。"""
    problems: list[str] = []
    problems.extend(collect_public_config_problems())
    problems.extend(collect_private_config_problems())
    problems.extend(collect_backend_dependency_problems())
    problems.extend(collect_frontend_dependency_problems())
    return problems


def shutil_which(command: str) -> str | None:
    """轻量封装命令存在性检测，避免脚本重复写判断。"""
    from shutil import which

    return which(command)


def _print_problems(problems: Iterable[str]) -> None:
    """按行打印问题列表。"""
    for problem in problems:
        print(problem)


def main() -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="A Stock deployment checks")
    parser.add_argument(
        "check",
        choices=["public-config", "private-config", "backend-deps", "frontend-deps", "mysql", "install", "startup"],
    )
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--private-config", default=None, help="私密配置文件路径")
    parser.add_argument("--python", default=None, help="后端 Python 解释器路径")
    parser.add_argument("--frontend-dir", default=None, help="前端目录路径")
    args = parser.parse_args()

    if args.check == "public-config":
        problems = collect_public_config_problems(args.config)
    elif args.check == "private-config":
        problems = collect_private_config_problems(args.config)
    elif args.check == "backend-deps":
        problems = collect_backend_dependency_problems(args.python)
    elif args.check == "frontend-deps":
        problems = collect_frontend_dependency_problems(args.frontend_dir)
    elif args.check == "mysql":
        problems = collect_database_connection_problems(args.config, args.private_config)
    elif args.check == "install":
        problems = collect_installation_problems()
    else:
        problems = collect_startup_problems()

    if problems:
        _print_problems(problems)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
