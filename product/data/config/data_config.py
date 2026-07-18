"""data 子系统公开配置读取模块。

职责：
- 从 `product/data/config/data.toml` 读取数据层自己的公开配置。
- 将 TOML 配置转换为类型化对象，供数据层 fetcher 使用。
- 仅承载 data 子系统的默认路径和配置模型，不依赖 app 子系统。

边界：
- 本文件只负责配置读取、类型转换和默认值兜底。
- 不负责任何投研判断或业务编排。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
import ast

try:  # Python 3.11+
    import tomllib  # type: ignore
except ModuleNotFoundError:  # Python 3.9/3.10 fallback
    tomllib = None  # type: ignore


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = ROOT / "product" / "data" / "config" / "data.toml"


@dataclass(frozen=True)
class MarketDataConfig:
    """市场数据接口配置。"""

    vix_data_url: str
    vix_source_url: str
    cnn_data_url: str
    cnn_source_url: str
    nasdaq_data_url: str
    nasdaq_source_url: str
    request_user_agent: str
    request_accept: str
    request_accept_language: str
    cache_ttl_seconds: int
    request_timeout_seconds: float
    connect_timeout_seconds: float


@dataclass(frozen=True)
class TushareConfig:
    """Tushare 默认查询配置。"""

    token_env: str
    ts_code: str


@dataclass(frozen=True)
class MysqlConfig:
    """data 子系统 MySQL 公开配置。"""

    host: str
    port: int
    database: str
    connect_timeout_seconds: float


@dataclass(frozen=True)
class ApiConfig:
    """data 子系统 HTTP API 运行配置。"""

    host: str
    port: int
    prefix: str


@dataclass(frozen=True)
class MonthlyRefreshConfig:
    """data 子系统月更调度配置。"""

    label: str
    day: int
    hour: int
    minute: int


@dataclass(frozen=True)
class DataConfig:
    """data 子系统公开配置聚合对象。"""

    market_data: MarketDataConfig
    tushare: TushareConfig
    mysql: MysqlConfig
    api: ApiConfig
    monthly_refresh: MonthlyRefreshConfig
    raw: dict[str, Any]


def _clean_text(value: Any) -> str | None:
    """清理可选文本配置，空字符串统一视为未配置。"""
    text = str(value).strip() if value is not None else ""
    return text or None


def _required_text(value: Any, field_name: str, problems: list[str]) -> str:
    """读取必填配置文本，缺失时记录问题并返回空字符串。"""
    text = _clean_text(value) or ""
    if not text:
        problems.append(f"Data config missing {field_name}")
    return text


def _required_int(value: Any, field_name: str, problems: list[str]) -> int:
    """读取必填整数字段，缺失或非法时记录问题并返回 0。"""
    text = _clean_text(value)
    if not text:
        problems.append(f"Data config missing {field_name}")
        return 0
    try:
        return int(text)
    except ValueError:
        problems.append(f"Data config {field_name} must be an integer")
        return 0


def _required_float(value: Any, field_name: str, problems: list[str]) -> float:
    """读取必填浮点字段，缺失或非法时记录问题并返回 0.0。"""
    text = _clean_text(value)
    if not text:
        problems.append(f"Data config missing {field_name}")
        return 0.0
    try:
        return float(text)
    except ValueError:
        problems.append(f"Data config {field_name} must be a number")
        return 0.0


def _clean_optional_int(value: Any, default: int) -> int:
    """把可选整数配置清洗为整数，缺失时使用默认值。"""
    text = _clean_text(value)
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def _clean_optional_float(value: Any, default: float) -> float:
    """把可选浮点配置清洗为浮点数，缺失时使用默认值。"""
    text = _clean_text(value)
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _parse_toml_fallback(raw_text: str) -> dict[str, Any]:
    """在没有 tomllib 的运行环境中解析 data 配置。"""
    data: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            current = data.setdefault(section, {})
            continue
        if current is None or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            current[key] = ""
            continue
        if value in {"true", "false"}:
            current[key] = value == "true"
            continue
        try:
            current[key] = ast.literal_eval(value.replace("true", "True").replace("false", "False"))
        except Exception:
            current[key] = value.strip('"').strip("'")
    return data


def _load_toml_text(text: str) -> dict[str, Any]:
    """优先使用标准 tomllib 解析 TOML，不可用时走项目内兜底解析器。"""
    if tomllib is not None:
        return tomllib.loads(text)
    return _parse_toml_fallback(text)


def _load_data_config_uncached(config_path: Path) -> DataConfig:
    """不带缓存地读取 data 配置文件。"""
    if not config_path.exists():
        raise FileNotFoundError(f"Data config not found: {config_path}")

    data = _load_toml_text(config_path.read_text(encoding="utf-8"))
    market_data = dict(data.get("market_data", {}))
    tushare_data = dict(data.get("tushare", {}))
    mysql_data = dict(data.get("mysql", {}))
    api_data = dict(data.get("api", {}))
    monthly_refresh_data = dict(data.get("monthly_refresh", {}))

    problems: list[str] = []
    try:
        market_config = MarketDataConfig(
            vix_data_url=_required_text(market_data.get("vix_data_url"), "market_data.vix_data_url", problems),
            vix_source_url=_required_text(market_data.get("vix_source_url"), "market_data.vix_source_url", problems),
            cnn_data_url=_required_text(market_data.get("cnn_data_url"), "market_data.cnn_data_url", problems),
            cnn_source_url=_required_text(market_data.get("cnn_source_url"), "market_data.cnn_source_url", problems),
            nasdaq_data_url=_required_text(market_data.get("nasdaq_data_url"), "market_data.nasdaq_data_url", problems),
            nasdaq_source_url=_required_text(market_data.get("nasdaq_source_url"), "market_data.nasdaq_source_url", problems),
            request_user_agent=_required_text(market_data.get("request_user_agent"), "market_data.request_user_agent", problems),
            request_accept=_required_text(market_data.get("request_accept"), "market_data.request_accept", problems),
            request_accept_language=_required_text(
                market_data.get("request_accept_language"), "market_data.request_accept_language", problems
            ),
            cache_ttl_seconds=_required_int(market_data.get("cache_ttl_seconds"), "market_data.cache_ttl_seconds", problems),
            request_timeout_seconds=_required_float(
                market_data.get("request_timeout_seconds"), "market_data.request_timeout_seconds", problems
            ),
            connect_timeout_seconds=_required_float(
                market_data.get("connect_timeout_seconds"), "market_data.connect_timeout_seconds", problems
            ),
        )
        tushare_config = TushareConfig(
            token_env=_required_text(tushare_data.get("token_env"), "tushare.token_env", problems),
            ts_code=_required_text(tushare_data.get("ts_code"), "tushare.ts_code", problems),
        )
        mysql_config = MysqlConfig(
            host=_required_text(mysql_data.get("host"), "mysql.host", problems),
            port=_clean_optional_int(mysql_data.get("port"), 3306),
            database=_required_text(mysql_data.get("database"), "mysql.database", problems),
            connect_timeout_seconds=_clean_optional_float(mysql_data.get("connect_timeout_seconds"), 5.0),
        )
        api_config = ApiConfig(
            host=_clean_text(api_data.get("host")) or "0.0.0.0",
            port=_clean_optional_int(api_data.get("port"), 8010),
            prefix=_clean_text(api_data.get("prefix")) or "/api",
        )
        monthly_refresh_config = MonthlyRefreshConfig(
            label=_clean_text(monthly_refresh_data.get("label")) or "com.astock.data-monthly-refresh",
            day=_clean_optional_int(monthly_refresh_data.get("day"), 3),
            hour=_clean_optional_int(monthly_refresh_data.get("hour"), 1),
            minute=_clean_optional_int(monthly_refresh_data.get("minute"), 12),
        )
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    if problems:
        raise ValueError("; ".join(problems))
    return DataConfig(
        market_data=market_config,
        tushare=tushare_config,
        mysql=mysql_config,
        api=api_config,
        monthly_refresh=monthly_refresh_config,
        raw=data,
    )


@lru_cache(maxsize=8)
def load_data_config(config_path: str | Path | None = None) -> DataConfig:
    """加载 data 子系统公开配置。"""
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    return _load_data_config_uncached(path.resolve())
