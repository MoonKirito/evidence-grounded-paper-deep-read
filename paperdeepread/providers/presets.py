"""Provider endpoints; model IDs remain a user choice."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPreset:
    protocol: str
    base_url: str
    api_key_env: str


PROVIDERS = {
    "mimo": ProviderPreset("openai", "https://token-plan-cn.xiaomimimo.com/v1", "MIMO_API_KEY"),
    "openai": ProviderPreset("openai", "https://api.openai.com/v1", "OPENAI_API_KEY"),
    "anthropic": ProviderPreset("anthropic", "https://api.anthropic.com/v1", "ANTHROPIC_API_KEY"),
    "gemini": ProviderPreset("gemini", "https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY"),
    "deepseek": ProviderPreset("openai", "https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    "qwen": ProviderPreset("openai", "https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "moonshot": ProviderPreset("openai", "https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    "zhipu": ProviderPreset("openai", "https://open.bigmodel.cn/api/paas/v4", "ZHIPU_API_KEY"),
    "doubao": ProviderPreset("openai", "https://ark.cn-beijing.volces.com/api/v3", "ARK_API_KEY"),
    "minimax": ProviderPreset("openai", "https://api.minimax.cn/v1", "MINIMAX_API_KEY"),
    "xai": ProviderPreset("openai", "https://api.x.ai/v1", "XAI_API_KEY"),
    "openrouter": ProviderPreset("openai", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "siliconflow": ProviderPreset("openai", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "openai_compatible": ProviderPreset("openai", "", "LLM_API_KEY"),
}
ALIASES = {"claude": "anthropic", "google": "gemini", "kimi": "moonshot",
           "glm": "zhipu", "dashscope": "qwen", "ark": "doubao", "grok": "xai",
           "openai-compatible": "openai_compatible"}


def canonical_provider(name: str) -> str:
    name = name.strip().lower()
    name = ALIASES.get(name, name)
    if name not in PROVIDERS:
        raise ValueError(f"Unsupported provider: {name}. Choose from: {', '.join(PROVIDERS)}")
    return name
