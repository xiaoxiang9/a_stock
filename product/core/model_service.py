"""模型调用公共层。

职责：
- 对业务层屏蔽模型供应商和调用方式差异。
- 支持外部 DeepSeek API 和本地 Codex CLI 两类运行路径。
- 统一要求模型返回 JSON，并在公共层完成结构校验。

边界：
- 本文件只负责模型路由、请求发送和输出结构校验。
- 不负责具体投研分析逻辑，也不在代码中硬编码投资判断。
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from .project_config import ModelRuntimeConfig, ProjectConfig, load_project_config


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ModelServiceConfig:
    """模型服务实例化配置。"""

    runtime: ModelRuntimeConfig
    codex_cli_path: str


def _codex_cli_path() -> str:
    """解析 Codex CLI 可执行文件路径。"""
    # 优先允许外部显式指定 Codex CLI，便于本地开发、CI 或生产环境切换。
    explicit = os.getenv("CODEX_CLI_PATH")
    if explicit:
        return explicit
    bundled = Path("/Applications/Codex.app/Contents/Resources/codex")
    if bundled.exists():
        return str(bundled)
    return "codex"


def build_codex_exec_command(
    prompt: str,
    runtime: ModelRuntimeConfig,
    output_file: Path | None = None,
    codex_cli_path: str | None = None,
) -> list[str]:
    """构造 Codex CLI 调用命令。

    这里仅做确定性的命令拼装，不承担任何分析判断；
    具体分析能力由 Codex 当前模型或外部模型完成。
    """
    output_file = output_file or (Path(os.getenv("TMPDIR", "/tmp")) / f"codex-report-{uuid.uuid4().hex}.json")
    command = [
        codex_cli_path or _codex_cli_path(),
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--output-last-message",
        str(output_file),
    ]
    if runtime.profile:
        command.extend(["--profile", runtime.profile])
    model_name = runtime.name
    if runtime.profile == "external" and not model_name:
        model_name = "deepseek-v4-pro"
    if model_name:
        command.extend(["--model", model_name])
    if runtime.use_oss:
        command.append("--oss")
    if runtime.local_provider:
        command.extend(["--local-provider", runtime.local_provider])
    command.append(prompt)
    return command


class ModelService:
    """统一的模型调用门面。

    业务层只调用 complete_json，不关心底层是 DeepSeek、Codex CLI，
    还是后续替换成其他外部模型，从而把模型切换逻辑收敛到公共层。
    """

    def __init__(
        self,
        runtime: ModelRuntimeConfig | None = None,
        *,
        codex_cli_path: str | None = None,
    ) -> None:
        """初始化模型服务。

        如果调用方未显式传入 runtime，则读取项目全局配置；
        codex_cli_path 允许测试或特殊运行环境覆盖 Codex CLI 路径。
        """
        project_config = load_project_config()
        self.runtime = runtime or project_config.model
        self.codex_cli_path = codex_cli_path or _codex_cli_path()

    @classmethod
    def from_project_config(
        cls,
        project_config: ProjectConfig | None = None,
    ) -> "ModelService":
        """根据项目配置构建模型服务实例。"""
        config = project_config or load_project_config()
        return cls(runtime=config.model)

    def complete_json(self, prompt: str) -> dict[str, Any]:
        """调用模型并要求返回 JSON 对象。"""
        # 投研分析结果要求结构化输出；这里负责校验 JSON 形态，
        # 不对内容做业务含义上的二次加工。
        raw_text = self._run(prompt)
        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Model output is not valid JSON: {raw_text[:500]}") from exc
        if not isinstance(raw, dict):
            raise RuntimeError("Model output JSON must be an object.")
        return raw

    def _run(self, prompt: str) -> str:
        """根据运行配置选择底层模型调用路径。"""
        # 当前约定：生产运行默认走外部模型；需要使用当前 Codex 能力时切换 profile/provider。
        if self.runtime.profile == "external" and self.runtime.provider == "deepseek":
            return self._run_deepseek(prompt)
        return self._run_codex(prompt)

    def _run_deepseek(self, prompt: str) -> str:
        """调用 DeepSeek Chat Completions API 并返回模型文本内容。"""
        # 外部模型密钥只从环境变量读取，不写入代码，便于部署和密钥轮换。
        api_key = os.getenv(self.runtime.api_key_env)
        if not api_key:
            raise RuntimeError(f"{self.runtime.api_key_env} is not configured.")

        url = f"{self.runtime.base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.runtime.name or "deepseek-v4-pro",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        if self.runtime.thinking:
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = self.runtime.reasoning_effort

        request = urllib_request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(request, timeout=30) as response:
                response_text = response.read().decode("utf-8").strip()
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise RuntimeError(detail or str(exc)) from exc
        except urllib_error.URLError as exc:
            raise RuntimeError(str(exc)) from exc

        if not response_text:
            raise RuntimeError("DeepSeek API returned empty content.")
        try:
            response_payload = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"DeepSeek response is not valid JSON: {response_text[:500]}") from exc
        try:
            content = response_payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("DeepSeek response missing assistant content.") from exc
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("DeepSeek response content is empty.")
        return content.strip()

    def _run_codex(self, prompt: str) -> str:
        """通过 Codex CLI 调用当前模型并读取输出文件。"""
        # Codex CLI 路径主要用于本地/Agent 场景，输出通过临时文件回收。
        output_file = Path(os.getenv("TMPDIR", "/tmp")) / f"codex-report-{uuid.uuid4().hex}.json"
        runtime = replace(self.runtime, name=None)
        command = build_codex_exec_command(
            prompt,
            runtime=runtime,
            output_file=output_file,
            codex_cli_path=self.codex_cli_path,
        )
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env=os.environ.copy(),
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "codex exec failed"
            raise RuntimeError(stderr)
        if not output_file.exists():
            raise RuntimeError("Codex exec did not produce an output file.")
        content = output_file.read_text(encoding="utf-8").strip()
        try:
            output_file.unlink(missing_ok=True)
        except Exception:
            pass
        if not content:
            raise RuntimeError("Codex exec returned empty content.")
        return content
