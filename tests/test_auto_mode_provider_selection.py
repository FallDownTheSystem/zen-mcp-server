"""Test auto mode provider selection logic specifically"""

import os

import pytest

from providers.base import ProviderType
from providers.registry import ModelProviderRegistry
from tools.models import ToolModelCategory


@pytest.mark.no_mock_provider
class TestAutoModeProviderSelection:
    """Test the core auto mode provider selection logic"""

    def setup_method(self):
        """Set up clean state before each test."""
        # Clear restriction service cache
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        # Clear provider registry
        registry = ModelProviderRegistry()
        registry._providers.clear()
        registry._initialized_providers.clear()

    def teardown_method(self):
        """Clean up after each test."""
        # Clear restriction service cache
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    def test_gemini_only_fallback_selection(self):
        """Test auto mode fallback when only Gemini is available."""

        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up environment - only Gemini available
            os.environ["GEMINI_API_KEY"] = "test-key"
            for key in ["OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Register only Gemini provider
            from providers.gemini import GeminiModelProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

            # Test fallback selection for different categories
            extended_reasoning = ModelProviderRegistry.get_preferred_fallback_model(
                ToolModelCategory.EXTENDED_REASONING
            )
            fast_response = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)
            balanced = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.BALANCED)

            # Should select appropriate Gemini models
            assert extended_reasoning in ["gemini-2.5-pro", "pro"]
            assert fast_response in ["gemini-2.5-flash", "flash"]
            assert balanced in ["gemini-2.5-flash", "flash"]

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

    def test_openai_only_fallback_selection(self):
        """Test auto mode fallback when only OpenAI is available."""

        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up environment - only OpenAI available
            os.environ["OPENAI_API_KEY"] = "test-key"
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Register only OpenAI provider
            from providers.openai_provider import OpenAIModelProvider

            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)

            # Test fallback selection for different categories
            extended_reasoning = ModelProviderRegistry.get_preferred_fallback_model(
                ToolModelCategory.EXTENDED_REASONING
            )
            fast_response = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)
            balanced = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.BALANCED)

            # Should select appropriate OpenAI models
            assert extended_reasoning in ["o3", "o3-mini", "o4-mini"]  # Any available OpenAI model for reasoning
            assert fast_response in ["o4-mini", "o3-mini"]  # Prefer faster models
            assert balanced in ["o4-mini", "o3-mini"]  # Balanced selection

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

    def test_both_gemini_and_openai_priority(self):
        """Test auto mode when both Gemini and OpenAI are available."""

        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up environment - both Gemini and OpenAI available
            os.environ["GEMINI_API_KEY"] = "test-key"
            os.environ["OPENAI_API_KEY"] = "test-key"
            for key in ["XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Register both providers
            from providers.gemini import GeminiModelProvider
            from providers.openai_provider import OpenAIModelProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)

            # Test fallback selection for different categories
            extended_reasoning = ModelProviderRegistry.get_preferred_fallback_model(
                ToolModelCategory.EXTENDED_REASONING
            )
            fast_response = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)

            # Should prefer OpenAI for reasoning (based on fallback logic)
            assert extended_reasoning == "o3"  # Should prefer O3 for extended reasoning

            # Should prefer OpenAI for fast response
            assert fast_response == "o4-mini"  # Should prefer O4-mini for fast response

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

    def test_xai_only_fallback_selection(self):
        """Test auto mode fallback when only XAI is available."""

        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up environment - only XAI available
            os.environ["XAI_API_KEY"] = "test-key"
            for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Register only XAI provider
            from providers.xai import XAIModelProvider

            ModelProviderRegistry.register_provider(ProviderType.XAI, XAIModelProvider)

            # Test fallback selection for different categories
            extended_reasoning = ModelProviderRegistry.get_preferred_fallback_model(
                ToolModelCategory.EXTENDED_REASONING
            )
            fast_response = ModelProviderRegistry.get_preferred_fallback_model(ToolModelCategory.FAST_RESPONSE)

            # Should fallback to available models or default fallbacks
            # Since XAI models are not explicitly handled in fallback logic,
            # it should fall back to the hardcoded defaults
            assert extended_reasoning is not None
            assert fast_response is not None

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

    def test_available_models_respects_restrictions(self):
        """Test that get_available_models respects model restrictions."""

        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "OPENAI_ALLOWED_MODELS"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up environment with restrictions
            os.environ["GEMINI_API_KEY"] = "test-key"
            os.environ["OPENAI_API_KEY"] = "test-key"
            os.environ["OPENAI_ALLOWED_MODELS"] = "o4-mini"  # Only allow o4-mini

            # Clear restriction service to pick up new restrictions
            import utils.model_restrictions

            utils.model_restrictions._restriction_service = None

            # Register both providers
            from providers.gemini import GeminiModelProvider
            from providers.openai_provider import OpenAIModelProvider

            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)

            # Get available models with restrictions
            available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)

            # Should include allowed OpenAI model
            assert "o4-mini" in available_models
            assert available_models["o4-mini"] == ProviderType.OPENAI

            # Should NOT include restricted OpenAI models
            assert "o3" not in available_models
            assert "o3-mini" not in available_models

            # Should include all Gemini models (no restrictions)
            assert "gemini-2.5-flash" in available_models
            assert available_models["gemini-2.5-flash"] == ProviderType.GOOGLE

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

    def test_model_validation_across_providers(self):
        """Test that model validation works correctly with LiteLLM unified provider."""

        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up all providers
            os.environ["GEMINI_API_KEY"] = "test-key"
            os.environ["OPENAI_API_KEY"] = "test-key"
            os.environ["XAI_API_KEY"] = "test-key"

            # With LiteLLM, all models go through the same provider
            # Test that various model names return the LiteLLM provider
            from providers.litellm_provider import LiteLLMProvider

            # Ensure LiteLLM provider is registered
            ModelProviderRegistry.register_provider(ProviderType.CUSTOM, LiteLLMProvider)

            # Test model validation - all models should go through LiteLLM
            # Gemini models
            gemini_provider = ModelProviderRegistry.get_provider_for_model("flash")
            assert gemini_provider is not None
            assert gemini_provider.get_provider_type() == ProviderType.CUSTOM

            # OpenAI models
            openai_provider = ModelProviderRegistry.get_provider_for_model("o3")
            assert openai_provider is not None
            assert openai_provider.get_provider_type() == ProviderType.CUSTOM

            # Should be the same provider type
            assert isinstance(gemini_provider, type(openai_provider))

            # XAI models
            xai_provider = ModelProviderRegistry.get_provider_for_model("grok")
            assert xai_provider is not None
            assert xai_provider.get_provider_type() == ProviderType.CUSTOM

            # Even invalid models return the LiteLLM provider
            # (LiteLLM will handle the validation and error)
            invalid_provider = ModelProviderRegistry.get_provider_for_model("invalid-model-name")
            assert invalid_provider is not None
            assert invalid_provider.get_provider_type() == ProviderType.CUSTOM

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

    def test_alias_resolution_before_api_calls(self):
        """Test that model aliases work correctly with LiteLLM provider."""

        # Save original environment
        original_env = {}
        for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY"]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up all providers
            os.environ["GEMINI_API_KEY"] = "test-key"
            os.environ["OPENAI_API_KEY"] = "test-key"
            os.environ["XAI_API_KEY"] = "test-key"

            # With LiteLLM, alias resolution is handled by LiteLLM's config
            from providers.litellm_provider import LiteLLMProvider

            # Ensure LiteLLM provider is registered
            ModelProviderRegistry.register_provider(ProviderType.CUSTOM, LiteLLMProvider)

            # Test that various aliases go through LiteLLM provider
            test_aliases = [
                "flash",  # Gemini alias
                "pro",  # Gemini alias
                "mini",  # OpenAI alias
                "o3mini",  # OpenAI alias
                "grok",  # XAI alias
                "grok3",  # XAI alias
                "grok3fast",  # XAI alias
            ]

            for alias in test_aliases:
                provider = ModelProviderRegistry.get_provider_for_model(alias)
                assert provider is not None, f"No provider found for alias '{alias}'"
                assert provider.get_provider_type() == ProviderType.CUSTOM, f"Expected CUSTOM provider for '{alias}'"

                # With LiteLLM, the provider itself doesn't resolve aliases
                # LiteLLM handles that internally during API calls
                # So we just verify the provider accepts these model names
                assert provider.validate_model_name(alias) is True

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)
