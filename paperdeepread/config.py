from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from pathlib import Path

from paperdeepread.providers.presets import PROVIDERS, canonical_provider

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


DEFAULT_CONFIG = """# Evidence-Grounded Paper Deep Read CLI config

[llm]
provider = "mimo"
base_url = "https://token-plan-cn.xiaomimimo.com/v1"
# Select a vision-capable model here or configure an independent [vision] section
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
# Required: extraction never falls back to manual crops
jar_path = ""
java_path = "java"
"""


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    base_url: str
    model: str
    api_key_env: str
    temperature: float | None
    max_tokens: int
    timeout_seconds: int
    stream: bool
    max_tokens_parameter: str = "auto"
    extra_body: dict = field(default_factory=dict)
    api_key_value: str = field(default="", repr=False)
    require_api_key: bool = True

    @property
    def token_parameter(self) -> str:
        if self.max_tokens_parameter != "auto":
            return self.max_tokens_parameter
        return "max_completion_tokens" if canonical_provider(self.provider) in {"openai", "minimax"} else "max_tokens"

    @property
    def api_key(self) -> str:
        return self.api_key_value or os.environ.get(self.api_key_env, "")


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
    vision: LlmConfig | None = None


def write_default_config(path: Path, force: bool = False, *, provider: str = "mimo",
                         model: str | None = None, base_url: str | None = None) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Config already exists: {path}")
    provider = canonical_provider(provider)
    preset = PROVIDERS[provider]
    model = model or ("mimo-v2.5-pro" if provider == "mimo" else None)
    if not model:
        raise ValueError("Pass --model with your provider's model ID (or deployment ID).")
    url = base_url or preset.base_url
    if not url:
        raise ValueError("Custom OpenAI-compatible providers require --base-url.")
    text = DEFAULT_CONFIG
    for old, new in [('provider = "mimo"', f'provider = {json.dumps(provider)}'),
                     ('base_url = "https://token-plan-cn.xiaomimimo.com/v1"', f'base_url = {json.dumps(url)}'),
                     ('model = "mimo-v2.5-pro"', f'model = {json.dumps(model)}'),
                     ('api_key_env = "MIMO_API_KEY"', f'api_key_env = {json.dumps(preset.api_key_env)}')]:
        text = text.replace(old, new)
    if provider != "mimo":
        text = text.replace("max_tokens = 24000", "max_tokens = 8192")
        text = text.replace("temperature = 0.2", "# temperature omitted; uses the model default (set explicitly if supported)")
    text += "\n# Optional independent vision model; see docs/providers.md\n# [vision]\n# provider = \"qwen\"\n# model = \"YOUR_VISION_MODEL_ID\"\n"
    path.write_text(text, encoding="utf-8")


def parse_llm_config(data: dict, inherit: LlmConfig | None = None) -> LlmConfig:
    if not isinstance(data, dict):
        raise ValueError("llm and vision configuration must be TOML tables")
    provider = canonical_provider(str(data.get("provider", inherit.provider if inherit else "mimo")))
    preset = PROVIDERS[provider]
    # Changing provider must not inherit another vendor's URL, key or extras.
    parent = inherit if inherit and provider == canonical_provider(inherit.provider) else None
    def option(name, default):
        return data.get(name, getattr(parent, name, default) if parent else default)
    model = str(option("model", "mimo-v2.5-pro" if provider == "mimo" else ""))
    base_url = str(option("base_url", preset.base_url)).rstrip("/")
    if not model or model.startswith("YOUR_"):
        raise ValueError(f"A valid model ID is required for provider {provider}.")
    if not base_url.startswith(("https://", "http://")):
        raise ValueError(f"A valid HTTP(S) base_url is required for provider {provider}.")
    if base_url.endswith(("/chat/completions", "/messages")):
        raise ValueError("base_url must be the API root, not the complete operation URL.")
    temperature = option("temperature", 0.2 if provider == "mimo" else None)
    if type(data.get("omit_temperature", False)) is not bool:
        raise ValueError("omit_temperature must be a boolean")
    if data.get("omit_temperature", False):
        temperature = None
    extra_body = option("extra_body", {})
    if not isinstance(extra_body, dict):
        raise ValueError("extra_body must be a TOML table")
    config = LlmConfig(
        provider=provider, base_url=base_url, model=model,
        api_key_env=str(option("api_key_env", preset.api_key_env)),
        temperature=float(temperature) if temperature is not None else None,
        max_tokens=int(option("max_tokens", 24000 if provider == "mimo" else 8192)),
        timeout_seconds=int(option("timeout_seconds", 900)), stream=option("stream", True),
        max_tokens_parameter=str(option("max_tokens_parameter", "auto")), extra_body=extra_body,
        api_key_value=str(data.get("api_key", parent.api_key_value if parent else "")),
        require_api_key=option("require_api_key", True),
    )
    if config.max_tokens <= 0 or config.timeout_seconds <= 0:
        raise ValueError("max_tokens and timeout_seconds must be positive")
    if config.max_tokens_parameter not in {"auto", "max_tokens", "max_completion_tokens"}:
        raise ValueError("max_tokens_parameter must be auto, max_tokens or max_completion_tokens")
    if type(config.stream) is not bool or type(config.require_api_key) is not bool:
        raise ValueError("stream and require_api_key must be booleans")
    return config


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}. Run: python -m paperdeepread init-config")

    data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    llm = data.get("llm", {})
    pipeline = data.get("pipeline", {})
    pdffigures2 = data.get("pdffigures2", {})

    llm_config = parse_llm_config(llm)
    return AppConfig(
        llm=llm_config,
        vision=parse_llm_config(data["vision"], inherit=llm_config) if "vision" in data else None,
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
