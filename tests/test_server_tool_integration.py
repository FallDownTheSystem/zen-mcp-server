"""Test server tool integration for test_custom_openai."""

import pytest
from unittest.mock import Mock, patch


class TestServerToolIntegration:
    """Test the server-level tool integration."""

    @patch('tools.test_custom_openai.TestCustomOpenAITool.execute')
    async def test_server_tool_returns_string(self, mock_execute):
        """Test that the server tool returns a string."""
        from server import test_custom_openai
        
        # Mock the tool execution to return a successful result
        mock_execute.return_value = [
            Mock(text='{"status": "success", "content": "Test response", "metadata": {"model": "o3-mini", "provider": "CustomOpenAI", "prompt_length": 150000, "response_length": 100, "response_time": 2.5, "tokens_used": {"total_tokens": 1000}}}')
        ]
        
        result = await test_custom_openai()
        
        # Verify result is a string
        assert isinstance(result, str)
        assert "CustomOpenAI Provider Test Results" in result
        assert "✅ SUCCESS" in result
        assert "Model: o3-mini" in result
        assert "Provider: CustomOpenAI" in result
        assert "150,000 characters" in result
        assert "2.50 seconds" in result
        assert "1000" in result

    @patch('tools.test_custom_openai.TestCustomOpenAITool.execute')
    async def test_server_tool_handles_error(self, mock_execute):
        """Test that the server tool handles errors correctly."""
        from server import test_custom_openai
        
        # Mock the tool execution to return an error result
        mock_execute.return_value = [
            Mock(text='{"status": "error", "content": "API key not found"}')
        ]
        
        result = await test_custom_openai()
        
        # Verify result is a string with error info
        assert isinstance(result, str)
        assert "CustomOpenAI Provider Test Results" in result
        assert "❌ ERROR" in result
        assert "API key not found" in result

    @patch('tools.test_custom_openai.TestCustomOpenAITool.execute')
    async def test_server_tool_handles_json_decode_error(self, mock_execute):
        """Test that the server tool handles JSON decode errors."""
        from server import test_custom_openai
        
        # Mock the tool execution to return invalid JSON
        mock_execute.return_value = [
            Mock(text='Invalid JSON response')
        ]
        
        result = await test_custom_openai()
        
        # Verify result is a string with error info
        assert isinstance(result, str)
        assert "Error: Failed to parse test result" in result
        assert "Invalid JSON response" in result

    @patch('tools.test_custom_openai.TestCustomOpenAITool.execute')
    async def test_server_tool_handles_no_result(self, mock_execute):
        """Test that the server tool handles empty results."""
        from server import test_custom_openai
        
        # Mock the tool execution to return no result
        mock_execute.return_value = []
        
        result = await test_custom_openai()
        
        # Verify result is a string with error info
        assert isinstance(result, str)
        assert "Error: No test result generated" in result

    @patch('tools.test_custom_openai.TestCustomOpenAITool.execute')
    async def test_server_tool_handles_exception(self, mock_execute):
        """Test that the server tool handles exceptions."""
        from server import test_custom_openai
        
        # Mock the tool execution to raise an exception
        mock_execute.side_effect = Exception("Test exception")
        
        result = await test_custom_openai()
        
        # Verify result is a string with error info
        assert isinstance(result, str)
        assert "Error: Test exception" in result