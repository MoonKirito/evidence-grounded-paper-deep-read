from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


DEFAULT_CONFIG = """# Evidence-Grounded Paper Deep Read CLI config

[llm]
provider = "mimo"
base_url = "https://token-plan-cn.xiaomimimo.com/v1"
model = "mimo-v2.5-pro"
api_key_env = "MIMO_API_KEY"
temperature = 0.2
max_tokens = 24000
timeout_seconds = 900
stream = true

[pipeline]
language = "中文"
generation_mode = "sectioned"
max_input_chars = 120000
validate_report = true
skip_existing = false

[pdffigures2]
jar_path = ""
java_path = "java"
"""


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    base_url: str
    model: str
    api_key_env: str
    temperature: float
    max_tokens: int
    timeout_seconds: int
    stream: bool

    @property
    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")


@dataclass(frozen=True)
class PipelineConfig:
    language: str
    generation_mode: str
    max_input_chars: int
    validate_report: bool
    skip_existing: bool


@dataclass(frozen=True)
class Pdffigures2Config:
    jar_path: str
    java_path: str


@dataclass(frozen=True)
class AppConfig:
    llm: LlmConfig
    pipeline: PipelineConfig
    pdffigures2: Pdffigures2Config


def write_default_config(path: Path, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Config already exists: {path}")
    path.write_text(DEFAULT_CONFIG, encoding="utf-8")


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}. Run: python -m paperdeepread init-config")

    data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    llm = data.get("llm", {})
    pipeline = data.get("pipeline", {})
    pdffigures2 = data.get("pdffigures2", {})

    return AppConfig(
        llm=LlmConfig(
            provider=str(llm.get("provider", "mimo")),
            base_url=str(llm.get("base_url", "https://token-plan-cn.xiaomimimo.com/v1")),
            model=str(llm.get("model", "mimo-v2.5-pro")),
            api_key_env=str(llm.get("api_key_env", "MIMO_API_KEY")),
            temperature=float(llm.get("temperature", 0.2)),
            max_tokens=int(llm.get("max_tokens", 24000)),
            timeout_seconds=int(llm.get("timeout_seconds", 900)),
            stream=bool(llm.get("stream", True)),
        ),
        pipeline=PipelineConfig(
            language=str(pipeline.get("language", "中文")),
            generation_mode=str(pipeline.get("generation_mode", "sectioned")),
            max_input_chars=int(pipeline.get("max_input_chars", 120000)),
            validate_report=bool(pipeline.get("validate_report", True)),
            skip_existing=bool(pipeline.get("skip_existing", False)),
        ),
        pdffigures2=Pdffigures2Config(
            jar_path=str(pdffigures2.get("jar_path", "")),
            java_path=str(pdffigures2.get("java_path", "java")),
        ),
    )
