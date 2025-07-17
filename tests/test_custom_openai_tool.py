"""Tests for TestCustomOpenAI tool implementation."""

import json
import os
from unittest.mock import Mock, patch

import pytest

from providers.custom_openai import CustomOpenAI
from tools.test_custom_openai import TestCustomOpenAITool


class TestCustomOpenAIToolTests:
    """Test the TestCustomOpenAI tool functionality."""

    def test_initialization(self):
        """Test tool initialization."""
        tool = TestCustomOpenAITool()
        assert tool.get_name() == "test_custom_openai"
        assert "CustomOpenAI provider" in tool.get_description()
        assert tool.get_tool_fields() == {}  # No parameters needed
        assert tool.get_required_fields() == []  # No required fields
        assert tool.supports_auto_mode() is False
        assert tool.is_effective_auto_mode() is False

    def test_model_field_schema(self):
        """Test model field schema is fixed to o3-mini."""
        tool = TestCustomOpenAITool()
        schema = tool.get_model_field_schema()
        
        assert schema["type"] == "string"
        assert schema["enum"] == ["o3-mini"]
        assert schema["default"] == "o3-mini"
        assert "o3-mini" in schema["description"]

    async def test_prepare_prompt_generates_large_payload(self):
        """Test that prepare_prompt generates ~150k characters."""
        tool = TestCustomOpenAITool()
        
        prompt = await tool.prepare_prompt(None)
        
        # Should be approximately 150k characters
        assert len(prompt) >= 149000  # Allow some tolerance
        assert len(prompt) <= 151000  # But not too much more
        
        # Should contain repetitive content
        assert "This is a test message" in prompt
        assert "Keep your response brief" in prompt

    def test_system_prompt(self):
        """Test system prompt."""
        tool = TestCustomOpenAITool()
        
        system_prompt = tool.get_system_prompt()
        assert "test assistant" in system_prompt.lower()
        assert "repetitive content" in system_prompt
        assert "brief" in system_prompt

    def test_format_response(self):
        """Test response formatting."""
        tool = TestCustomOpenAITool()
        
        # Set up a mock last prompt
        tool._last_prompt = "A" * 150000
        
        response = "Test response from o3-mini"
        formatted = tool.format_response(response, None, {
            "response_time": 2.5,
            "provider": "CustomOpenAI",
            "model_name": "o3-mini"
        })
        
        assert "CustomOpenAI Test Results" in formatted
        assert "Model: o3-mini" in formatted
        assert "150,000 characters" in formatted
        assert "Test response from o3-mini" in formatted
        assert "Successfully processed large payload" in formatted

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch('urllib.request.urlopen')
    async def test_execute_success(self, mock_urlopen):
        """Test successful tool execution."""
        tool = TestCustomOpenAITool()
        
        # Mock successful API response
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "I received your large message with repetitive content."}}],
            "usage": {
                "prompt_tokens": 37500,
                "completion_tokens": 12,
                "total_tokens": 37512
            }
        }).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response
        
        # Execute the tool
        result = await tool.execute({})
        
        # Parse the result
        assert len(result) == 1
        result_data = json.loads(result[0].text)
        
        assert result_data["status"] == "success"
        assert "CustomOpenAI Test Results" in result_data["content"]
        assert result_data["metadata"]["provider"] == "CustomOpenAI"
        assert result_data["metadata"]["model"] == "o3-mini"
        assert result_data["metadata"]["prompt_length"] >= 149000
        assert result_data["metadata"]["response_time"] >= 0
        assert result_data["metadata"]["tokens_used"]["total_tokens"] == 37512

    @patch.dict(os.environ, {}, clear=True)
    async def test_execute_missing_api_key(self):
        """Test execution with missing API key."""
        tool = TestCustomOpenAITool()
        
        # Execute without API key
        result = await tool.execute({})
        
        # Parse the result
        assert len(result) == 1
        result_data = json.loads(result[0].text)
        
        assert result_data["status"] == "error"
        assert "OPENAI_API_KEY environment variable not set" in result_data["content"]

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch('urllib.request.urlopen')
    async def test_execute_api_error(self, mock_urlopen):
        """Test execution with API error."""
        tool = TestCustomOpenAITool()
        
        # Mock API error
        from urllib.error import HTTPError
        error_response = Mock()
        error_response.read.return_value = json.dumps({
            "error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}
        }).encode('utf-8')
        
        http_error = HTTPError(
            url="https://api.openai.com/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=error_response
        )
        mock_urlopen.side_effect = http_error
        
        # Execute the tool
        result = await tool.execute({})
        
        # Parse the result
        assert len(result) == 1
        result_data = json.loads(result[0].text)
        
        assert result_data["status"] == "error"
        assert "CustomOpenAI provider failed" in result_data["content"]
        assert result_data["metadata"]["prompt_length"] >= 149000
        assert result_data["metadata"]["error_type"] == "RuntimeError"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch('urllib.request.urlopen')
    async def test_execute_measures_response_time(self, mock_urlopen):
        """Test that execution measures response time."""
        tool = TestCustomOpenAITool()
        
        # Mock successful API response with delay
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}
        }).encode('utf-8')
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response
        
        # Execute the tool
        result = await tool.execute({})
        
        # Parse the result
        result_data = json.loads(result[0].text)
        
        assert result_data["status"] == "success"
        assert "response_time" in result_data["metadata"]
        assert result_data["metadata"]["response_time"] >= 0

    async def test_large_payload_size_verification(self):
        """Test that the tool generates exactly the right payload size."""
        tool = TestCustomOpenAITool()
        
        # Generate multiple prompts and verify they're all around 150k
        for _ in range(3):
            prompt = await tool.prepare_prompt(None)
            
            # Should be very close to 150k (within 1k tolerance)
            assert abs(len(prompt) - 150000) < 1000, f"Prompt length {len(prompt)} is not close to 150k"
            
            # Should contain the expected structure
            assert prompt.count("This is a test message") > 1000  # Lots of repetitions
            assert "Given the above repetitive text" in prompt
            assert "Keep your response brief" in prompt

    def test_tool_annotations(self):
        """Test tool annotations."""
        tool = TestCustomOpenAITool()
        
        annotations = tool.get_annotations()
        assert annotations["readOnlyHint"] is True  # Should be read-only

    def test_tool_schema_generation(self):
        """Test that tool generates proper schema."""
        tool = TestCustomOpenAITool()
        
        schema = tool.get_input_schema()
        
        # Should have model field fixed to o3-mini
        assert "model" in schema["properties"]
        assert schema["properties"]["model"]["enum"] == ["o3-mini"]
        assert schema["properties"]["model"]["default"] == "o3-mini"
        
        # Should have no other required fields
        assert "required" not in schema or len(schema.get("required", [])) == 0