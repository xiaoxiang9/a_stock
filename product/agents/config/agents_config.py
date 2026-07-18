"""agents 子系统公开配置读取模块。

职责：
- 从 `product/agents/config/agents.toml` 读取多 Agent 研究体系的运行配置。
- 将 TOML 配置转换为类型化对象，供后续 LangGraph 工作流和 agent 编排使用。
- 不依赖 app 或 data 子系统的配置加载器。
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
DEFAULT_CONFIG_PATH = ROOT / "product" / "agents" / "config" / "agents.toml"


@dataclass(frozen=True)
class ModelConfig:
    """agents 子系统模型路由配置。"""

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
class WorkflowConfig:
    """agents 子系统工作流配置。"""

    default_graph: str
    max_reflection_rounds: int
    enable_evidence_collection: bool


@dataclass(frozen=True)
class SearchConfig:
    """agents 子系统联网搜索配置。"""

    websearch_enabled: bool
    websearch_command: str
    websearch_api_key_env: str
    websearch_model: str
    websearch_thinking: str
    websearch_max_tokens: int
    websearch_timeout_seconds: int


@dataclass(frozen=True)
class AgentsConfig:
    """agents 子系统公开配置聚合对象。"""

    model: ModelConfig
    workflow: WorkflowConfig
    search: SearchConfig
    raw: dict[str, Any]


def _clean_text(value: Any) -> str | None:
    """清理可选文本配置，空字符串统一视为未配置。"""
    text = str(value).strip() if value is not None else ""
    return text or None


def _required_text(value: Any, field_name: str, problems: list[str]) -> str:
    """读取必填配置文本，缺失时记录问题并返回空字符串。"""
    text = _clean_text(value) or ""
    if not text:
        problems.append(f"Agents config missing {field_name}")
    return text


def _as_bool(value: Any, default: bool = False) -> bool:
    """把配置值转换为布尔值。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _required_int(value: Any, field_name: str, problems: list[str]) -> int:
    """读取必填整数字段，缺失或非法时记录问题并返回 0。"""
    text = _clean_text(value)
    if not text:
        problems.append(f"Agents config missing {field_name}")
        return 0
    try:
        return int(text)
    except ValueError:
        problems.append(f"Agents config {field_name} must be an integer")
        return 0


def _optional_int(value: Any, default: int) -> int:
    """读取可选整数字段，非法时回落到默认值。"""
    text = _clean_text(value)
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def _parse_toml_fallback(raw_text: str) -> dict[str, Any]:
    """在没有 tomllib 的运行环境中解析 agents 配置。"""
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


def _load_agents_config_uncached(config_path: Path) -> AgentsConfig:
    """不带缓存地读取 agents 配置文件。"""
    if not config_path.exists():
        raise FileNotFoundError(f"Agents config not found: {config_path}")

    data = _load_toml_text(config_path.read_text(encoding="utf-8"))
    model_data = dict(data.get("model", {}))
    workflow_data = dict(data.get("workflow", {}))
    search_data = dict(data.get("search", {}))

    problems: list[str] = []
    model_config = ModelConfig(
        provider=_required_text(model_data.get("provider"), "model.provider", problems),
        profile=_required_text(model_data.get("profile"), "model.profile", problems),
        name=_clean_text(model_data.get("name")),
        api_key_env=_clean_text(model_data.get("api_key_env")) or "DEEPSEEK_API_KEY",
        base_url=_clean_text(model_data.get("base_url")) or "https://api.deepseek.com",
        thinking=_as_bool(model_data.get("thinking"), default=True),
        reasoning_effort=_clean_text(model_data.get("reasoning_effort")) or "high",
        use_oss=_as_bool(model_data.get("use_oss"), default=False),
        local_provider=_clean_text(model_data.get("local_provider")),
    )
    workflow_config = WorkflowConfig(
        default_graph=_clean_text(workflow_data.get("default_graph")) or "research",
        max_reflection_rounds=_required_int(
            workflow_data.get("max_reflection_rounds"), "workflow.max_reflection_rounds", problems
        ),
        enable_evidence_collection=_as_bool(workflow_data.get("enable_evidence_collection"), default=True),
    )
    search_config = SearchConfig(
        websearch_enabled=_as_bool(search_data.get("websearch_enabled"), default=True),
        websearch_command=_clean_text(search_data.get("websearch_command")) or "websearch-deepseek",
        websearch_api_key_env=_clean_text(search_data.get("websearch_api_key_env")) or "DEEPSEEK_API_KEY",
        websearch_model=_clean_text(search_data.get("websearch_model")) or "deepseek-v4-flash",
        websearch_thinking=_clean_text(search_data.get("websearch_thinking")) or "enabled",
        websearch_max_tokens=_optional_int(search_data.get("websearch_max_tokens"), default=32768),
        websearch_timeout_seconds=_optional_int(search_data.get("websearch_timeout_seconds"), default=90),
    )
    if problems:
        raise ValueError("; ".join(problems))
    return AgentsConfig(model=model_config, workflow=workflow_config, search=search_config, raw=data)


@lru_cache(maxsize=8)
def load_agents_config(config_path: str | Path | None = None) -> AgentsConfig:
    """加载 agents 子系统公开配置。"""
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    return _load_agents_config_uncached(path.resolve())
