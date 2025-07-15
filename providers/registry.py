"""Model provider registry for managing available providers."""

import logging
import os
from typing import TYPE_CHECKING, Optional

from .base import ModelProvider, ProviderType

if TYPE_CHECKING:
    from tools.models import ToolModelCategory


class ModelProviderRegistry:
    """Registry for managing model providers."""

    _instance = None

    def __new__(cls):
        """Singleton pattern for registry."""
        if cls._instance is None:
            logging.debug("REGISTRY: Creating new registry instance")
            cls._instance = super().__new__(cls)
            # Initialize instance dictionaries on first creation
            cls._instance._providers = {}
            cls._instance._initialized_providers = {}
            logging.debug(f"REGISTRY: Created instance {cls._instance}")
        return cls._instance

    @classmethod
    def register_provider(cls, provider_type: ProviderType, provider_class: type[ModelProvider]) -> None:
        """Register a new provider class.

        Args:
            provider_type: Type of the provider (e.g., ProviderType.GOOGLE)
            provider_class: Class that implements ModelProvider interface
        """
        instance = cls()
        instance._providers[provider_type] = provider_class

    @classmethod
    def get_provider(cls, provider_type: ProviderType, force_new: bool = False) -> Optional[ModelProvider]:
        """Get an initialized provider instance.

        Args:
            provider_type: Type of provider to get
            force_new: Force creation of new instance instead of using cached

        Returns:
            Initialized ModelProvider instance or None if not available
        """
        instance = cls()

        # Return cached instance if available and not forcing new
        if not force_new and provider_type in instance._initialized_providers:
            return instance._initialized_providers[provider_type]

        # Check if provider class is registered
        if provider_type not in instance._providers:
            return None

        # Get API key from environment
        api_key = cls._get_api_key_for_provider(provider_type)

        # Get provider class or factory function
        provider_class = instance._providers[provider_type]

        # For custom providers, handle special initialization requirements
        if provider_type == ProviderType.CUSTOM:
            # Check if it's LiteLLMProvider - it doesn't need special handling
            from .litellm_provider import LiteLLMProvider

            if provider_class == LiteLLMProvider:
                # LiteLLMProvider doesn't need API key or URL - it uses env vars directly
                provider = provider_class()
            # Check if it's a factory function (callable but not a class)
            elif callable(provider_class) and not isinstance(provider_class, type):
                # Factory function - call it with api_key parameter
                provider = provider_class(api_key=api_key)
            else:
                # Legacy custom provider - need to handle URL requirement
                custom_url = os.getenv("CUSTOM_API_URL", "")
                if not custom_url:
                    if api_key:  # Key is set but URL is missing
                        logging.warning("CUSTOM_API_KEY set but CUSTOM_API_URL missing – skipping Custom provider")
                    return None
                # Use empty string as API key for custom providers that don't need auth (e.g., Ollama)
                # This allows the provider to be created even without CUSTOM_API_KEY being set
                api_key = api_key or ""
                # Initialize custom provider with both API key and base URL
                provider = provider_class(api_key=api_key, base_url=custom_url)
        else:
            if not api_key:
                return None
            # Initialize non-custom provider with just API key
            provider = provider_class(api_key=api_key)

        # Cache the instance
        instance._initialized_providers[provider_type] = provider

        return provider

    @classmethod
    def get_provider_for_model(cls, model_name: str) -> Optional[ModelProvider]:
        """Get provider instance for a specific model name.

        With LiteLLM integration, all models are handled by the single LiteLLMProvider.

        Args:
            model_name: Name of the model (e.g., "gemini-2.5-flash", "o3-mini")

        Returns:
            ModelProvider instance that supports this model
        """
        logging.debug(f"get_provider_for_model called with model_name='{model_name}'")

        # With LiteLLM, we only have one provider that handles all models
        instance = cls()
        logging.debug(f"Registry instance: {instance}")
        logging.debug(f"Available providers in registry: {list(instance._providers.keys())}")

        # LiteLLM provider is registered as CUSTOM type
        if ProviderType.CUSTOM in instance._providers:
            provider = cls.get_provider(ProviderType.CUSTOM)
            if provider:
                # LiteLLM provider always returns True for model validation
                # It will handle errors during actual API calls
                logging.debug(f"Returning LiteLLMProvider for model {model_name}")
                return provider

        logging.debug(f"No LiteLLM provider found for model {model_name}")
        return None

    @classmethod
    def get_available_providers(cls) -> list[ProviderType]:
        """Get list of registered provider types."""
        instance = cls()
        return list(instance._providers.keys())

    @classmethod
    def get_available_models(cls, respect_restrictions: bool = True) -> dict[str, ProviderType]:
        """Get mapping of all available models to their providers.

        Args:
            respect_restrictions: If True, filter out models not allowed by restrictions

        Returns:
            Dict mapping model names to provider types
        """
        # Import here to avoid circular imports
        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service() if respect_restrictions else None
        models: dict[str, ProviderType] = {}
        instance = cls()

        for provider_type in instance._providers:
            provider = cls.get_provider(provider_type)
            if not provider:
                continue

            try:
                available = provider.list_models(respect_restrictions=respect_restrictions)
            except NotImplementedError:
                logging.warning("Provider %s does not implement list_models", provider_type)
                continue

            for model_name in available:
                # =====================================================================================
                # CRITICAL: Prevent double restriction filtering (Fixed Issue #98)
                # =====================================================================================
                # Previously, both the provider AND registry applied restrictions, causing
                # double-filtering that resulted in "no models available" errors.
                #
                # Logic: If respect_restrictions=True, provider already filtered models,
                # so registry should NOT filter them again.
                # TEST COVERAGE: tests/test_provider_routing_bugs.py::TestOpenRouterAliasRestrictions
                # =====================================================================================
                if (
                    restriction_service
                    and not respect_restrictions  # Only filter if provider didn't already filter
                    and not restriction_service.is_allowed(provider_type, model_name)
                ):
                    logging.debug("Model %s filtered by restrictions", model_name)
                    continue
                models[model_name] = provider_type

        return models

    @classmethod
    def get_available_model_names(cls, provider_type: Optional[ProviderType] = None) -> list[str]:
        """Get list of available model names, optionally filtered by provider.

        This respects model restrictions automatically.

        Args:
            provider_type: Optional provider to filter by

        Returns:
            List of available model names
        """
        available_models = cls.get_available_models(respect_restrictions=True)

        if provider_type:
            # Filter by specific provider
            return [name for name, ptype in available_models.items() if ptype == provider_type]
        else:
            # Return all available models
            return list(available_models.keys())

    @classmethod
    def _get_api_key_for_provider(cls, provider_type: ProviderType) -> Optional[str]:
        """Get API key for a provider from environment variables.

        Args:
            provider_type: Provider type to get API key for

        Returns:
            API key string or None if not found
        """
        key_mapping = {
            ProviderType.GOOGLE: "GEMINI_API_KEY",
            ProviderType.OPENAI: "OPENAI_API_KEY",
            ProviderType.XAI: "XAI_API_KEY",
            ProviderType.OPENROUTER: "OPENROUTER_API_KEY",
            ProviderType.CUSTOM: "CUSTOM_API_KEY",  # Can be empty for providers that don't need auth
            ProviderType.DIAL: "DIAL_API_KEY",
        }

        env_var = key_mapping.get(provider_type)
        if not env_var:
            return None

        return os.getenv(env_var)

    @classmethod
    def get_preferred_fallback_model(cls, tool_category: Optional["ToolModelCategory"] = None) -> str:
        """Get the preferred fallback model based on available API keys and tool category.

        This method checks which providers have valid API keys and returns
        a sensible default model for auto mode fallback situations.

        Takes into account model restrictions when selecting fallback models.

        Args:
            tool_category: Optional category to influence model selection

        Returns:
            Model name string for fallback use
        """
        # Import here to avoid circular import
        from tools.models import ToolModelCategory

        # Get available models respecting restrictions
        available_models = cls.get_available_models(respect_restrictions=True)

        # With LiteLLM, all models are registered under CUSTOM provider type
        # So we just work with the model names directly
        all_models = list(available_models.keys())

        if not all_models:
            # No models available due to restrictions
            logging.warning("No models available due to restrictions")
            return "gemini-2.5-flash"  # Default fallback

        if tool_category == ToolModelCategory.EXTENDED_REASONING:
            # Prefer thinking-capable models for deep reasoning tools
            if "o3" in all_models:
                return "o3"  # O3 for deep reasoning
            elif "grok-3" in all_models:
                return "grok-3"  # GROK-3 for deep reasoning
            elif any("pro" in m for m in all_models):
                # Find the pro model
                return next(m for m in all_models if "pro" in m)
            elif all_models:
                # Fall back to first available model
                return all_models[0]
            else:
                return "gemini-2.5-pro"  # Default

        elif tool_category == ToolModelCategory.FAST_RESPONSE:
            # Prefer fast, cost-efficient models
            if "o4-mini" in all_models:
                return "o4-mini"  # Latest, fast and efficient
            elif "o3-mini" in all_models:
                return "o3-mini"  # Second choice
            elif "grok-3-fast" in all_models:
                return "grok-3-fast"  # GROK-3 Fast for speed
            elif any("flash" in m for m in all_models):
                # Find flash models and prefer newer versions
                flash_models = [m for m in all_models if "flash" in m]
                flash_models_sorted = sorted(flash_models, reverse=True)
                return flash_models_sorted[0]
            elif all_models:
                return all_models[0]
            else:
                return "gemini-2.5-flash"  # Default

        # BALANCED or no category specified
        if "o4-mini" in all_models:
            return "o4-mini"  # Latest balanced performance/cost
        elif "o3-mini" in all_models:
            return "o3-mini"  # Second choice
        elif "grok-3" in all_models:
            return "grok-3"  # GROK-3 as balanced choice
        elif any("flash" in m for m in all_models):
            # Prefer newer flash models
            flash_models = [m for m in all_models if "flash" in m]
            flash_models_sorted = sorted(flash_models, reverse=True)
            return flash_models_sorted[0]
        elif all_models:
            return all_models[0]
        else:
            # Return a reasonable default for backward compatibility
            return "gemini-2.5-flash"

    @classmethod
    def _find_extended_thinking_model(cls) -> Optional[str]:
        """Find a model suitable for extended reasoning.

        This method is kept for backward compatibility but simplified
        for LiteLLM integration.

        Returns:
            Model name if found, None otherwise
        """
        # With LiteLLM, we can check available models directly
        available_models = cls.get_available_models(respect_restrictions=True)
        model_names = list(available_models.keys())

        # Prefer models known for deep reasoning
        preferred_models = ["o3", "o3-pro", "o3-deep-research", "gemini-2.5-pro", "grok-3"]

        for model in preferred_models:
            if model in model_names:
                return model

        # Return None if no suitable model found
        return None

    @classmethod
    def get_available_providers_with_keys(cls) -> list[ProviderType]:
        """Get list of provider types that have valid API keys.

        Returns:
            List of ProviderType values for providers with valid API keys
        """
        available = []
        instance = cls()
        for provider_type in instance._providers:
            if cls.get_provider(provider_type) is not None:
                available.append(provider_type)
        return available

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached provider instances."""
        instance = cls()
        instance._initialized_providers.clear()

    @classmethod
    def unregister_provider(cls, provider_type: ProviderType) -> None:
        """Unregister a provider (mainly for testing)."""
        instance = cls()
        instance._providers.pop(provider_type, None)
        instance._initialized_providers.pop(provider_type, None)
