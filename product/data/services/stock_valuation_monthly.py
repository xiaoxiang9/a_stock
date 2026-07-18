"""股票月度 PE/PB 存储与查询服务。

职责：
- 将 Tushare 日频估值数据压缩为月频序列。
- 将月度序列落到 data 子系统自己的 MySQL 表中。
- 对外提供初始化、月更保鲜和查询结果构造。

边界：
- 这里只负责确定性数据流转、数据库读写和数据整合。
- 不承载投资结论，也不直接依赖 app 子系统。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from html import escape
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from shutil import which
from typing import Any, Iterable, Sequence

from product.data.config.data_config import DataConfig, load_data_config
from product.data.config.private_config import DataPrivateConfig, load_private_data_config
from product.data.fetchers.valuation_monthly import fetch_monthly_valuation_points
from product.data.processors.stock_valuation_monthly import (
    build_monthly_valuation_payload,
    summarize_monthly_valuation_points,
)


TABLE_NAME = "stock_valuation_monthly"


@dataclass(frozen=True)
class MysqlConnectionSettings:
    """MySQL 连接参数。"""

    host: str
    port: int
    database: str
    user: str
    password: str
    connect_timeout_seconds: float = 5.0


def _parse_date(value: str | None) -> date:
    """把业务日期转换为 date 对象。"""
    if not value:
        return date.today()
    if "-" in value:
        return datetime.strptime(value, "%Y-%m-%d").date()
    return datetime.strptime(value, "%Y%m%d").date()


def _format_date(value: date) -> str:
    """把 date 转换成 YYYYMMDD。"""
    return value.strftime("%Y%m%d")


def _month_floor(value: date) -> date:
    """把日期归一到所在月的第一天。"""
    return value.replace(day=1)


def _format_date_human(value: str | None) -> str:
    """把 YYYYMMDD 或 YYYY-MM-DD 转换成 YYYY-MM-DD。"""
    if not value:
        return ""
    cleaned = value.strip()
    if "-" in cleaned:
        return cleaned
    if len(cleaned) == 8:
        return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:8]}"
    return cleaned


def _sql_escape_text(value: str) -> str:
    """对 SQL 文本做最小转义。"""
    return value.replace("\\", "\\\\").replace("'", "''")


def _json_text(value: Any) -> str:
    """把结构化数据序列化为稳定 JSON。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _sql_value(value: Any) -> str:
    """把 Python 值转换成 SQL 字面量。"""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    return f"'{_sql_escape_text(text)}'"


def _runtime_python_path() -> str:
    """选择 data 子系统可用的 Python 解释器。"""
    project_python = Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python"
    if project_python.exists():
        return str(project_python)
    return sys.executable


def _resolve_mysql_settings(
    config: DataConfig | None = None,
    private_config: DataPrivateConfig | None = None,
) -> MysqlConnectionSettings:
    """从 data 子系统配置拼装 MySQL 连接参数。"""
    public_config = config or load_data_config()
    secret_config = private_config or load_private_data_config()
    mysql_user = secret_config.mysql.get("user", "").strip()
    mysql_password = secret_config.mysql.get("password", "").strip()
    if not mysql_user or not mysql_password:
        raise RuntimeError("data 私密配置缺少 mysql.user 或 mysql.password")
    return MysqlConnectionSettings(
        host=public_config.mysql.host,
        port=public_config.mysql.port,
        database=public_config.mysql.database,
        user=mysql_user,
        password=mysql_password,
        connect_timeout_seconds=public_config.mysql.connect_timeout_seconds,
    )


class MysqlCliStore:
    """通过本机 mysql CLI 访问 data 子系统数据库。"""

    def __init__(self, settings: MysqlConnectionSettings) -> None:
        """初始化 MySQL CLI 存储访问器。"""
        self._settings = settings

    def _mysql_cli(self) -> str:
        """解析 mysql CLI 路径。"""
        return which("mysql") or "mysql"

    def _run_sql(self, sql: str) -> str:
        """通过 mysql CLI 执行 SQL 并返回 stdout。"""
        command = [
            self._mysql_cli(),
            "--protocol=tcp",
            "--host",
            self._settings.host,
            "--port",
            str(self._settings.port),
            "--user",
            self._settings.user,
            "--database",
            self._settings.database,
            "--batch",
            "--skip-column-names",
            "--raw",
        ]
        env = os.environ.copy()
        env["MYSQL_PWD"] = self._settings.password
        result = subprocess.run(
            command,
            input=sql,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[4]),
            env=env,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "mysql command failed"
            raise RuntimeError(stderr)
        return result.stdout.strip()

    def ensure_schema(self) -> None:
        """创建月度估值表。"""
        sql = f"""
CREATE TABLE IF NOT EXISTS `{TABLE_NAME}` (
    `ts_code` VARCHAR(20) NOT NULL,
    `stock_name` VARCHAR(128) NOT NULL DEFAULT '',
    `listed_date` VARCHAR(10) NOT NULL DEFAULT '',
    `months_json` LONGTEXT NOT NULL,
    `pe_values_json` LONGTEXT NOT NULL,
    `pb_values_json` LONGTEXT NOT NULL,
    `latest_month` VARCHAR(7) NOT NULL DEFAULT '',
    `latest_trade_date` VARCHAR(8) NOT NULL DEFAULT '',
    `latest_pe_ttm` DECIMAL(18,6) DEFAULT NULL,
    `latest_pb` DECIMAL(18,6) DEFAULT NULL,
    `pe_percentile` DECIMAL(8,4) DEFAULT NULL,
    `pb_percentile` DECIMAL(8,4) DEFAULT NULL,
    `series_count` INT NOT NULL DEFAULT 0,
    `source` VARCHAR(32) NOT NULL DEFAULT 'Tushare',
    `source_meta_json` LONGTEXT NOT NULL,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`ts_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
        self._run_sql(sql)

    def upsert_record(self, payload: dict[str, Any]) -> None:
        """写入或更新单只股票的月度估值记录。"""
        sql = f"""
INSERT INTO `{TABLE_NAME}` (
    `ts_code`,
    `stock_name`,
    `listed_date`,
    `months_json`,
    `pe_values_json`,
    `pb_values_json`,
    `latest_month`,
    `latest_trade_date`,
    `latest_pe_ttm`,
    `latest_pb`,
    `pe_percentile`,
    `pb_percentile`,
    `series_count`,
    `source`,
    `source_meta_json`
) VALUES (
    {_sql_value(payload["ts_code"])},
    {_sql_value(payload.get("stock_name", ""))},
    {_sql_value(payload.get("listed_date", ""))},
    {_sql_value(_json_text(payload.get("months", [])))},
    {_sql_value(_json_text(payload.get("pe_values", [])))},
    {_sql_value(_json_text(payload.get("pb_values", [])))},
    {_sql_value(payload.get("latest_month", ""))},
    {_sql_value(payload.get("latest_trade_date", ""))},
    {_sql_value(payload.get("latest_pe_ttm"))},
    {_sql_value(payload.get("latest_pb"))},
    {_sql_value(payload.get("pe_percentile"))},
    {_sql_value(payload.get("pb_percentile"))},
    {int(payload.get("series_count", 0))},
    {_sql_value(payload.get("source", "Tushare"))},
    {_sql_value(_json_text(payload.get("source_meta", {})))}
)
ON DUPLICATE KEY UPDATE
    `stock_name` = VALUES(`stock_name`),
    `listed_date` = VALUES(`listed_date`),
    `months_json` = VALUES(`months_json`),
    `pe_values_json` = VALUES(`pe_values_json`),
    `pb_values_json` = VALUES(`pb_values_json`),
    `latest_month` = VALUES(`latest_month`),
    `latest_trade_date` = VALUES(`latest_trade_date`),
    `latest_pe_ttm` = VALUES(`latest_pe_ttm`),
    `latest_pb` = VALUES(`latest_pb`),
    `pe_percentile` = VALUES(`pe_percentile`),
    `pb_percentile` = VALUES(`pb_percentile`),
    `series_count` = VALUES(`series_count`),
    `source` = VALUES(`source`),
    `source_meta_json` = VALUES(`source_meta_json`);
"""
        self._run_sql(sql)

    def fetch_record(self, ts_code: str) -> dict[str, Any] | None:
        """读取单只股票的月度估值记录。"""
        sql = f"""
SELECT
    `ts_code`,
    `stock_name`,
    `listed_date`,
    `months_json`,
    `pe_values_json`,
    `pb_values_json`,
    `latest_month`,
    `latest_trade_date`,
    `latest_pe_ttm`,
    `latest_pb`,
    `pe_percentile`,
    `pb_percentile`,
    `series_count`,
    `source`,
    `source_meta_json`,
    DATE_FORMAT(`updated_at`, '%Y-%m-%d %H:%i:%s')
FROM `{TABLE_NAME}`
WHERE `ts_code` = '{_sql_escape_text(ts_code)}'
LIMIT 1;
"""
        output = self._run_sql(sql)
        if not output:
            return None
        columns = [
            "ts_code",
            "stock_name",
            "listed_date",
            "months_json",
            "pe_values_json",
            "pb_values_json",
            "latest_month",
            "latest_trade_date",
            "latest_pe_ttm",
            "latest_pb",
            "pe_percentile",
            "pb_percentile",
            "series_count",
            "source",
            "source_meta_json",
            "updated_at",
        ]
        values = output.split("\t")
        row = dict(zip(columns, values))
        row["months"] = json.loads(row["months_json"]) if row.get("months_json") else []
        row["pe_values"] = json.loads(row["pe_values_json"]) if row.get("pe_values_json") else []
        row["pb_values"] = json.loads(row["pb_values_json"]) if row.get("pb_values_json") else []
        row["source_meta"] = json.loads(row["source_meta_json"]) if row.get("source_meta_json") else {}
        row["listed_date"] = _format_date_human(row.get("listed_date"))
        row["latest_pe_ttm"] = float(row["latest_pe_ttm"]) if row.get("latest_pe_ttm") else None
        row["latest_pb"] = float(row["latest_pb"]) if row.get("latest_pb") else None
        row["pe_percentile"] = float(row["pe_percentile"]) if row.get("pe_percentile") else 0.0
        row["pb_percentile"] = float(row["pb_percentile"]) if row.get("pb_percentile") else 0.0
        row["series_count"] = int(row["series_count"]) if row.get("series_count") else 0
        return row

    def fetch_tracked_records(self) -> list[dict[str, Any]]:
        """读取当前数据库中已经维护的股票列表。

        这里只返回已经落库的标的，用作月度保鲜池的输入，不再重新拉取全市场上市清单。
        """
        sql = f"""
SELECT
    `ts_code`,
    `stock_name`,
    `listed_date`
FROM `{TABLE_NAME}`
ORDER BY `ts_code` ASC;
"""
        output = self._run_sql(sql)
        if not output:
            return []
        rows: list[dict[str, Any]] = []
        for line in output.splitlines():
            if not line.strip():
                continue
            ts_code, stock_name, listed_date = (line.split("\t") + ["", "", ""])[:3]
            rows.append(
                {
                    "ts_code": ts_code.strip(),
                    "stock_name": stock_name.strip(),
                    "listed_date": listed_date.strip(),
                }
            )
        return rows


def _merge_points(
    existing_points: Sequence[dict[str, Any]],
    new_points: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """按月份合并旧序列和新序列，保留每月最后一个交易日的数据。"""
    merged: dict[str, dict[str, Any]] = {str(point["month"]): dict(point) for point in existing_points}
    for point in new_points:
        month = str(point.get("month", "")).strip()
        if not month:
            continue
        merged[month] = {
            "month": month,
            "trade_date": str(point.get("trade_date", "")).strip(),
            "pe_ttm": point.get("pe_ttm"),
            "pb": point.get("pb"),
        }
    return [merged[key] for key in sorted(merged)]


def _normalize_stock_inputs(stocks: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    """把批量输入的股票参数归一化为可执行列表。

    这里只负责参数清洗和必填校验，不做任何股票筛选或业务判断。
    """
    normalized: list[dict[str, str]] = []
    for index, stock in enumerate(stocks):
        ts_code = str(stock.get("ts_code", "")).strip()
        if not ts_code:
            raise ValueError(f"bootstrap-all 第 {index + 1} 条输入缺少 ts_code")
        normalized.append(
            {
                "ts_code": ts_code,
                "stock_name": str(stock.get("stock_name", stock.get("name", ""))).strip(),
                "listed_date": str(stock.get("listed_date", stock.get("list_date", ""))).strip(),
            }
        )
    if not normalized:
        raise ValueError("bootstrap-all 需要至少提供一只股票")
    return normalized


class StockValuationMonthlyService:
    """股票月度 PE/PB 服务。"""

    def __init__(
        self,
        config: DataConfig | None = None,
        private_config: DataPrivateConfig | None = None,
    ) -> None:
        """初始化服务。"""
        self._config = config or load_data_config()
        self._private = private_config or load_private_data_config()
        self._token = self._private.secrets.get("tushare_token", "").strip()
        if not self._token:
            raise RuntimeError("data 私密配置缺少 secrets.tushare_token")
        self._store = MysqlCliStore(_resolve_mysql_settings(self._config, self._private))

    @property
    def api_prefix(self) -> str:
        """返回 API 前缀。"""
        return self._config.api.prefix

    def ensure_schema(self) -> None:
        """确保月度估值表已创建。"""
        self._store.ensure_schema()

    def bootstrap_stock(
        self,
        ts_code: str,
        *,
        stock_name: str = "",
        listed_date: str | None = None,
        as_of_date: str | None = None,
    ) -> dict[str, Any]:
        """初始化单只股票的全量月度估值历史。"""
        listed_day = _parse_date(listed_date) if listed_date else date(1990, 1, 1)
        start_date = _format_date(_month_floor(listed_day))
        points = fetch_monthly_valuation_points(
            self._token,
            ts_code=ts_code,
            start_date=start_date,
            end_date=as_of_date,
        )
        payload = build_monthly_valuation_payload(
            ts_code=ts_code,
            stock_name=stock_name,
            listed_date=listed_date,
            points=points,
        )
        if not payload.get("months"):
            raise RuntimeError(f"未获取到 {ts_code} 的月度估值数据，无法初始化")
        payload["source_meta"] = {
            "source": "Tushare",
            "mode": "bootstrap",
            "as_of_date": as_of_date or date.today().isoformat(),
        }
        self._store.upsert_record(payload)
        return payload

    def refresh_stock(
        self,
        ts_code: str,
        *,
        stock_name: str = "",
        listed_date: str | None = None,
        as_of_date: str | None = None,
        lookback_days: int = 120,
    ) -> dict[str, Any]:
        """刷新单只股票当前月度估值点。"""
        existing = self._store.fetch_record(ts_code)
        if existing is None:
            return self.bootstrap_stock(ts_code, stock_name=stock_name, listed_date=listed_date, as_of_date=as_of_date)

        end_day = _parse_date(as_of_date)
        start_day = end_day - timedelta(days=max(lookback_days, 1))
        fresh_points = fetch_monthly_valuation_points(
            self._token,
            ts_code=ts_code,
            start_date=_format_date(start_day),
            end_date=end_day.isoformat(),
        )
        merged_points = _merge_points(
            [
                {
                    "month": str(month),
                    "trade_date": "",
                    "pe_ttm": pe,
                    "pb": pb,
                }
                for month, pe, pb in zip(existing.get("months", []), existing.get("pe_values", []), existing.get("pb_values", []))
            ],
            fresh_points,
        )
        payload = build_monthly_valuation_payload(
            ts_code=ts_code,
            stock_name=stock_name or existing.get("stock_name", ""),
            listed_date=listed_date or existing.get("listed_date", ""),
            points=merged_points,
        )
        if not payload.get("months"):
            raise RuntimeError(f"未获取到 {ts_code} 的月度估值数据，无法刷新")
        payload["source_meta"] = {
            "source": "Tushare",
            "mode": "refresh",
            "as_of_date": as_of_date or date.today().isoformat(),
            "lookback_days": lookback_days,
        }
        self._store.upsert_record(payload)
        return payload

    def bootstrap_all(
        self,
        stocks: Sequence[dict[str, Any]],
        *,
        as_of_date: str | None = None,
    ) -> dict[str, Any]:
        """批量初始化输入股票列表的月度估值历史。"""
        target_stocks = _normalize_stock_inputs(stocks)
        processed = 0
        failed: list[dict[str, str]] = []
        for row in target_stocks:
            ts_code = row["ts_code"]
            try:
                self.bootstrap_stock(
                    ts_code,
                    stock_name=row["stock_name"],
                    listed_date=_format_date_human(row["listed_date"]),
                    as_of_date=as_of_date,
                )
                processed += 1
            except Exception as exc:
                failed.append({"ts_code": ts_code, "error": str(exc)})
        return {"processed": processed, "failed": failed, "failed_count": len(failed)}

    def refresh_all(self, *, as_of_date: str | None = None, limit: int | None = None) -> dict[str, Any]:
        """批量刷新数据库中已维护的股票月度估值点。"""
        tracked_stocks = self._store.fetch_tracked_records()
        if limit is not None and limit > 0:
            tracked_stocks = tracked_stocks[:limit]
        processed = 0
        failed: list[dict[str, str]] = []
        for row in tracked_stocks:
            ts_code = str(row.get("ts_code", "")).strip()
            try:
                self.refresh_stock(
                    ts_code,
                    stock_name=str(row.get("stock_name", "")).strip(),
                    listed_date=_format_date_human(str(row.get("listed_date", "")).strip()),
                    as_of_date=as_of_date,
                )
                processed += 1
            except Exception as exc:
                failed.append({"ts_code": ts_code, "error": str(exc)})
        return {"processed": processed, "failed": failed, "failed_count": len(failed)}

    def query_stock(self, ts_code: str, *, refresh_if_missing: bool = False) -> dict[str, Any] | None:
        """查询单只股票的月度估值记录。"""
        record = self._store.fetch_record(ts_code)
        if record is None and refresh_if_missing:
            self.refresh_stock(ts_code)
            record = self._store.fetch_record(ts_code)
        if record is None:
            return None
        points = [
            {
                "month": month,
                "trade_date": "",
                "pe_ttm": pe,
                "pb": pb,
            }
            for month, pe, pb in zip(record.get("months", []), record.get("pe_values", []), record.get("pb_values", []))
        ]
        payload = build_monthly_valuation_payload(
            ts_code=record["ts_code"],
            stock_name=record.get("stock_name", ""),
            listed_date=record.get("listed_date", ""),
            points=points,
        )
        payload["source_meta"] = record.get("source_meta", {})
        payload["updated_at"] = record.get("updated_at", "")
        payload["latest_trade_date"] = record.get("latest_trade_date", "")
        payload["latest_pe_ttm"] = record.get("latest_pe_ttm")
        payload["latest_pb"] = record.get("latest_pb")
        payload["pe_percentile"] = record.get("pe_percentile")
        payload["pb_percentile"] = record.get("pb_percentile")
        payload["series_count"] = record.get("series_count")
        return payload

    def render_launchd_plist(self) -> str:
        """生成 data 月更任务的 launchd 配置。"""
        project_root = Path(__file__).resolve().parents[3]
        script_path = project_root / "product" / "data" / "scripts" / "refresh.sh"
        log_path = project_root / "product" / "data" / "scripts" / "monthly_refresh.log"
        config = self._config.monthly_refresh
        python_path = _runtime_python_path()
        xml_items = "\n".join(
            [
                "    <key>ProgramArguments</key>",
                "    <array>",
                f"        <string>{escape(python_path)}</string>",
                f"        <string>{escape(str(script_path))}</string>",
                "        <string>--refresh-all</string>",
                "    </array>",
                "    <key>WorkingDirectory</key>",
                f"    <string>{escape(str(project_root))}</string>",
                "    <key>StartCalendarInterval</key>",
                "    <dict>",
                f"        <key>Day</key><integer>{config.day}</integer>",
                f"        <key>Hour</key><integer>{config.hour}</integer>",
                f"        <key>Minute</key><integer>{config.minute}</integer>",
                "    </dict>",
                "    <key>StandardOutPath</key>",
                f"    <string>{escape(str(log_path))}</string>",
                "    <key>StandardErrorPath</key>",
                f"    <string>{escape(str(log_path))}</string>",
                "    <key>RunAtLoad</key>",
                "    <false/>",
            ]
        )
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{escape(config.label)}</string>
{xml_items}
</dict>
</plist>
"""

    def install_launch_agent(self) -> Path:
        """安装 data 月更 launchd 配置。"""
        launch_agents = Path.home() / "Library" / "LaunchAgents"
        launch_agents.mkdir(parents=True, exist_ok=True)
        plist_path = launch_agents / f"{self._config.monthly_refresh.label}.plist"
        plist_path.write_text(self.render_launchd_plist(), encoding="utf-8")
        return plist_path


def build_service(
    config: DataConfig | None = None,
    private_config: DataPrivateConfig | None = None,
) -> StockValuationMonthlyService:
    """构造月度估值服务。"""
    service = StockValuationMonthlyService(config=config, private_config=private_config)
    service.ensure_schema()
    return service


def main(argv: Sequence[str] | None = None) -> int:
    """命令行入口，支持初始化和刷新任务。"""
    import argparse

    parser = argparse.ArgumentParser(description="Stock valuation monthly service helper")
    parser.add_argument("command", choices=["bootstrap", "bootstrap-all", "refresh", "refresh-all", "query", "install-launchd"])
    parser.add_argument("--stocks-json", dest="stocks_json", default="")
    parser.add_argument("--ts-code", dest="ts_code", default="")
    parser.add_argument("--stock-name", dest="stock_name", default="")
    parser.add_argument("--listed-date", dest="listed_date", default="")
    parser.add_argument("--as-of-date", dest="as_of_date", default="")
    parser.add_argument("--limit", dest="limit", type=int, default=0)
    parser.add_argument("--refresh-if-missing", dest="refresh_if_missing", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    service = build_service()
    if args.command == "bootstrap":
        if not args.ts_code:
            raise SystemExit("--ts-code is required")
        result = service.bootstrap_stock(
            args.ts_code,
            stock_name=args.stock_name,
            listed_date=args.listed_date or None,
            as_of_date=args.as_of_date or None,
        )
    elif args.command == "bootstrap-all":
        stocks_payload = args.stocks_json.strip()
        if not stocks_payload:
            raise SystemExit("--stocks-json is required for bootstrap-all")
        try:
            stocks = json.loads(stocks_payload)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--stocks-json 不是合法 JSON: {exc}") from exc
        if not isinstance(stocks, list):
            raise SystemExit("--stocks-json 必须是股票数组")
        result = service.bootstrap_all(stocks, as_of_date=args.as_of_date or None)
    elif args.command == "refresh":
        if not args.ts_code:
            raise SystemExit("--ts-code is required")
        result = service.refresh_stock(
            args.ts_code,
            stock_name=args.stock_name,
            listed_date=args.listed_date or None,
            as_of_date=args.as_of_date or None,
        )
    elif args.command == "refresh-all":
        result = service.refresh_all(as_of_date=args.as_of_date or None, limit=args.limit or None)
    elif args.command == "install-launchd":
        result = {"plist_path": str(service.install_launch_agent())}
    else:
        if not args.ts_code:
            raise SystemExit("--ts-code is required")
        result = service.query_stock(args.ts_code, refresh_if_missing=args.refresh_if_missing)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
