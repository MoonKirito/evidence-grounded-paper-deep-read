"""Provider factory. Imports are lazy to avoid configuration cycles."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paperdeepread.config import LlmConfig
    from paperdeepread.providers.base import ModelClient


def create_client(config: LlmConfig) -> ModelClient:
    from paperdeepread.providers.presets import PROVIDERS, canonical_provider
    from paperdeepread.providers.openai_compatible import OpenAICompatibleClient
    from paperdeepread.providers.anthropic import AnthropicClient
    from paperdeepread.providers.gemini import GeminiClient
    protocol = PROVIDERS[canonical_provider(config.provider)].protocol
    return {"openai": OpenAICompatibleClient, "anthropic": AnthropicClient, "gemini": GeminiClient}[protocol](config)
