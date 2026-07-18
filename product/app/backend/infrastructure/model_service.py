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
import tempfile
import re
from datetime import datetime
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from .config.private_config import require_deepseek_api_key
from .config.project_config import ModelRuntimeConfig, ProjectConfig, load_project_config


ROOT = Path(__file__).resolve().parents[4]


def _model_audit_dir() -> Path:
    """解析模型审计日志目录。"""
    configured = os.getenv("ASTOCK_MODEL_AUDIT_DIR")
    return Path(configured) if configured else ROOT / "product" / "reports" / "daily" / "_model_audit"


@dataclass(frozen=True)
class ModelServiceConfig:
    """模型服务实例化配置。"""

    runtime: ModelRuntimeConfig
    codex_cli_path: str


def _codex_cli_path() -> str:
    """解析 Codex CLI 可执行文件路径。"""
    bundled = Path("/Applications/Codex.app/Contents/Resources/codex")
    if bundled.exists():
        return str(bundled)
    return "codex"


def _extract_first_json_object(raw_text: str) -> str | None:
    """从文本中提取第一个完整 JSON 对象。"""
    start = raw_text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(raw_text)):
        char = raw_text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return raw_text[start : index + 1]
    return None


def _repair_json_prompt(raw_text: str) -> str:
    """构造 JSON 修复提示词。"""
    return (
        "你是JSON修复器。请把下面文本修复成严格合法的JSON对象，只输出JSON，不要解释，不要代码块。\n"
        f"原始文本：\n{raw_text}"
    )


def _safe_audit_snippet(text: str, limit: int = 2000) -> str:
    """截断并清洗审计文本。"""
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _write_model_audit(kind: str, prompt: str, raw_text: str, repaired_text: str | None = None) -> Path:
    """把模型原始输出和修复过程写入审计日志。"""
    audit_dir = _model_audit_dir()
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / f"model-audit-{datetime.now().strftime('%Y%m%d')}.jsonl"
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "kind": kind,
        "prompt": _safe_audit_snippet(prompt),
        "raw_text": _safe_audit_snippet(raw_text),
        "repaired_text": _safe_audit_snippet(repaired_text) if repaired_text is not None else "",
    }
    audit_file.write_text(
        (audit_file.read_text(encoding="utf-8") if audit_file.exists() else "") + json.dumps(payload, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return audit_file


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
    output_file = output_file or (Path(tempfile.gettempdir()) / f"codex-report-{uuid.uuid4().hex}.json")
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
        raw = self._parse_json_or_repair(prompt, raw_text)
        if not isinstance(raw, dict):
            raise RuntimeError("Model output JSON must be an object.")
        return raw

    def _parse_json_or_repair(self, prompt: str, raw_text: str) -> dict[str, Any]:
        """先直接解析，再尝试修复不合法 JSON。"""
        candidate_text = _extract_first_json_object(raw_text) or raw_text
        try:
            return json.loads(candidate_text)
        except json.JSONDecodeError:
            audit_file = _write_model_audit("json-parse-failed", prompt, raw_text)
            repaired_text = self._repair_json_text(prompt, raw_text)
            _write_model_audit("json-repaired", prompt, raw_text, repaired_text)
            try:
                return json.loads(_extract_first_json_object(repaired_text) or repaired_text)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Model output is not valid JSON after repair. Audit log: {audit_file}"
                ) from exc

    def _repair_json_text(self, prompt: str, raw_text: str) -> str:
        """调用模型修复不合法 JSON。"""
        repair_prompt = _repair_json_prompt(raw_text)
        repaired = self._run(repair_prompt)
        return repaired.strip()

    def _run(self, prompt: str) -> str:
        """根据运行配置选择底层模型调用路径。"""
        # 当前约定：生产运行默认走外部模型；需要使用当前 Codex 能力时切换 profile/provider。
        if self.runtime.profile == "external" and self.runtime.provider == "deepseek":
            return self._run_deepseek(prompt)
        return self._run_codex(prompt)

    def _run_deepseek(self, prompt: str) -> str:
        """调用 DeepSeek Chat Completions API 并返回模型文本内容。"""
        # 外部模型密钥从仓库内私密配置读取，避免依赖 shell 环境变量。
        api_key = require_deepseek_api_key()

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
            with urllib_request.urlopen(request, timeout=300) as response:
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
        output_file = Path(tempfile.gettempdir()) / f"codex-report-{uuid.uuid4().hex}.json"
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
