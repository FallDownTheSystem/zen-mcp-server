"""Test timeout behavior in the consensus tool."""

import asyncio
import os
import unittest
from unittest.mock import MagicMock, Mock, patch

import pytest

from providers.base import ModelCapabilities, ModelProvider, ModelResponse, ProviderType
from tools.consensus import ConsensusTool


class TestConsensusTimeouts(unittest.TestCase):
    """Test timeout handling in consensus tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.tool = ConsensusTool()

    def test_get_consensus_timeout_default(self):
        """Test default consensus timeout when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            timeout = self.tool._get_consensus_timeout()
            self.assertEqual(timeout, 600.0)  # 10 minutes default

    def test_get_consensus_timeout_from_env(self):
        """Test consensus timeout from environment variable."""
        with patch.dict(os.environ, {"CONSENSUS_MODEL_TIMEOUT": "300"}):
            timeout = self.tool._get_consensus_timeout()
            self.assertEqual(timeout, 300.0)

    def test_get_consensus_timeout_invalid_env(self):
        """Test consensus timeout with invalid env var falls back to default."""
        test_cases = [
            ("invalid", 600.0),
            ("-100", 600.0),
            ("0", 600.0),
            ("", 600.0),
        ]

        for env_value, expected in test_cases:
            with self.subTest(env_value=env_value):
                with patch.dict(os.environ, {"CONSENSUS_MODEL_TIMEOUT": env_value}):
                    timeout = self.tool._get_consensus_timeout()
                    self.assertEqual(timeout, expected)

    def test_get_model_timeout_from_capabilities(self):
        """Test getting model-specific timeout from capabilities."""
        # Mock provider with custom timeout
        mock_provider = Mock(spec=ModelProvider)
        mock_capabilities = ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3-pro",
            friendly_name="OpenAI",
            context_window=128000,
            max_output_tokens=16384,
            timeout=1800.0,  # 30 minutes
        )
        mock_provider.get_capabilities.return_value = mock_capabilities

        with patch.object(self.tool, "get_model_provider", return_value=mock_provider):
            timeout = self.tool._get_model_timeout("o3-pro")
            self.assertEqual(timeout, 1800.0)

    def test_get_model_timeout_fallback_to_consensus(self):
        """Test model timeout falls back to consensus timeout if not specified."""
        # Mock provider without timeout in capabilities
        mock_provider = Mock(spec=ModelProvider)
        mock_capabilities = Mock()
        # Simulate missing timeout attribute
        del mock_capabilities.timeout
        mock_provider.get_capabilities.return_value = mock_capabilities

        with patch.object(self.tool, "get_model_provider", return_value=mock_provider):
            with patch.dict(os.environ, {"CONSENSUS_MODEL_TIMEOUT": "450"}):
                timeout = self.tool._get_model_timeout("gpt-4")
                self.assertEqual(timeout, 450.0)

    def test_get_model_timeout_provider_error(self):
        """Test model timeout handles provider errors gracefully."""
        with patch.object(self.tool, "get_model_provider", side_effect=Exception("Provider error")):
            timeout = self.tool._get_model_timeout("unknown-model")
            self.assertEqual(timeout, 600.0)  # Falls back to default

    def test_get_phase_timeout_calculation(self):
        """Test phase timeout calculation takes max model timeout plus buffer."""
        model_configs = [
            {"model": "gpt-4"},
            {"model": "o3-pro"},
            {"model": "gemini-pro"},
        ]

        # Mock different timeouts for each model
        def mock_get_model_timeout(model_name):
            timeouts = {
                "gpt-4": 180.0,  # 3 minutes
                "o3-pro": 1800.0,  # 30 minutes
                "gemini-pro": 300.0,  # 5 minutes
            }
            return timeouts.get(model_name, 600.0)

        with patch.object(self.tool, "_get_model_timeout", side_effect=mock_get_model_timeout):
            phase_timeout = self.tool._get_phase_timeout(model_configs)
            # Should be max (1800) + 60 second buffer
            self.assertEqual(phase_timeout, 1860.0)

    def test_get_phase_timeout_empty_configs(self):
        """Test phase timeout with empty model configs."""
        phase_timeout = self.tool._get_phase_timeout([])
        # Should be 0 + 60 second buffer
        self.assertEqual(phase_timeout, 60.0)


class TestConsensusTimeoutExecution(unittest.TestCase):
    """Test timeout behavior during consensus execution."""

    def setUp(self):
        """Set up test fixtures."""
        self.tool = ConsensusTool()

    @pytest.mark.asyncio
    async def test_phase_timeout_cancels_pending_tasks(self):
        """Test that phase timeout properly cancels pending tasks."""

        # Create a mock that will hang forever
        async def hanging_consult(*args, **kwargs):
            await asyncio.sleep(10000)  # Simulate hanging
            return {"model": "test", "status": "success", "response": "Should not reach here"}

        # Set up the tool with test models
        self.tool.models_to_consult = [
            {"model": "fast-model"},
            {"model": "hanging-model"},
        ]

        # Mock the consult methods
        fast_response = {
            "model": "fast-model",
            "status": "success",
            "phase": "initial",
            "response": "Fast response",
            "metadata": {"response_time": 0.1},
        }

        with patch.object(self.tool, "_get_phase_timeout", return_value=0.5):  # 500ms timeout
            with patch.object(self.tool, "_consult_model") as mock_consult:
                # First call returns quickly, second hangs
                mock_consult.side_effect = [asyncio.coroutine(lambda: fast_response)(), hanging_consult()]

                # Execute consensus
                request = MagicMock()
                request.prompt = "Test prompt"
                request.models = self.tool.models_to_consult
                request.enable_cross_feedback = False
                request.relevant_files = []
                request.images = None
                request.temperature = 0.7
                request.continuation_id = None

                # Mock the request model
                with patch.object(self.tool, "get_request_model", return_value=lambda **kwargs: request):
                    result = await self.tool.execute(
                        {"prompt": "Test prompt", "models": self.tool.models_to_consult, "enable_cross_feedback": False}
                    )

                    # Parse the response
                    import json

                    response_data = json.loads(result[0].text)

                    # Should have one successful response
                    self.assertEqual(response_data["successful_responses"], 1)
                    # Should have one failed model due to timeout
                    self.assertEqual(len(response_data["failed_models"]), 1)
                    self.assertIn("timeout", response_data["failed_models"][0]["error"].lower())

    @pytest.mark.asyncio
    async def test_individual_model_timeout_propagated_to_provider(self):
        """Test that model-specific timeouts are passed to provider."""
        # Mock provider
        mock_provider = Mock(spec=ModelProvider)
        mock_response = ModelResponse(
            content="Test response", usage={"input_tokens": 10, "output_tokens": 20}, model_name="o3-pro"
        )
        mock_provider.generate_content = Mock(return_value=mock_response)
        mock_provider.get_provider_type.return_value = ProviderType.OPENAI

        # Mock capabilities with custom timeout
        mock_capabilities = ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3-pro",
            friendly_name="OpenAI",
            context_window=128000,
            max_output_tokens=16384,
            timeout=3600.0,  # 1 hour
        )
        mock_provider.get_capabilities.return_value = mock_capabilities

        # Set up tool
        self.tool.models_to_consult = [{"model": "o3-pro"}]

        with patch.object(self.tool, "get_model_provider", return_value=mock_provider):
            request = MagicMock()
            request.prompt = "Test prompt"
            request.models = self.tool.models_to_consult
            request.continuation_id = None
            request.relevant_files = []
            request.images = None
            request.temperature = 0.7
            request.reasoning_effort = "medium"

            # Call _consult_model directly
            await self.tool._consult_model({"model": "o3-pro"}, request)

            # Verify provider was called with correct timeout
            mock_provider.generate_content.assert_called_once()
            call_kwargs = mock_provider.generate_content.call_args[1]
            self.assertEqual(call_kwargs["timeout"], 3600.0)

    @pytest.mark.asyncio
    async def test_refinement_phase_timeout(self):
        """Test timeout handling in refinement phase."""
        # Set up successful initial responses
        initial_responses = [
            {
                "model": "gpt-4",
                "status": "success",
                "response": "Initial response 1",
                "metadata": {"response_time": 1.0},
            },
            {
                "model": "gemini-pro",
                "status": "success",
                "response": "Initial response 2",
                "metadata": {"response_time": 1.0},
            },
        ]

        # Mock hanging refinement
        async def hanging_refinement(*args, **kwargs):
            await asyncio.sleep(10000)
            return {"status": "should not reach"}

        self.tool.models_to_consult = [{"model": "gpt-4"}, {"model": "gemini-pro"}]

        # Mock initial consultation to return quickly
        with patch.object(
            self.tool,
            "_consult_model",
            side_effect=[
                asyncio.coroutine(lambda *a, **k: initial_responses[0])(),
                asyncio.coroutine(lambda *a, **k: initial_responses[1])(),
            ],
        ):
            # Mock refinement to hang
            with patch.object(self.tool, "_consult_model_with_feedback", side_effect=hanging_refinement):
                with patch.object(self.tool, "_get_phase_timeout", return_value=0.5):  # 500ms timeout

                    request = MagicMock()
                    request.prompt = "Test prompt"
                    request.models = self.tool.models_to_consult
                    request.enable_cross_feedback = True  # Enable refinement
                    request.relevant_files = []
                    request.images = None
                    request.temperature = 0.7
                    request.continuation_id = None
                    request.cross_feedback_prompt = None

                    with patch.object(self.tool, "get_request_model", return_value=lambda **kwargs: request):
                        result = await self.tool.execute(
                            {
                                "prompt": "Test prompt",
                                "models": self.tool.models_to_consult,
                                "enable_cross_feedback": True,
                            }
                        )

                        import json

                        response_data = json.loads(result[0].text)

                        # Should have successful initial responses
                        self.assertEqual(response_data["successful_responses"], 2)
                        # Refinement should have timed out, but we still have initial responses
                        self.assertEqual(len(response_data["responses"]), 2)

    @pytest.mark.asyncio
    async def test_partial_results_on_timeout(self):
        """Test that partial results are returned when some models timeout."""

        # Create mixed response timings
        async def fast_model(*args, **kwargs):
            await asyncio.sleep(0.1)
            return {
                "model": "fast-model",
                "status": "success",
                "phase": "initial",
                "response": "Fast response",
                "metadata": {"response_time": 0.1},
            }

        async def slow_model(*args, **kwargs):
            await asyncio.sleep(0.3)
            return {
                "model": "slow-model",
                "status": "success",
                "phase": "initial",
                "response": "Slow response",
                "metadata": {"response_time": 0.3},
            }

        async def hanging_model(*args, **kwargs):
            await asyncio.sleep(10000)
            return {"model": "hanging-model", "status": "success"}

        self.tool.models_to_consult = [{"model": "fast-model"}, {"model": "slow-model"}, {"model": "hanging-model"}]

        # Mock consult with different timings
        consult_functions = [fast_model, slow_model, hanging_model]
        with patch.object(self.tool, "_consult_model", side_effect=consult_functions):
            with patch.object(self.tool, "_get_phase_timeout", return_value=0.5):  # 500ms timeout

                request = MagicMock()
                request.prompt = "Test prompt"
                request.models = self.tool.models_to_consult
                request.enable_cross_feedback = False
                request.relevant_files = []
                request.images = None
                request.temperature = 0.7
                request.continuation_id = None

                with patch.object(self.tool, "get_request_model", return_value=lambda **kwargs: request):
                    result = await self.tool.execute(
                        {"prompt": "Test prompt", "models": self.tool.models_to_consult, "enable_cross_feedback": False}
                    )

                    import json

                    response_data = json.loads(result[0].text)

                    # Should have 2 successful responses (fast and slow)
                    self.assertEqual(response_data["successful_responses"], 2)
                    # Should have 1 failed model (hanging)
                    self.assertEqual(len(response_data["failed_models"]), 1)
                    self.assertEqual(response_data["failed_models"][0]["model"], "hanging-model")
                    self.assertIn("timeout", response_data["failed_models"][0]["error"].lower())


class TestTimeoutErrorHandling(unittest.TestCase):
    """Test error handling for timeout scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.tool = ConsensusTool()

    @pytest.mark.asyncio
    async def test_timeout_error_includes_phase_info(self):
        """Test that timeout errors include phase information."""

        async def hanging_model(*args, **kwargs):
            await asyncio.sleep(10000)

        self.tool.models_to_consult = [{"model": "test-model"}]

        with patch.object(self.tool, "_consult_model", side_effect=hanging_model):
            with patch.object(self.tool, "_get_phase_timeout", return_value=0.1):  # 100ms timeout

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

                    # Check error includes phase
                    self.assertEqual(response_data["failed_models"][0]["phase"], "initial")

    def test_timeout_logging(self):
        """Test that extended timeouts are logged appropriately."""
        mock_provider = Mock(spec=ModelProvider)
        mock_capabilities = ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3-deep-research",
            friendly_name="OpenAI",
            context_window=128000,
            max_output_tokens=16384,
            timeout=3600.0,  # 1 hour - should trigger logging
        )
        mock_provider.get_capabilities.return_value = mock_capabilities

        with patch.object(self.tool, "get_model_provider", return_value=mock_provider):
            with patch("tools.consensus.logger") as mock_logger:
                timeout = self.tool._get_model_timeout("o3-deep-research")

                # Should log extended timeout
                mock_logger.info.assert_called_with("Using extended timeout of 3600.0s for model o3-deep-research")
                self.assertEqual(timeout, 3600.0)


if __name__ == "__main__":
    unittest.main()
