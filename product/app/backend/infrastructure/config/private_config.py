"""私密配置读取模块。

职责：
- 从 `product/app/config/private.local.toml` 读取仓库内忽略的私密配置。
- 将 SMTP 密码和其他敏感配置转换为类型化对象，供任务层和后端调度复用。
- 为后续新增的私密配置项预留统一入口，但不把密钥散落到环境变量里。

边界：
- 本文件只负责读取和校验私密配置，不负责发送邮件或其他业务处理。
- 文件缺失或必填字段不完整时，直接抛出明确异常，避免静默降级。
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


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_PRIVATE_CONFIG_PATH = ROOT / "product" / "app" / "config" / "private.local.toml"


@dataclass(frozen=True)
class SecretsConfig:
    """通用私密凭据配置。"""

    deepseek_api_key: str = ""
    tushare_token: str = ""


@dataclass(frozen=True)
class MysqlSecretsConfig:
    """MySQL 私密连接配置。"""

    user: str
    password: str


@dataclass(frozen=True)
class PrivateConfig:
    """私密配置聚合对象。"""

    smtp_password: str
    secrets: SecretsConfig
    mysql: MysqlSecretsConfig
    raw: dict[str, Any]


def _clean_text(value: Any) -> str:
    """把配置值清洗为非空字符串。"""
    text = str(value).strip() if value is not None else ""
    return text


def _collect_required_text(value: Any, field_name: str, problems: list[str]) -> str:
    """读取必填文本字段，缺失时记录问题并返回空字符串。"""
    text = _clean_text(value)
    if not text:
        problems.append(f"Private config missing {field_name}")
    return text


def _parse_toml_fallback(raw_text: str) -> dict[str, Any]:
    """在没有 tomllib 的运行环境中解析私密配置。

    这里沿用项目内最小化 TOML 解析策略，只覆盖本仓库当前使用到的语法。
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


def _build_smtp_password(private_data: dict[str, Any]) -> str:
    """从私密配置中提取 SMTP 密码。"""
    smtp_data = dict(private_data.get("smtp", {}))
    problems: list[str] = []
    password = _collect_required_text(smtp_data.get("password"), "smtp.password", problems)
    if problems:
        raise ValueError("; ".join(problems))
    return password


def _build_secrets_config(private_data: dict[str, Any]) -> SecretsConfig:
    """从私密配置中提取通用密钥。"""
    secrets_data = dict(private_data.get("secrets", {}))
    problems: list[str] = []
    deepseek_api_key = _collect_required_text(secrets_data.get("deepseek_api_key"), "secrets.deepseek_api_key", problems)
    tushare_token = _collect_required_text(secrets_data.get("tushare_token"), "secrets.tushare_token", problems)
    if problems:
        raise ValueError("; ".join(problems))
    return SecretsConfig(
        deepseek_api_key=deepseek_api_key,
        tushare_token=tushare_token,
    )


def _build_mysql_config(private_data: dict[str, Any]) -> MysqlSecretsConfig:
    """从私密配置中提取 MySQL 账号信息。"""
    mysql_data = dict(private_data.get("mysql", {}))
    problems: list[str] = []
    user = _collect_required_text(mysql_data.get("user"), "mysql.user", problems)
    password = _collect_required_text(mysql_data.get("password"), "mysql.password", problems)
    if problems:
        raise ValueError("; ".join(problems))
    return MysqlSecretsConfig(user=user, password=password)


def _load_private_config_uncached(config_path: Path) -> PrivateConfig:
    """不带缓存地读取私密配置文件。"""
    if not config_path.exists():
        raise FileNotFoundError(f"Private config not found: {config_path}")
    data = _load_toml_text(config_path.read_text(encoding="utf-8"))
    smtp_password = _build_smtp_password(data)
    secrets = _build_secrets_config(data)
    mysql = _build_mysql_config(data)
    return PrivateConfig(smtp_password=smtp_password, secrets=secrets, mysql=mysql, raw=data)


@lru_cache(maxsize=8)
def load_private_config(config_path: str | Path | None = None) -> PrivateConfig:
    """加载私密配置。

    配置结果做缓存，避免频繁读取同一份本地密钥文件；
    测试如需切换配置路径，可以传入不同 config_path。
    """
    path = Path(config_path) if config_path is not None else DEFAULT_PRIVATE_CONFIG_PATH
    return _load_private_config_uncached(path.resolve())


def require_deepseek_api_key(private_config: PrivateConfig | None = None) -> str:
    """读取 DeepSeek API key，缺失时抛出明确异常。"""
    config = private_config or load_private_config()
    api_key = config.secrets.deepseek_api_key.strip()
    if not api_key:
        raise RuntimeError("Private config missing secrets.deepseek_api_key")
    return api_key


def require_tushare_token(private_config: PrivateConfig | None = None) -> str:
    """读取 Tushare token，缺失时抛出明确异常。"""
    config = private_config or load_private_config()
    token = config.secrets.tushare_token.strip()
    if not token:
        raise RuntimeError("Private config missing secrets.tushare_token")
    return token
