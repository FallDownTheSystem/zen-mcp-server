"""Tests for CustomOpenAI provider implementation."""

import json
import os
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError, URLError

import pytest

from providers.base import ProviderType
from providers.custom_openai import CustomOpenAI


class TestCustomOpenAIProvider:
    """Test CustomOpenAI provider functionality."""

    def setup_method(self):
        """Set up clean state before each test."""
        # Clear restriction service cache before each test
        import utils.model_restrictions
        utils.model_restrictions._restriction_service = None

    def teardown_method(self):
        """Clean up after each test to avoid singleton issues."""
        # Clear restriction service cache after each test
        import utils.model_restrictions
        utils.model_restrictions._restriction_service = None

    def test_initialization(self):
        """Test provider initialization."""
        provider = CustomOpenAI("test-key")
        assert provider.api_key == "test-key"
        assert provider.get_provider_type() == ProviderType.OPENAI
        assert provider.base_url == "https://api.openai.com/v1"

    def test_initialization_with_custom_url(self):
        """Test provider initialization with custom base URL."""
        provider = CustomOpenAI("test-key", base_url="https://custom.openai.com/v1")
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://custom.openai.com/v1"

    def test_model_validation(self):
        """Test model name validation."""
        provider = CustomOpenAI("test-key")

        # Test valid model
        assert provider.validate_model_name("o3-mini") is True
        
        # Test invalid models
        assert provider.validate_model_name("gpt-4") is False
        assert provider.validate_model_name("invalid-model") is False

    def test_get_capabilities(self):
        """Test getting model capabilities."""
        provider = CustomOpenAI("test-key")
        
        capabilities = provider.get_capabilities("o3-mini")
        assert capabilities.provider == ProviderType.OPENAI
        assert capabilities.model_name == "o3-mini"
        assert capabilities.friendly_name == "OpenAI o3-mini"
        assert capabilities.context_window == 200000
        assert capabilities.max_output_tokens == 100000
        assert capabilities.supports_extended_thinking is True
        assert capabilities.supports_system_prompts is True
        assert capabilities.supports_streaming is False
        assert capabilities.supports_function_calling is True
        assert capabilities.supports_images is False
        assert capabilities.supports_temperature is True
        assert capabilities.timeout == 300.0

    def test_get_capabilities_invalid_model(self):
        """Test getting capabilities for invalid model."""
        provider = CustomOpenAI("test-key")
        
        with pytest.raises(ValueError, match="Model invalid-model not supported"):
            provider.get_capabilities("invalid-model")

    def test_supports_thinking_mode(self):
        """Test thinking mode support."""
        provider = CustomOpenAI("test-key")
        
        assert provider.supports_thinking_mode("o3-mini") is True
        assert provider.supports_thinking_mode("invalid-model") is False

    def test_count_tokens(self):
        """Test token counting (simplified approximation)."""
        provider = CustomOpenAI("test-key")
        
        # Test basic token counting (4 chars per token approximation)
        text = "Hello world"
        token_count = provider.count_tokens(text, "o3-mini")
        expected_tokens = len(text) // 4
        assert token_count == expected_tokens

    @patch('urllib.request.urlopen')
    def test_generate_content_success(self, mock_urlopen):
        """Test successful content generation."""
        provider = CustomOpenAI("test-key")
        
        # Mock successful response
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Hello, this is a test response."}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18
            }
        }).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response
        
        result = provider.generate_content(
            prompt="Test prompt",
            model_name="o3-mini",
            system_prompt="You are a helpful assistant.",
            temperature=1.0
        )
        
        assert result.content == "Hello, this is a test response."
        assert result.usage["input_tokens"] == 10
        assert result.usage["output_tokens"] == 8
        assert result.usage["total_tokens"] == 18
        assert result.model_name == "o3-mini"
        assert result.friendly_name == "OpenAI o3-mini"
        assert result.provider == ProviderType.OPENAI

    @patch('urllib.request.urlopen')
    def test_generate_content_with_large_payload(self, mock_urlopen):
        """Test content generation with large payload (150k chars)."""
        provider = CustomOpenAI("test-key")
        
        # Create a large prompt (~150k characters)
        large_prompt = "A" * 150000
        
        # Mock successful response
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Processed large payload successfully."}}],
            "usage": {
                "prompt_tokens": 37500,  # ~150k/4
                "completion_tokens": 10,
                "total_tokens": 37510
            }
        }).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response
        
        result = provider.generate_content(
            prompt=large_prompt,
            model_name="o3-mini",
            temperature=1.0
        )
        
        assert result.content == "Processed large payload successfully."
        assert result.usage["input_tokens"] == 37500
        assert result.usage["output_tokens"] == 10
        assert result.usage["total_tokens"] == 37510
        
        # Verify the request was made with correct URL and headers
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args[0][0]  # Get the request object
        assert call_args.full_url == "https://api.openai.com/v1/chat/completions"
        assert call_args.headers["Authorization"] == "Bearer test-key"
        assert call_args.headers["Content-type"] == "application/json"

    @patch('urllib.request.urlopen')
    def test_generate_content_http_error(self, mock_urlopen):
        """Test handling of HTTP errors."""
        provider = CustomOpenAI("test-key")
        
        # Mock HTTP error
        error_response = Mock()
        error_response.read.return_value = json.dumps({
            "error": {
                "message": "Invalid API key",
                "type": "invalid_request_error"
            }
        }).encode('utf-8')
        
        http_error = HTTPError(
            url="https://api.openai.com/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=error_response
        )
        mock_urlopen.side_effect = http_error
        
        with pytest.raises(RuntimeError, match="OpenAI API error 401"):
            provider.generate_content(
                prompt="Test prompt",
                model_name="o3-mini"
            )

    @patch('urllib.request.urlopen')
    def test_generate_content_url_error(self, mock_urlopen):
        """Test handling of URL/connection errors."""
        provider = CustomOpenAI("test-key")
        
        # Mock URL error
        mock_urlopen.side_effect = URLError("Connection failed")
        
        with pytest.raises(RuntimeError, match="Connection error"):
            provider.generate_content(
                prompt="Test prompt",
                model_name="o3-mini"
            )

    @patch('urllib.request.urlopen')
    def test_generate_content_json_error(self, mock_urlopen):
        """Test handling of JSON decode errors."""
        provider = CustomOpenAI("test-key")
        
        # Mock response with invalid JSON
        mock_response = Mock()
        mock_response.read.return_value = b"Invalid JSON response"
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response
        
        with pytest.raises(RuntimeError, match="Invalid JSON response"):
            provider.generate_content(
                prompt="Test prompt",
                model_name="o3-mini"
            )

    @patch('urllib.request.urlopen')
    def test_generate_content_timeout(self, mock_urlopen):
        """Test handling of timeout errors."""
        provider = CustomOpenAI("test-key")
        
        # Mock timeout
        mock_urlopen.side_effect = Exception("timeout")
        
        with pytest.raises(RuntimeError, match="Unexpected error"):
            provider.generate_content(
                prompt="Test prompt",
                model_name="o3-mini"
            )

    @patch('urllib.request.urlopen')
    def test_request_payload_structure(self, mock_urlopen):
        """Test that the request payload is structured correctly."""
        provider = CustomOpenAI("test-key")
        
        # Mock successful response
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Test response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
        }).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response
        
        provider.generate_content(
            prompt="Test prompt",
            model_name="o3-mini",
            system_prompt="You are a helpful assistant.",
            temperature=0.7,
            max_output_tokens=1000
        )
        
        # Get the request object
        request = mock_urlopen.call_args[0][0]
        
        # Parse the JSON payload
        payload = json.loads(request.data.decode('utf-8'))
        
        # Verify payload structure
        assert payload["model"] == "o3-mini"
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 1000
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][0]["content"] == "You are a helpful assistant."
        assert payload["messages"][1]["role"] == "user"
        assert payload["messages"][1]["content"] == "Test prompt"

    @patch('urllib.request.urlopen')
    def test_request_without_system_prompt(self, mock_urlopen):
        """Test request payload without system prompt."""
        provider = CustomOpenAI("test-key")
        
        # Mock successful response
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Test response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
        }).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response
        
        provider.generate_content(
            prompt="Test prompt",
            model_name="o3-mini",
            temperature=1.0
        )
        
        # Get the request object
        request = mock_urlopen.call_args[0][0]
        
        # Parse the JSON payload
        payload = json.loads(request.data.decode('utf-8'))
        
        # Verify payload structure (no system message)
        assert payload["model"] == "o3-mini"
        assert payload["temperature"] == 1.0
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"
        assert payload["messages"][0]["content"] == "Test prompt"

    def test_model_resolution(self):
        """Test model name resolution."""
        provider = CustomOpenAI("test-key")
        
        # Test that model resolution works correctly
        assert provider._resolve_model_name("o3-mini") == "o3-mini"
        # Since we only support o3-mini, other models should remain as-is
        assert provider._resolve_model_name("unsupported") == "unsupported"

    def test_supported_models_list(self):
        """Test that supported models are properly configured."""
        provider = CustomOpenAI("test-key")
        
        # Test that we have the expected model
        assert "o3-mini" in provider.SUPPORTED_MODELS
        assert len(provider.SUPPORTED_MODELS) == 1
        
        # Test model list
        models = provider.list_models()
        assert "o3-mini" in models