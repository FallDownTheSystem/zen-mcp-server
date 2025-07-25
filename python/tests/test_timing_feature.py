"""
Test for the model response timing feature.

This test verifies that the SimpleTool base class correctly adds timing
information to model responses.
"""

from unittest.mock import MagicMock, patch

import pytest

from tools.chat import ChatTool


class TestTimingFeature:
    """Test that model response timing is correctly added"""

    @pytest.mark.asyncio
    async def test_timing_info_added_to_successful_response(self):
        """Test that timing information is appended to successful model responses"""

        # Create a ChatTool instance
        tool = ChatTool()

        # Mock the model response
        mock_response = MagicMock()
        mock_response.content = "This is a test response from the model."
        mock_response.usage = {"input_tokens": 50, "output_tokens": 20}
        mock_response.metadata = {"finish_reason": "stop"}

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.generate_content.return_value = mock_response
        mock_provider.get_provider_type.return_value.value = "test"
        mock_provider.supports_thinking_mode.return_value = False

        # Mock model context
        mock_model_context = MagicMock()
        mock_model_context.model_name = "test-model"
        mock_model_context.provider = mock_provider
        mock_model_context.capabilities.temperature_constraint.validate.return_value = True

        # Create arguments
        arguments = {
            "prompt": "Test prompt",
            "model": "test-model",
            "_model_context": mock_model_context,
            "_resolved_model_name": "test-model",
        }

        # Execute the tool
        with patch.object(tool, "_resolve_model_context", return_value=("test-model", mock_model_context)):
            result = await tool.execute(arguments)

        # Parse the result
        import json

        result_data = json.loads(result[0].text)

        # Verify the response contains timing information in metadata
        assert result_data["status"] in ["success", "continuation_available"]
        assert "metadata" in result_data
        assert "response_time" in result_data["metadata"]
        assert isinstance(result_data["metadata"]["response_time"], (int, float))
        # Content should NOT contain timing info
        assert "test-model took" not in result_data["content"]
        assert "seconds to respond" not in result_data["content"]

    @pytest.mark.asyncio
    async def test_timing_info_added_to_error_response(self):
        """Test that timing information is included even in error responses"""

        tool = ChatTool()

        # Mock a failed model response
        mock_response = MagicMock()
        mock_response.content = None  # No content indicates failure
        mock_response.metadata = {"finish_reason": "blocked"}

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.generate_content.return_value = mock_response
        mock_provider.get_provider_type.return_value.value = "test"
        mock_provider.supports_thinking_mode.return_value = False

        # Mock model context
        mock_model_context = MagicMock()
        mock_model_context.model_name = "test-model"
        mock_model_context.provider = mock_provider
        mock_model_context.capabilities.temperature_constraint.validate.return_value = True

        # Create arguments
        arguments = {
            "prompt": "Test prompt",
            "model": "test-model",
            "_model_context": mock_model_context,
            "_resolved_model_name": "test-model",
        }

        # Execute the tool
        with patch.object(tool, "_resolve_model_context", return_value=("test-model", mock_model_context)):
            result = await tool.execute(arguments)

        # Parse the result
        import json

        result_data = json.loads(result[0].text)

        # Verify error response contains timing information in metadata
        assert result_data["status"] == "error"
        assert "metadata" in result_data
        assert "response_time" in result_data["metadata"]
        assert isinstance(result_data["metadata"]["response_time"], (int, float))
        # Content should NOT contain timing info
        assert "test-model took" not in result_data["content"]
        assert "seconds to respond" not in result_data["content"]

    def test_format_response_metadata_timing(self):
        """Test that timing information is added to metadata, not content"""

        tool = ChatTool()

        # Create model info with timing
        model_info = {"model_name": "gemini-pro", "response_time": 2.345, "provider": "google"}

        # Call _parse_response directly
        raw_text = "This is the model's response"
        request = MagicMock()
        request.continuation_id = None

        # Mock format_response to return the raw text
        with patch.object(tool, "format_response", return_value=raw_text):
            with patch.object(tool, "_create_continuation_offer", return_value=None):
                result = tool._parse_response(raw_text, request, model_info)

        # Verify timing is in metadata, not content
        assert result.content == raw_text  # Content should be unmodified
        assert result.metadata is not None
        assert result.metadata.get("response_time") == 2.345
