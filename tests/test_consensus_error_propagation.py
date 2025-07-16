"""Test error propagation in the consensus tool."""

import asyncio
import unittest
from unittest.mock import MagicMock, Mock, patch

import pytest

from providers.base import ModelProvider, ModelResponse, ProviderType


class TestConsensusErrorPropagation(unittest.TestCase):
    """Test that errors are propagated immediately without waiting for timeouts."""

    def setUp(self):
        """Set up test fixtures."""
        from tools.consensus import ConsensusTool

        self.tool = ConsensusTool()

    @pytest.mark.asyncio
    async def test_immediate_error_propagation_no_retry(self):
        """Test that provider errors are returned immediately without retry."""
        # Create an error that should not be retried
        error = RuntimeError("Model not available: insufficient quota")

        # Mock provider that raises error immediately
        mock_provider = Mock(spec=ModelProvider)
        mock_provider.generate_content.side_effect = error
        mock_provider.get_provider_type.return_value = ProviderType.OPENAI

        self.tool.models_to_consult = [{"model": "gpt-4"}]

        with patch.object(self.tool, "get_model_provider", return_value=mock_provider):
            # Mock phase timeout to be long (should not be reached)
            with patch.object(self.tool, "_get_phase_timeout", return_value=300.0):  # 5 minutes

                request = MagicMock()
                request.prompt = "Test prompt"
                request.models = self.tool.models_to_consult
                request.enable_cross_feedback = False
                request.relevant_files = []
                request.images = None
                request.temperature = 0.7
                request.continuation_id = None
                request.reasoning_effort = "medium"

                with patch.object(self.tool, "get_request_model", return_value=lambda **kwargs: request):
                    # Track timing
                    import time

                    start_time = time.time()

                    result = await self.tool.execute(
                        {"prompt": "Test prompt", "models": self.tool.models_to_consult, "enable_cross_feedback": False}
                    )

                    end_time = time.time()
                    elapsed = end_time - start_time

                    # Should return quickly (within 1 second), not wait for timeout
                    self.assertLess(elapsed, 1.0, "Error should be returned immediately")

                    # Parse response
                    import json

                    response_data = json.loads(result[0].text)

                    # Should have failed model with the original error
                    self.assertEqual(len(response_data["failed_models"]), 1)
                    self.assertIn("insufficient quota", response_data["failed_models"][0]["error"])

    @pytest.mark.asyncio
    async def test_mixed_success_and_error_responses(self):
        """Test handling of mixed successful and error responses."""
        # Set up multiple models
        self.tool.models_to_consult = [{"model": "gpt-4"}, {"model": "claude-3"}, {"model": "gemini-pro"}]

        # Create different responses
        success_response = ModelResponse(
            content="Successful response", usage={"input_tokens": 10, "output_tokens": 20}, model_name="gpt-4"
        )

        # Mock providers with different behaviors
        mock_providers = {
            "gpt-4": Mock(spec=ModelProvider),
            "claude-3": Mock(spec=ModelProvider),
            "gemini-pro": Mock(spec=ModelProvider),
        }

        # GPT-4 succeeds
        mock_providers["gpt-4"].generate_content.return_value = success_response
        mock_providers["gpt-4"].get_provider_type.return_value = ProviderType.OPENAI

        # Claude fails with API error
        mock_providers["claude-3"].generate_content.side_effect = RuntimeError("API key invalid")
        mock_providers["claude-3"].get_provider_type.return_value = ProviderType.OPENAI

        # Gemini succeeds
        gemini_response = ModelResponse(
            content="Gemini response", usage={"input_tokens": 15, "output_tokens": 25}, model_name="gemini-pro"
        )
        mock_providers["gemini-pro"].generate_content.return_value = gemini_response
        mock_providers["gemini-pro"].get_provider_type.return_value = ProviderType.GOOGLE

        def get_provider(model_name):
            return mock_providers.get(model_name)

        with patch.object(self.tool, "get_model_provider", side_effect=get_provider):
            with patch.object(self.tool, "_get_phase_timeout", return_value=10.0):

                request = MagicMock()
                request.prompt = "Test prompt"
                request.models = self.tool.models_to_consult
                request.enable_cross_feedback = False
                request.relevant_files = []
                request.images = None
                request.temperature = 0.7
                request.continuation_id = None
                request.reasoning_effort = "medium"

                with patch.object(self.tool, "get_request_model", return_value=lambda **kwargs: request):
                    result = await self.tool.execute(
                        {"prompt": "Test prompt", "models": self.tool.models_to_consult, "enable_cross_feedback": False}
                    )

                    import json

                    response_data = json.loads(result[0].text)

                    # Should have 2 successful responses
                    self.assertEqual(response_data["successful_responses"], 2)
                    # Should have 1 failed model
                    self.assertEqual(len(response_data["failed_models"]), 1)
                    self.assertEqual(response_data["failed_models"][0]["model"], "claude-3")
                    self.assertIn("API key invalid", response_data["failed_models"][0]["error"])

    @pytest.mark.asyncio
    async def test_all_models_fail_quickly(self):
        """Test that consensus completes quickly when all models fail."""
        self.tool.models_to_consult = [{"model": "model1"}, {"model": "model2"}, {"model": "model3"}]

        # All providers fail immediately
        mock_provider = Mock(spec=ModelProvider)
        mock_provider.generate_content.side_effect = RuntimeError("Service unavailable")
        mock_provider.get_provider_type.return_value = ProviderType.OPENAI

        with patch.object(self.tool, "get_model_provider", return_value=mock_provider):
            with patch.object(self.tool, "_get_phase_timeout", return_value=300.0):  # 5 minutes

                request = MagicMock()
                request.prompt = "Test prompt"
                request.models = self.tool.models_to_consult
                request.enable_cross_feedback = False
                request.relevant_files = []
                request.images = None
                request.temperature = 0.7
                request.continuation_id = None
                request.reasoning_effort = "medium"

                with patch.object(self.tool, "get_request_model", return_value=lambda **kwargs: request):
                    import time

                    start_time = time.time()

                    result = await self.tool.execute(
                        {"prompt": "Test prompt", "models": self.tool.models_to_consult, "enable_cross_feedback": False}
                    )

                    end_time = time.time()
                    elapsed = end_time - start_time

                    # Should complete within 1 second despite 5 minute timeout
                    self.assertLess(elapsed, 1.0)

                    import json

                    response_data = json.loads(result[0].text)

                    # All models should have failed
                    self.assertEqual(response_data["successful_responses"], 0)
                    self.assertEqual(len(response_data["failed_models"]), 3)

    @pytest.mark.asyncio
    async def test_error_ordering_preserved(self):
        """Test that model order is preserved even with errors."""
        self.tool.models_to_consult = [
            {"model": "model1"},
            {"model": "model2"},
            {"model": "model3"},
            {"model": "model4"},
        ]

        # Create mixed responses with specific timing
        async def model1_response(*args, **kwargs):
            await asyncio.sleep(0.1)
            return {
                "model": "model1",
                "status": "success",
                "phase": "initial",
                "response": "Response 1",
                "metadata": {"response_time": 0.1},
            }

        async def model2_error(*args, **kwargs):
            # Fail immediately
            raise RuntimeError("Model 2 error")

        async def model3_response(*args, **kwargs):
            await asyncio.sleep(0.05)
            return {
                "model": "model3",
                "status": "success",
                "phase": "initial",
                "response": "Response 3",
                "metadata": {"response_time": 0.05},
            }

        async def model4_timeout(*args, **kwargs):
            # This will timeout
            await asyncio.sleep(10.0)

        with patch.object(
            self.tool,
            "_consult_model",
            side_effect=[model1_response(), model2_error(), model3_response(), model4_timeout()],
        ):
            with patch.object(self.tool, "_get_phase_timeout", return_value=0.5):

                request = MagicMock()
                request.prompt = "Test"
                request.models = self.tool.models_to_consult
                request.enable_cross_feedback = False
                request.relevant_files = []
                request.images = None
                request.temperature = 0.7
                request.continuation_id = None

                with patch.object(self.tool, "get_request_model", return_value=lambda **kwargs: request):
                    result = await self.tool.execute(
                        {"prompt": "Test", "models": self.tool.models_to_consult, "enable_cross_feedback": False}
                    )

                    import json

                    response_data = json.loads(result[0].text)

                    # Check responses are in order
                    self.assertEqual(len(response_data["responses"]), 2)
                    self.assertEqual(response_data["responses"][0]["model"], "model1")
                    self.assertEqual(response_data["responses"][1]["model"], "model3")

                    # Check failed models
                    self.assertEqual(len(response_data["failed_models"]), 2)
                    failed_models = {fm["model"]: fm for fm in response_data["failed_models"]}
                    self.assertIn("model2", failed_models)
                    self.assertIn("model4", failed_models)
                    self.assertIn("Model 2 error", failed_models["model2"]["error"])
                    self.assertIn("timeout", failed_models["model4"]["error"].lower())


class TestErrorPropagationInRefinement(unittest.TestCase):
    """Test error propagation in the refinement phase."""

    def setUp(self):
        """Set up test fixtures."""
        from tools.consensus import ConsensusTool

        self.tool = ConsensusTool()

    @pytest.mark.asyncio
    async def test_refinement_error_does_not_affect_initial(self):
        """Test that refinement errors don't affect initial responses."""
        # Successful initial responses
        initial_responses = [
            {"model": "gpt-4", "status": "success", "response": "Initial GPT-4", "metadata": {"response_time": 0.1}},
            {"model": "gemini", "status": "success", "response": "Initial Gemini", "metadata": {"response_time": 0.1}},
        ]

        self.tool.models_to_consult = [{"model": "gpt-4"}, {"model": "gemini"}]

        # Mock successful initial phase
        with patch.object(
            self.tool,
            "_consult_model",
            side_effect=[
                asyncio.coroutine(lambda *a, **k: initial_responses[0])(),
                asyncio.coroutine(lambda *a, **k: initial_responses[1])(),
            ],
        ):
            # Mock refinement to fail for one model
            async def refinement_with_error(model_config, *args, **kwargs):
                if model_config["model"] == "gpt-4":
                    # GPT-4 refinement succeeds
                    return {
                        "model": "gpt-4",
                        "status": "success",
                        "phase": "refinement",
                        "initial_response": "Initial GPT-4",
                        "refined_response": "Refined GPT-4",
                        "metadata": {"response_time": 0.2},
                    }
                else:
                    # Gemini refinement fails
                    raise RuntimeError("Refinement API error")

            with patch.object(self.tool, "_consult_model_with_feedback", side_effect=refinement_with_error):
                with patch.object(self.tool, "_get_phase_timeout", return_value=10.0):

                    request = MagicMock()
                    request.prompt = "Test"
                    request.models = self.tool.models_to_consult
                    request.enable_cross_feedback = True
                    request.relevant_files = []
                    request.images = None
                    request.temperature = 0.7
                    request.continuation_id = None
                    request.cross_feedback_prompt = None

                    with patch.object(self.tool, "get_request_model", return_value=lambda **kwargs: request):
                        result = await self.tool.execute(
                            {"prompt": "Test", "models": self.tool.models_to_consult, "enable_cross_feedback": True}
                        )

                        import json

                        response_data = json.loads(result[0].text)

                        # Should still have 2 successful responses
                        self.assertEqual(response_data["successful_responses"], 2)

                        # Check responses
                        responses_by_model = {r["model"]: r for r in response_data["responses"]}

                        # GPT-4 should have refined response
                        self.assertEqual(responses_by_model["gpt-4"]["response"], "Refined GPT-4")

                        # Gemini should fall back to initial response
                        self.assertEqual(responses_by_model["gemini"]["response"], "Initial Gemini")


if __name__ == "__main__":
    unittest.main()
