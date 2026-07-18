"""项目全局配置读取模块。

职责：
- 从 `product/app/config/app.toml` 读取运行配置。
- 将 TOML 配置转换为类型化 dataclass，供后端、任务、前端构建脚本等统一使用。
- 为缺失配置提供确定性默认值，避免业务代码散落硬编码。

边界：
- 本文件只负责配置读取、类型转换和默认值兜底。
- 不负责投资分析、数据获取或模型调用。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
import ast

# Python 3.11 内置 tomllib；为了让项目在 3.9/3.10 也能独立运行，
# 这里保留一个极简 TOML 解析兜底，仅覆盖本项目配置文件使用到的语法。
try:  # Python 3.11+
    import tomllib  # type: ignore
except ModuleNotFoundError:  # Python 3.9/3.10 fallback
    tomllib = None  # type: ignore


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_CONFIG_PATH = ROOT / "product" / "app" / "config" / "app.toml"


# 以下 dataclass 是全局配置文件的“类型化视图”。
# 上游业务只读取这些对象，不直接散落读取环境变量或硬编码默认值。
@dataclass(frozen=True)
class ModelRuntimeConfig:
    """模型运行时配置，描述模型路由和外部模型调用参数。"""

    provider: str
    profile: str
    name: str | None = None
    api_key_env: str = "DEEPSEEK_API_KEY"
    base_url: str = "https://api.deepseek.com"
    thinking: bool = True
    reasoning_effort: str = "high"
    use_oss: bool = False
    local_provider: str | None = None


@dataclass(frozen=True)
class SmtpConfig:
    """SMTP 公开配置。"""

    host: str
    port: int
    user: str
    from_addr: str


@dataclass(frozen=True)
class EmailConfig:
    """邮件发送配置。"""

    recipient: str


@dataclass(frozen=True)
class LaunchdConfig:
    """每日定时任务配置。

    该配置保留历史字段名，实际语义已经扩展为“后端常驻调度使用的每日执行时间”。
    """

    label: str
    hour: int
    minute: int


@dataclass(frozen=True)
class BackendConfig:
    """后端服务配置。"""

    title: str
    description: str
    version: str
    cors_origins: list[str]
    public_base_url: str


@dataclass(frozen=True)
class RuntimeConfig:
    """脚本运行时配置。"""

    python_path: str
    reexec_flag: str


@dataclass(frozen=True)
class TushareConfig:
    """Tushare 数据源配置。"""

    token_env: str
    ts_code: str


@dataclass(frozen=True)
class ReportConfig:
    """报告产物输出配置。"""

    output_dir: str


@dataclass(frozen=True)
class FrontendConfig:
    """前端开发和 API 访问配置。"""

    dev_host: str
    dev_port: int
    api_base_path: str
    docs_url: str


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
class MysqlConfig:
    """MySQL 公开连接配置。"""

    host: str
    port: int
    database: str
    connect_timeout_seconds: float


@dataclass(frozen=True)
class ProjectConfig:
    """项目全局配置聚合对象。"""

    smtp: SmtpConfig
    runtime: RuntimeConfig
    backend: BackendConfig
    model: ModelRuntimeConfig
    email: EmailConfig
    launchd: LaunchdConfig
    tushare: TushareConfig
    report: ReportConfig
    frontend: FrontendConfig
    market_data: MarketDataConfig
    mysql: MysqlConfig
    raw: dict[str, Any]


def _as_bool(value: Any, default: bool = False) -> bool:
    """把配置值转换为布尔值。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _clean_optional_text(value: Any) -> str | None:
    """清理可选文本配置，空字符串统一视为未配置。"""
    text = str(value).strip() if value is not None else ""
    return text or None


def _required_text(value: Any, field_name: str, problems: list[str]) -> str:
    """读取必填配置文本，缺失时记录问题并返回空字符串。"""
    text = _clean_optional_text(value) or ""
    if not text:
        problems.append(f"Public config missing {field_name}")
    return text


def _parse_toml_fallback(raw_text: str) -> dict[str, Any]:
    """在没有 tomllib 的运行环境中解析项目配置。

    注意：这不是通用 TOML 解析器，只服务于 product/app/config/app.toml
    当前使用的 section、字符串、数字、布尔值和简单数组语法。
    """
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


def _load_project_config_uncached(config_path: Path) -> ProjectConfig:
    """不带缓存地读取配置文件并转换为 ProjectConfig。"""
    # 所有默认值集中在这里兜底，保证配置文件缺字段时系统仍能以可预期方式启动。
    if not config_path.exists():
        raise FileNotFoundError(f"Project config not found: {config_path}")
    data = _load_toml_text(config_path.read_text(encoding="utf-8"))
    backend_data = dict(data.get("backend", {}))
    runtime_data = dict(data.get("runtime", {}))
    model_data = dict(data.get("model", {}))
    smtp_data = dict(data.get("smtp", {}))
    email_data = dict(data.get("email", {}))
    launchd_data = dict(data.get("launchd", {}))
    tushare_data = dict(data.get("tushare", {}))
    report_data = dict(data.get("report", {}))
    market_data_data = dict(data.get("market_data", {}))
    mysql_data = dict(data.get("mysql", {}))

    backend = BackendConfig(
        title=_clean_optional_text(backend_data.get("title")) or "A Stock API",
        description=_clean_optional_text(backend_data.get("description")) or "Python + Vue starter API",
        version=_clean_optional_text(backend_data.get("version")) or "0.1.0",
        cors_origins=[
            str(origin).strip()
            for origin in (backend_data.get("cors_origins") or ["http://localhost:5173", "http://127.0.0.1:5173"])
            if str(origin).strip()
        ],
        public_base_url=_clean_optional_text(backend_data.get("public_base_url")) or "http://127.0.0.1:8000",
    )

    smtp_problems: list[str] = []
    smtp_host = _required_text(smtp_data.get("host"), "smtp.host", smtp_problems)
    smtp_port_raw = _required_text(smtp_data.get("port"), "smtp.port", smtp_problems) or "0"
    smtp_user = _required_text(smtp_data.get("user"), "smtp.user", smtp_problems)
    smtp_from_addr = _required_text(smtp_data.get("from_addr"), "smtp.from_addr", smtp_problems)
    try:
        smtp_port = int(smtp_port_raw)
    except ValueError as exc:
        smtp_problems.append("Public config smtp.port must be an integer")
        smtp_port = 0
        smtp_port_error = exc
    else:
        smtp_port_error = None
    if smtp_problems:
        raise ValueError("; ".join(smtp_problems)) from smtp_port_error
    smtp = SmtpConfig(
        host=smtp_host,
        port=smtp_port,
        user=smtp_user,
        from_addr=smtp_from_addr,
    )

    runtime = RuntimeConfig(
        python_path=_clean_optional_text(runtime_data.get("python_path")) or "",
        reexec_flag=_clean_optional_text(runtime_data.get("reexec_flag")) or "MUYUAN_NIGHTLY_REEXEC",
    )

    model = ModelRuntimeConfig(
        provider=_clean_optional_text(model_data.get("provider")) or "deepseek",
        profile=_clean_optional_text(model_data.get("profile")) or "external",
        name=_clean_optional_text(model_data.get("name")) or "deepseek-v4-pro",
        api_key_env=_clean_optional_text(model_data.get("api_key_env")) or "DEEPSEEK_API_KEY",
        base_url=_clean_optional_text(model_data.get("base_url")) or "https://api.deepseek.com",
        thinking=_as_bool(model_data.get("thinking"), default=True),
        reasoning_effort=_clean_optional_text(model_data.get("reasoning_effort")) or "high",
        use_oss=_as_bool(model_data.get("use_oss"), default=False),
        local_provider=_clean_optional_text(model_data.get("local_provider")),
    )
    email = EmailConfig(
        recipient=_clean_optional_text(email_data.get("recipient")) or "376597874@qq.com",
    )
    launchd = LaunchdConfig(
        label=_clean_optional_text(launchd_data.get("label")) or "com.astock.muyuan-nightly",
        hour=int(launchd_data.get("hour", 1)),
        minute=int(launchd_data.get("minute", 12)),
    )
    tushare = TushareConfig(
        token_env=_clean_optional_text(tushare_data.get("token_env")) or "TUSHARE_TOKEN",
        ts_code=_clean_optional_text(tushare_data.get("ts_code")) or "002714.SZ",
    )
    report = ReportConfig(
        output_dir=_clean_optional_text(report_data.get("output_dir")) or "product/reports/daily",
    )
    frontend_data = dict(data.get("frontend", {}))
    frontend = FrontendConfig(
        dev_host=_clean_optional_text(frontend_data.get("dev_host")) or "0.0.0.0",
        dev_port=int(frontend_data.get("dev_port", 5173)),
        api_base_path=_clean_optional_text(frontend_data.get("api_base_path")) or "/api",
        docs_url=_clean_optional_text(frontend_data.get("docs_url")) or "http://127.0.0.1:8000/docs",
    )
    market_data = MarketDataConfig(
        vix_data_url=_clean_optional_text(market_data_data.get("vix_data_url")) or "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
        vix_source_url=_clean_optional_text(market_data_data.get("vix_source_url")) or "https://www.cboe.com/tradable_products/vix/vix_historical_data/",
        cnn_data_url=_clean_optional_text(market_data_data.get("cnn_data_url")) or "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        cnn_source_url=_clean_optional_text(market_data_data.get("cnn_source_url")) or "https://www.cnn.com/markets/fear-and-greed",
        nasdaq_data_url=_clean_optional_text(market_data_data.get("nasdaq_data_url")) or "https://api.nasdaq.com/api/quote/QQQ/historical",
        nasdaq_source_url=_clean_optional_text(market_data_data.get("nasdaq_source_url")) or "https://www.nasdaq.com/market-activity/etf/qqq/historical",
        request_user_agent=_clean_optional_text(market_data_data.get("request_user_agent")) or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        ),
        request_accept=_clean_optional_text(market_data_data.get("request_accept")) or "application/json, text/plain, */*",
        request_accept_language=_clean_optional_text(market_data_data.get("request_accept_language")) or "en-US,en;q=0.9",
        cache_ttl_seconds=int(market_data_data.get("cache_ttl_seconds", 300)),
        request_timeout_seconds=float(market_data_data.get("request_timeout_seconds", 20.0)),
        connect_timeout_seconds=float(market_data_data.get("connect_timeout_seconds", 10.0)),
    )
    mysql = MysqlConfig(
        host=_clean_optional_text(mysql_data.get("host")) or "127.0.0.1",
        port=int(mysql_data.get("port", 3306)),
        database=_clean_optional_text(mysql_data.get("database")) or "astock",
        connect_timeout_seconds=float(mysql_data.get("connect_timeout_seconds", 5.0)),
    )
    return ProjectConfig(
        smtp=smtp,
        runtime=runtime,
        backend=backend,
        model=model,
        email=email,
        launchd=launchd,
        tushare=tushare,
        report=report,
        frontend=frontend,
        market_data=market_data,
        mysql=mysql,
        raw=data,
    )


@lru_cache(maxsize=8)
def load_project_config(config_path: str | Path | None = None) -> ProjectConfig:
    """加载项目全局配置。

    配置结果做缓存，避免前后端接口和定时任务反复读取 TOML；
    测试如需切换配置路径，可传入不同 config_path。
    """
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    return _load_project_config_uncached(path.resolve())
