"""Model provider abstractions for supporting multiple AI providers."""

from .base import ModelCapabilities, ModelProvider, ModelResponse, ProviderType
from .litellm_provider import LiteLLMProvider
from .registry import ModelProviderRegistry

# Keep legacy imports for backward compatibility during migration
try:
    from .gemini import GeminiModelProvider
    from .openai_compatible import OpenAICompatibleProvider
    from .openai_provider import OpenAIModelProvider
    from .openrouter import OpenRouterProvider
except ImportError:
    # Legacy providers may be removed in task 6
    pass

__all__ = [
    "ModelProvider",
    "ModelResponse",
    "ModelCapabilities",
    "ModelProviderRegistry",
    "ProviderType",
    "LiteLLMProvider",
]
