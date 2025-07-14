"""Test o3-pro response handling."""

import os
import pytest
from unittest.mock import Mock, MagicMock, patch

from providers.openai_provider import OpenAIModelProvider
from providers.base import ProviderType


@pytest.mark.integration
class TestO3ProResponse:
    """Test o3-pro model response handling."""

    @patch("providers.openai_compatible.OpenAI")
    def test_o3_pro_response_format_mock(self, mock_openai_class):
        """Test that o3-pro uses correct request format (mocked)."""
        # Set up mock OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Mock the responses endpoint
        mock_response = Mock()
        mock_response.output_text = "Test response from o3-pro"
        mock_response.usage = None
        mock_response.input_tokens = 10
        mock_response.output_tokens = 5
        mock_client.responses.create.return_value = mock_response
        
        provider = OpenAIModelProvider("test-key")
        
        response = provider.generate_content(
            prompt="Test user message",
            model_name="o3-pro",
            temperature=0.5,
            max_output_tokens=100,
            system_prompt="Test system message"
        )
        
        # Verify the correct endpoint was called
        mock_client.responses.create.assert_called_once()
        
        # Verify the request format
        call_args = mock_client.responses.create.call_args[1]
        assert call_args["model"] == "o3-pro-2025-06-10"
        assert call_args["input"] == "Test user message"
        assert call_args["instructions"] == "Test system message"
        assert call_args["reasoning"] == {"effort": "high"}
        assert call_args["max_completion_tokens"] == 100
        
        # Verify response extraction
        assert response.content == "Test response from o3-pro"
        assert response.model_name == "o3-pro-2025-06-10"  # Returns resolved name
        assert response.provider == ProviderType.OPENAI

    @patch("providers.openai_compatible.OpenAI")
    def test_o3_pro_response_extraction_formats(self, mock_openai_class):
        """Test different response formats for o3-pro."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        provider = OpenAIModelProvider("test-key")
        
        # Test 1: Direct output_text field (expected format)
        mock_response = Mock()
        mock_response.output_text = "Direct output text"
        mock_response.usage = None
        mock_response.input_tokens = 5
        mock_response.output_tokens = 3
        mock_client.responses.create.return_value = mock_response
        
        response = provider.generate_content(prompt="Test", model_name="o3-pro")
        assert response.content == "Direct output text"
        
        # Test 2: Nested output.text field
        mock_response2 = Mock()
        mock_response2.output_text = None
        mock_response2.output = Mock()
        mock_response2.output.text = "Nested output text"
        mock_response2.usage = None
        mock_client.responses.create.return_value = mock_response2
        
        response2 = provider.generate_content(prompt="Test", model_name="o3-pro")
        assert response2.content == "Nested output text"
        
        # Test 3: Content array format
        mock_response3 = Mock()
        mock_response3.output_text = None
        mock_response3.output = Mock()
        mock_response3.output.text = None
        mock_content_item = Mock()
        mock_content_item.type = "output_text"
        mock_content_item.text = "Content array text"
        mock_response3.output.content = [mock_content_item]
        mock_response3.usage = None
        mock_client.responses.create.return_value = mock_response3
        
        response3 = provider.generate_content(prompt="Test", model_name="o3-pro")
        assert response3.content == "Content array text"

    @patch("providers.openai_compatible.OpenAI")
    def test_o3_pro_with_system_prompt(self, mock_openai_class):
        """Test o3-pro with system prompt."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.output_text = "Response with system prompt"
        mock_response.usage = None
        mock_client.responses.create.return_value = mock_response
        
        provider = OpenAIModelProvider("test-key")
        
        response = provider.generate_content(
            prompt="How are you?",
            model_name="o3-pro",
            system_prompt="You are a helpful assistant",
            temperature=0.7
        )
        
        # Check that the request was formatted correctly
        call_args = mock_client.responses.create.call_args[1]
        assert call_args["instructions"] == "You are a helpful assistant"
        assert call_args["input"] == "How are you?"

    def test_o3_pro_simple_ack_integration(self):
        """Test that o3-pro can handle a simple ACK message (real API call)."""
        # Skip if no OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")
        
        provider = OpenAIModelProvider(os.getenv("OPENAI_API_KEY"))
        
        # This should complete without timing out
        response = provider.generate_content(
            prompt="Reply with just 'ACK' to confirm you received this.",
            model_name="o3-pro",
            temperature=0.1,
            max_output_tokens=50
        )
        
        assert response is not None
        assert response.content is not None
        assert len(response.content) > 0
        assert response.model_name == "o3-pro-2025-06-10"  # Returns resolved name
        print(f"o3-pro response: {response.content}")

    def test_o3_pro_with_system_message_integration(self):
        """Test that o3-pro handles system messages correctly (real API call)."""
        # Skip if no OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")
        
        provider = OpenAIModelProvider(os.getenv("OPENAI_API_KEY"))
        
        response = provider.generate_content(
            prompt="Say 'Hello' to confirm you received this.",
            model_name="o3-pro",
            system_prompt="You are a helpful assistant. Always respond concisely.",
            temperature=0.1,
            max_output_tokens=50
        )
        
        assert response is not None
        assert response.content is not None
        assert "hello" in response.content.lower() or "Hello" in response.content
        print(f"o3-pro response with system: {response.content}")