#!/usr/bin/env python3

"""牧原股份日报草稿生成脚本。

职责：
- 根据日期从日报模板生成 Markdown 草稿。
- 将草稿写入项目配置指定的报告目录。

边界：
- 本文件只负责模板占位替换和文件落盘。
- 不获取行情数据，不生成投研判断。
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from product.app.backend.infrastructure.config.project_config import load_project_config

TEMPLATE = ROOT / "product" / "reports" / "daily" / "muyuan_21_template.md"
OUTPUT_DIR = ROOT / load_project_config().report.output_dir


def build_output_path(target_date: str) -> Path:
    """根据日期生成日报草稿输出路径。"""
    return OUTPUT_DIR / f"{target_date}-muyuan.md"


def render_template(target_date: str) -> str:
    """渲染日报模板。

    这个脚本只负责生成占位草稿，不做任何投研判断。
    """
    content = TEMPLATE.read_text(encoding="utf-8")
    return content.replace("{{date}}", target_date)


def main() -> int:
    """命令行入口，解析日期和覆盖参数后生成草稿。"""
    parser = argparse.ArgumentParser(description="Generate Muyuan nightly review stub.")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Report date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the file if it already exists.",
    )
    args = parser.parse_args()

    output_path = build_output_path(args.date)
    if output_path.exists() and not args.force:
        print(f"skip: {output_path} already exists")
        return 0

    output_path.write_text(render_template(args.date), encoding="utf-8")
    print(f"generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
