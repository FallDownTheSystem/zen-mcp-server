"""
Tests for the Consensus tool using WorkflowTool architecture.
"""

from unittest.mock import Mock

import pytest

from tools.consensus import ConsensusRequest, ConsensusTool
from tools.models import ToolModelCategory


class TestConsensusTool:
    """Test suite for ConsensusTool using WorkflowTool architecture."""

    def test_tool_metadata(self):
        """Test basic tool metadata and configuration."""
        tool = ConsensusTool()

        assert tool.get_name() == "consensus"
        assert "PARALLEL CONSENSUS WITH CROSS-MODEL FEEDBACK" in tool.get_description()
        assert tool.get_default_temperature() == 0.2  # TEMPERATURE_ANALYTICAL
        assert tool.get_model_category() == ToolModelCategory.EXTENDED_REASONING
        assert tool.requires_model() is False  # Consensus manages its own models

    def test_request_validation(self):
        """Test Pydantic request model validation for parallel consensus."""
        # Valid consensus request
        request = ConsensusRequest(
            step="Analyzing the real-time collaboration proposal",
            step_number=1,
            total_steps=1,  # Single-call execution
            next_step_required=False,
            findings="Initial assessment shows strong value but technical complexity",
            confidence="medium",
            models=[{"model": "flash", "stance": "neutral"}, {"model": "o3-mini", "stance": "for"}],
            relevant_files=["/proposal.md"],
            enable_cross_feedback=True,
        )

        assert request.step_number == 1
        assert request.total_steps == 1
        assert request.next_step_required is False
        assert len(request.models) == 2
        assert request.models[0]["model"] == "flash"
        assert request.enable_cross_feedback is True

    def test_request_validation_missing_models(self):
        """Test that consensus requires models field."""
        with pytest.raises(ValueError, match="Consensus requires 'models' field"):
            ConsensusRequest(
                step="Test step",
                step_number=1,
                total_steps=1,
                next_step_required=False,
                findings="Test findings",
                # Missing models field
            )

    def test_cross_feedback_disabled(self):
        """Test request with cross-feedback disabled."""
        request = ConsensusRequest(
            step="Quick consensus without refinement",
            step_number=1,
            total_steps=1,
            next_step_required=False,
            findings="Need fast consensus",
            models=[{"model": "flash"}, {"model": "o3-mini"}],
            enable_cross_feedback=False,  # Disable refinement phase
        )

        assert request.enable_cross_feedback is False
        assert request.cross_feedback_prompt is None

    def test_request_validation_duplicate_model_stance(self):
        """Test that duplicate model+stance combinations are rejected."""
        # Valid: same model with different stances
        valid_request = ConsensusRequest(
            step="Analyze this proposal",
            step_number=1,
            total_steps=1,
            next_step_required=False,
            findings="Initial analysis",
            models=[
                {"model": "o3", "stance": "for"},
                {"model": "o3", "stance": "against"},
                {"model": "flash", "stance": "neutral"},
            ],
            continuation_id="test-id",
        )
        assert len(valid_request.models) == 3

        # Invalid: duplicate model+stance combination
        with pytest.raises(ValueError, match="Duplicate model \\+ stance combination"):
            ConsensusRequest(
                step="Analyze this proposal",
                step_number=1,
                total_steps=1,
                next_step_required=False,
                findings="Initial analysis",
                models=[
                    {"model": "o3", "stance": "for"},
                    {"model": "flash", "stance": "neutral"},
                    {"model": "o3", "stance": "for"},  # Duplicate!
                ],
                continuation_id="test-id",
            )

    def test_custom_cross_feedback_prompt(self):
        """Test request with custom cross-feedback prompt."""
        custom_prompt = (
            "Based on the other models' insights, please revise your response focusing on technical feasibility."
        )

        request = ConsensusRequest(
            step="Evaluate technical architecture",
            step_number=1,
            total_steps=1,
            next_step_required=False,
            findings="Need consensus on architecture",
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

        # Verify consensus workflow fields are present
        assert "step" in schema["properties"]
        assert "step_number" in schema["properties"]
        assert "total_steps" in schema["properties"]
        assert "next_step_required" in schema["properties"]
        assert "findings" in schema["properties"]
        # confidence field should be excluded
        assert "confidence" not in schema["properties"]
        assert "models" in schema["properties"]
        # relevant_files should be present as it's used by consensus
        assert "relevant_files" in schema["properties"]

        # model field should be present for Gemini compatibility (consensus uses 'models' as well)
        assert "model" in schema["properties"]

        # Verify workflow fields that should NOT be present
        assert "files_checked" not in schema["properties"]
        assert "hypothesis" not in schema["properties"]
        assert "issues_found" not in schema["properties"]
        assert "temperature" not in schema["properties"]
        assert "thinking_mode" not in schema["properties"]
        assert "use_websearch" not in schema["properties"]

        # Images should be present now
        assert "images" in schema["properties"]
        assert schema["properties"]["images"]["type"] == "array"
        assert schema["properties"]["images"]["items"]["type"] == "string"

        # New cross-feedback fields should be present
        assert "enable_cross_feedback" in schema["properties"]
        assert schema["properties"]["enable_cross_feedback"]["type"] == "boolean"
        assert schema["properties"]["enable_cross_feedback"]["default"] is True

        assert "cross_feedback_prompt" in schema["properties"]
        assert schema["properties"]["cross_feedback_prompt"]["type"] == "string"

        # Verify field types
        assert schema["properties"]["step"]["type"] == "string"
        assert schema["properties"]["step_number"]["type"] == "integer"
        assert schema["properties"]["models"]["type"] == "array"

        # Verify models array structure
        models_items = schema["properties"]["models"]["items"]
        assert models_items["type"] == "object"
        assert "model" in models_items["properties"]
        assert "stance" in models_items["properties"]
        assert "stance_prompt" in models_items["properties"]

    def test_get_required_actions(self):
        """Test required actions for parallel consensus workflow."""
        tool = ConsensusTool()

        # For the new parallel workflow, get_required_actions always returns the same list
        # regardless of step number since everything happens in one call
        actions = tool.get_required_actions(1, "exploring", "Initial findings", 1)

        # Check that all expected actions are present
        assert any("consult all specified models in parallel" in action for action in actions)
        assert any("Models will receive the same prompt" in action for action in actions)
        assert any("cross-feedback is enabled" in action for action in actions)
        assert any("receive all responses" in action for action in actions)
        assert any("single result" in action for action in actions)

    def test_prepare_step_data(self):
        """Test step data preparation for consensus workflow."""
        tool = ConsensusTool()
        request = ConsensusRequest(
            step="Test step",
            step_number=1,
            total_steps=3,
            next_step_required=True,
            findings="Test findings",
            confidence="medium",
            models=[{"model": "test"}],
            relevant_files=["/test.py"],
        )

        step_data = tool.prepare_step_data(request)

        # Verify consensus-specific fields
        assert step_data["step"] == "Test step"
        assert step_data["findings"] == "Test findings"
        assert step_data["relevant_files"] == ["/test.py"]

        # Verify unused workflow fields are empty
        assert step_data["files_checked"] == []
        assert step_data["relevant_context"] == []
        assert step_data["issues_found"] == []
        assert step_data["hypothesis"] is None

    def test_stance_enhanced_prompt_generation(self):
        """Test stance-enhanced prompt generation."""
        tool = ConsensusTool()

        # Test different stances
        for_prompt = tool._get_stance_enhanced_prompt("for")
        assert "SUPPORTIVE PERSPECTIVE" in for_prompt

        against_prompt = tool._get_stance_enhanced_prompt("against")
        assert "CRITICAL PERSPECTIVE" in against_prompt

        neutral_prompt = tool._get_stance_enhanced_prompt("neutral")
        assert "BALANCED PERSPECTIVE" in neutral_prompt

        # Test custom stance prompt
        custom = "Focus on specific aspects"
        custom_prompt = tool._get_stance_enhanced_prompt("for", custom)
        assert custom in custom_prompt
        assert "SUPPORTIVE PERSPECTIVE" not in custom_prompt

    def test_should_call_expert_analysis(self):
        """Test that consensus workflow doesn't use expert analysis."""
        tool = ConsensusTool()
        assert tool.should_call_expert_analysis({}) is False
        assert tool.requires_expert_analysis() is False

    def test_execute_workflow_step1_basic(self):
        """Test basic workflow validation for step 1."""
        tool = ConsensusTool()

        # Test that step 1 sets up the workflow correctly
        arguments = {
            "step": "Initial analysis of proposal",
            "step_number": 1,
            "total_steps": 2,
            "next_step_required": True,
            "findings": "Found pros and cons",
            "models": [{"model": "flash", "stance": "neutral"}, {"model": "o3-mini", "stance": "for"}],
        }

        # Verify models_to_consult is set correctly from step 1
        request = tool.get_workflow_request_model()(**arguments)
        assert len(request.models) == 2
        assert request.models[0]["model"] == "flash"
        assert request.models[1]["model"] == "o3-mini"

    def test_execute_workflow_total_steps_calculation(self):
        """Test that total_steps is calculated correctly from models."""
        tool = ConsensusTool()

        # Test with 2 models
        arguments = {
            "step": "Initial analysis",
            "step_number": 1,
            "total_steps": 4,  # This should be corrected to 2
            "next_step_required": True,
            "findings": "Analysis complete",
            "models": [{"model": "flash", "stance": "neutral"}, {"model": "o3-mini", "stance": "for"}],
        }

        request = tool.get_workflow_request_model()(**arguments)
        # The tool should set total_steps = len(models) = 2
        assert len(request.models) == 2

    def test_consult_model_basic_structure(self):
        """Test basic model consultation structure."""
        tool = ConsensusTool()

        # Test that _get_stance_enhanced_prompt works
        for_prompt = tool._get_stance_enhanced_prompt("for")
        against_prompt = tool._get_stance_enhanced_prompt("against")
        neutral_prompt = tool._get_stance_enhanced_prompt("neutral")

        assert "SUPPORTIVE PERSPECTIVE" in for_prompt
        assert "CRITICAL PERSPECTIVE" in against_prompt
        assert "BALANCED PERSPECTIVE" in neutral_prompt

    def test_model_configuration_validation(self):
        """Test model configuration validation."""
        tool = ConsensusTool()

        # Test single model config
        models = [{"model": "flash", "stance": "neutral"}]
        arguments = {
            "step": "Test",
            "step_number": 1,
            "total_steps": 1,
            "next_step_required": False,
            "findings": "Test findings",
            "models": models,
        }

        request = tool.get_workflow_request_model()(**arguments)
        assert len(request.models) == 1
        assert request.models[0]["model"] == "flash"
        assert request.models[0]["stance"] == "neutral"

    def test_handle_work_continuation(self):
        """Test work continuation handling - legacy method for parallel workflow."""
        tool = ConsensusTool()
        tool.models_to_consult = [{"model": "flash", "stance": "neutral"}, {"model": "o3-mini", "stance": "for"}]

        # In the new parallel workflow, this method is not used and simply returns
        # the response_data unchanged
        request = Mock(step_number=1, current_model_index=0)
        response_data = {"test": "data"}

        result = tool.handle_work_continuation(response_data, request)
        # The method returns response_data unchanged in the new workflow
        assert result == response_data

        # Test with different data
        response_data2 = {"other": "info", "status": "existing"}
        result2 = tool.handle_work_continuation(response_data2, request)
        assert result2 == response_data2

    def test_customize_workflow_response(self):
        """Test response customization for consensus workflow."""
        tool = ConsensusTool()
        tool.accumulated_responses = [{"model": "test", "response": "data"}]

        # Test different step numbers (new workflow: 2 models = 2 steps)
        request = Mock(step_number=1, total_steps=2)
        response_data = {}
        result = tool.customize_workflow_response(response_data, request)
        assert result["consensus_workflow_status"] == "initial_analysis_complete"

        request = Mock(step_number=2, total_steps=2)
        response_data = {}
        result = tool.customize_workflow_response(response_data, request)
        assert result["consensus_workflow_status"] == "ready_for_synthesis"


if __name__ == "__main__":
    import unittest

    unittest.main()
