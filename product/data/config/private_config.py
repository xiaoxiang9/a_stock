"""data 子系统私密配置读取模块。

职责：
- 从 `product/data/config/private.local.toml` 读取 data 子系统私密配置。
- 保留未来数据源密钥的统一入口，但不依赖 app 子系统的私密配置。

边界：
- 本文件只做读取和保存，不负责业务处理。
- 当前 data 子系统尚未强依赖私密项，因此允许配置项为空。
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
DEFAULT_PRIVATE_CONFIG_PATH = ROOT / "product" / "data" / "config" / "private.local.toml"


@dataclass(frozen=True)
class DataPrivateConfig:
    """data 子系统私密配置聚合对象。"""

    secrets: dict[str, str]
    mysql: dict[str, str]
    raw: dict[str, Any]


def _parse_toml_fallback(raw_text: str) -> dict[str, Any]:
    """在没有 tomllib 的运行环境中解析 data 私密配置。"""
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


def _load_private_config_uncached(config_path: Path) -> DataPrivateConfig:
    """不带缓存地读取 data 私密配置。"""
    if not config_path.exists():
        raise FileNotFoundError(f"Data private config not found: {config_path}")
    data = _load_toml_text(config_path.read_text(encoding="utf-8"))
    secrets = {
        key: str(value).strip()
        for key, value in dict(data.get("secrets", {})).items()
        if str(value).strip()
    }
    mysql = {
        key: str(value).strip()
        for key, value in dict(data.get("mysql", {})).items()
        if str(value).strip()
    }
    return DataPrivateConfig(secrets=secrets, mysql=mysql, raw=data)


@lru_cache(maxsize=8)
def load_private_data_config(config_path: str | Path | None = None) -> DataPrivateConfig:
    """加载 data 子系统私密配置。"""
    path = Path(config_path) if config_path is not None else DEFAULT_PRIVATE_CONFIG_PATH
    return _load_private_config_uncached(path.resolve())
