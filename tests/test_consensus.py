"""Tests for the consensus tool."""

import pytest

from tools.consensus import ConsensusRequest, ConsensusTool


class TestConsensusTool:
    """Test suite for consensus tool functionality."""

    def test_tool_metadata(self):
        """Test basic tool metadata."""
        tool = ConsensusTool()
        assert tool.get_name() == "consensus"
        assert "PARALLEL CONSENSUS" in tool.get_description()
        assert "multiple AI models" in tool.get_description()

    def test_request_validation(self):
        """Test Pydantic request model validation for parallel consensus."""
        # Valid consensus request
        request = ConsensusRequest(
            prompt="Analyzing the real-time collaboration proposal",
            models=[{"model": "flash"}, {"model": "o3-mini"}],
            relevant_files=["/proposal.md"],
            enable_cross_feedback=True,
        )

        assert len(request.models) == 2
        assert request.models[0]["model"] == "flash"
        assert request.enable_cross_feedback is True

    def test_request_validation_missing_models(self):
        """Test that consensus requires models field."""
        with pytest.raises(ValueError, match="Consensus requires at least one model"):
            ConsensusRequest(
                prompt="Test prompt",
                models=[],  # Empty models list
            )

    def test_cross_feedback_disabled(self):
        """Test request with cross-feedback disabled."""
        request = ConsensusRequest(
            prompt="Quick consensus without refinement",
            models=[{"model": "flash"}, {"model": "o3-mini"}],
            enable_cross_feedback=False,  # Disable refinement phase
        )

        assert request.enable_cross_feedback is False
        assert request.cross_feedback_prompt is None

    def test_custom_cross_feedback_prompt(self):
        """Test request with custom cross-feedback prompt."""
        custom_prompt = (
            "Based on the other models' insights, please revise your response focusing on technical feasibility."
        )

        request = ConsensusRequest(
            prompt="Evaluate technical architecture",
            models=[{"model": "gemini-pro"}, {"model": "o3"}],
            enable_cross_feedback=True,
            cross_feedback_prompt=custom_prompt,
        )

        assert request.enable_cross_feedback is True
        assert request.cross_feedback_prompt == custom_prompt

    def test_input_schema_generation(self):
        """Test that input schema is generated correctly."""
        tool = ConsensusTool()
        schema = tool.get_input_schema()

        # Verify consensus fields are present
        assert "prompt" in schema["properties"]
        assert "models" in schema["properties"]
        assert "relevant_files" in schema["properties"]
        assert "images" in schema["properties"]
        assert "enable_cross_feedback" in schema["properties"]
        assert "cross_feedback_prompt" in schema["properties"]
        assert "continuation_id" in schema["properties"]

        # Step-based fields should not be present
        assert "step" not in schema["properties"]
        assert "step_number" not in schema["properties"]
        assert "total_steps" not in schema["properties"]
        assert "next_step_required" not in schema["properties"]
        assert "findings" not in schema["properties"]
        assert "confidence" not in schema["properties"]

        # Verify field types
        assert schema["properties"]["prompt"]["type"] == "string"
        assert schema["properties"]["models"]["type"] == "array"

        # Verify models array structure
        models_items = schema["properties"]["models"]["items"]
        assert models_items["type"] == "object"
        assert "model" in models_items["properties"]

    def test_schema_required_fields(self):
        """Test that schema has correct required fields."""
        tool = ConsensusTool()
        schema = tool.get_input_schema()

        assert "required" in schema
        assert "prompt" in schema["required"]
        assert "models" in schema["required"]

    def test_tool_does_not_require_model(self):
        """Test that consensus tool doesn't require model at MCP boundary."""
        tool = ConsensusTool()
        assert tool.requires_model() is False

    def test_default_temperature(self):
        """Test that consensus uses analytical temperature."""
        tool = ConsensusTool()
        assert tool.get_default_temperature() == 0.2

    def test_model_category(self):
        """Test that consensus requires extended reasoning models."""
        tool = ConsensusTool()
        from tools.models import ToolModelCategory

        assert tool.get_model_category() == ToolModelCategory.EXTENDED_REASONING

    def test_build_cross_feedback_prompt(self):
        """Test cross-feedback prompt building."""
        tool = ConsensusTool()
        tool.initial_prompt = "What is the best approach?"

        initial_response = {"model": "flash", "response": "I think approach A is best because..."}

        other_responses = [{"model": "o3", "response": "Approach B might be better..."}]

        # Test default prompt
        prompt = tool._build_cross_feedback_prompt(initial_response, other_responses)
        assert "What is the best approach?" in prompt
        assert "I think approach A is best" in prompt
        assert "Approach B might be better" in prompt
        assert "OTHER APPROACHES" in prompt

        # Test custom prompt
        custom = "Custom refinement instructions"
        prompt = tool._build_cross_feedback_prompt(initial_response, other_responses, custom)
        assert prompt == custom

    def test_get_tool_fields(self):
        """Test that tool fields are properly defined."""
        tool = ConsensusTool()
        fields = tool.get_tool_fields()

        assert "prompt" in fields
        assert "models" in fields
        assert "relevant_files" in fields
        assert "images" in fields
        assert "enable_cross_feedback" in fields
        assert "cross_feedback_prompt" in fields

        # Check field types
        assert fields["prompt"]["type"] == "string"
        assert fields["models"]["type"] == "array"
        assert fields["enable_cross_feedback"]["type"] == "boolean"
        assert fields["enable_cross_feedback"]["default"] is True

    def test_get_required_fields(self):
        """Test that required fields are correctly specified."""
        tool = ConsensusTool()
        required = tool.get_required_fields()

        assert "prompt" in required
        assert "models" in required
        assert len(required) == 2
