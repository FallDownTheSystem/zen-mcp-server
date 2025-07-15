"""Tests for LiteLLMProvider functionality."""

from unittest.mock import MagicMock, patch

import pytest

from providers.base import ProviderType
from providers.litellm_provider import LiteLLMProvider


class TestLiteLLMProvider:
    """Test LiteLLMProvider class functionality."""

    def test_provider_initialization(self):
        """Test LiteLLMProvider initializes correctly."""
        provider = LiteLLMProvider()

        assert provider.get_provider_type() == ProviderType.CUSTOM
        assert provider.FRIENDLY_NAME == "LiteLLM"
        assert provider.api_key == ""  # No API key needed

    def test_provider_initialization_with_metadata(self):
        """Test LiteLLMProvider initializes with model metadata."""
        metadata = {
            "gpt-4": {
                "friendly_name": "GPT-4",
                "context_window": 128000,
                "max_output_tokens": 4096,
                "supports_temperature": True,
                "temperature_constraint": "range",
            }
        }
        provider = LiteLLMProvider(model_metadata=metadata)

        assert provider.model_metadata == metadata

    def test_validate_model_name_always_true(self):
        """Test validate_model_name always returns True for LiteLLM."""
        provider = LiteLLMProvider()

        # LiteLLM handles its own validation
        assert provider.validate_model_name("gpt-4")
        assert provider.validate_model_name("gemini-pro")
        assert provider.validate_model_name("unknown-model")
        assert provider.validate_model_name("any/model/name")

    def test_get_capabilities_with_metadata(self):
        """Test get_capabilities returns metadata when available."""
        metadata = {
            "o3": {
                "friendly_name": "O3",
                "context_window": 200000,
                "max_output_tokens": 100000,
                "supports_extended_thinking": True,
                "supports_temperature": False,
                "temperature_constraint": "fixed",
            }
        }
        provider = LiteLLMProvider(model_metadata=metadata)

        capabilities = provider.get_capabilities("o3")

        assert capabilities.provider == ProviderType.CUSTOM
        assert capabilities.model_name == "o3"
        assert capabilities.friendly_name == "O3"
        assert capabilities.context_window == 200000
        assert capabilities.max_output_tokens == 100000
        assert capabilities.supports_extended_thinking is True
        assert capabilities.supports_temperature is False

    def test_get_capabilities_default(self):
        """Test get_capabilities returns defaults for unknown models."""
        provider = LiteLLMProvider()

        capabilities = provider.get_capabilities("unknown-model")

        assert capabilities.provider == ProviderType.CUSTOM
        assert capabilities.model_name == "unknown-model"
        assert capabilities.friendly_name == "LiteLLM Model"
        assert capabilities.context_window == 128000
        assert capabilities.max_output_tokens == 8192
        assert capabilities.supports_extended_thinking is False
        assert capabilities.supports_system_prompts is True
        assert capabilities.supports_streaming is True

    def test_supports_thinking_mode_from_metadata(self):
        """Test supports_thinking_mode checks metadata first."""
        metadata = {
            "custom-thinking-model": {"supports_extended_thinking": True},
            "regular-model": {"supports_extended_thinking": False},
        }
        provider = LiteLLMProvider(model_metadata=metadata)

        assert provider.supports_thinking_mode("custom-thinking-model") is True
        assert provider.supports_thinking_mode("regular-model") is False

    def test_supports_thinking_mode_known_models(self):
        """Test supports_thinking_mode detects known thinking models."""
        provider = LiteLLMProvider()

        # O3 and O4 models support thinking
        assert provider.supports_thinking_mode("o3") is True
        assert provider.supports_thinking_mode("o3-mini") is True
        assert provider.supports_thinking_mode("o4-mini") is True
        assert provider.supports_thinking_mode("O3-Pro") is True  # Case insensitive

        # Other models don't
        assert provider.supports_thinking_mode("gpt-4") is False
        assert provider.supports_thinking_mode("gemini-pro") is False

    @patch("providers.litellm_provider.litellm.token_counter")
    def test_count_tokens_success(self, mock_token_counter):
        """Test count_tokens uses LiteLLM's token counter."""
        provider = LiteLLMProvider()
        mock_token_counter.return_value = 42

        count = provider.count_tokens("Hello world", "gpt-4")

        assert count == 42
        mock_token_counter.assert_called_once_with(model="gpt-4", text="Hello world")

    @patch("providers.litellm_provider.litellm.token_counter")
    def test_count_tokens_fallback(self, mock_token_counter):
        """Test count_tokens falls back to estimation on error."""
        provider = LiteLLMProvider()
        mock_token_counter.side_effect = Exception("Token counting failed")

        # Should fall back to 4 chars per token
        count = provider.count_tokens("Hello world!", "gpt-4")  # 12 chars

        assert count == 3  # 12 / 4 = 3

    @patch("providers.litellm_provider.completion")
    def test_generate_content_basic(self, mock_completion):
        """Test generate_content with basic parameters."""
        provider = LiteLLMProvider()

        # Mock LiteLLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_response.id = "test-id"
        mock_response.model = "gpt-4"
        mock_completion.return_value = mock_response

        response = provider.generate_content(prompt="Hello", model_name="gpt-4", temperature=0.7)

        assert response.content == "Test response"
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 5
        assert response.usage["total_tokens"] == 15
        assert response.model_name == "gpt-4"
        assert response.friendly_name == "LiteLLM"
        assert response.provider == ProviderType.CUSTOM

        # Check call to LiteLLM
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "gpt-4"
        assert call_kwargs["temperature"] == 0.7
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"
        assert call_kwargs["messages"][0]["content"] == "Hello"

    @patch("providers.litellm_provider.completion")
    def test_generate_content_with_system_prompt(self, mock_completion):
        """Test generate_content with system prompt."""
        provider = LiteLLMProvider()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage = None  # Test missing usage
        mock_completion.return_value = mock_response

        provider.generate_content(
            prompt="Hello", model_name="gpt-4", system_prompt="You are helpful", temperature=0.5, max_output_tokens=100
        )

        # Check messages include system prompt
        call_kwargs = mock_completion.call_args[1]
        assert len(call_kwargs["messages"]) == 2
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][0]["content"] == "You are helpful"
        assert call_kwargs["messages"][1]["role"] == "user"
        assert call_kwargs["messages"][1]["content"] == "Hello"
        assert call_kwargs["max_tokens"] == 100

    @patch("providers.litellm_provider.completion")
    def test_generate_content_with_timeout(self, mock_completion):
        """Test generate_content passes timeout correctly."""
        provider = LiteLLMProvider()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test"
        mock_completion.return_value = mock_response

        provider.generate_content(prompt="Hello", model_name="gpt-4", timeout=30.0)  # Tool passes timeout

        # Check timeout was passed to LiteLLM
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["timeout"] == 30.0

    @patch("providers.litellm_provider.completion")
    def test_generate_content_exception_handling(self, mock_completion):
        """Test generate_content handles LiteLLM exceptions."""
        provider = LiteLLMProvider()

        # Test various LiteLLM exceptions
        from litellm.exceptions import RateLimitError, Timeout

        # Test timeout error
        mock_completion.side_effect = Timeout("Timeout", "gpt-4", "openai")

        with pytest.raises(Timeout):
            provider.generate_content("Hello", "gpt-4")

        # Test rate limit error
        mock_completion.side_effect = RateLimitError("Rate limited", "gpt-4", "openai")

        with pytest.raises(RateLimitError):
            provider.generate_content("Hello", "gpt-4")

    @pytest.mark.asyncio
    @patch("providers.litellm_provider.acompletion")
    async def test_agenerate_content_basic(self, mock_acompletion):
        """Test async generate_content."""
        provider = LiteLLMProvider()

        # Mock async response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Async response"
        mock_response.usage.prompt_tokens = 8
        mock_response.usage.completion_tokens = 4
        mock_response.usage.total_tokens = 12
        mock_acompletion.return_value = mock_response

        response = await provider.agenerate_content(prompt="Hello async", model_name="gpt-4", temperature=0.3)

        assert response.content == "Async response"
        assert response.usage["input_tokens"] == 8
        assert response.usage["output_tokens"] == 4
        assert response.usage["total_tokens"] == 12

        # Check async call
        mock_acompletion.assert_called_once()
        call_kwargs = mock_acompletion.call_args[1]
        assert call_kwargs["model"] == "gpt-4"
        assert call_kwargs["temperature"] == 0.3
