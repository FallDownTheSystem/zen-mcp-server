"""Model provider abstractions for supporting multiple AI providers."""

from .gemini import GeminiModelProvider
from .openai_compatible import OpenAICompatibleProvider
from .openai_provider import OpenAIProvider
from .openrouter import OpenRouterProvider
from .base import ModelCapabilities, ModelProvider, ModelResponse, ProviderType
from .litellm_provider import LiteLLMProvider
from .registry import ModelProviderRegistry

# Legacy providers removed in task 6 - all models now use LiteLLMProvider

__all__ = [
    "ModelProvider",
    "ModelResponse",
    "ModelCapabilities",
    "ModelProviderRegistry",
    "GeminiModelProvider",
    "OpenAIProvider",
    "OpenAICompatibleProvider",
    "OpenRouterProvider",
    "ProviderType",
    "LiteLLMProvider",
]
