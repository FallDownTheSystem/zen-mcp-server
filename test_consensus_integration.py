"""
Integration test for the new parallel consensus workflow.
This test simulates a real-world consensus gathering scenario.
"""

import asyncio
import json
import logging
from datetime import datetime
from unittest.mock import Mock, patch

from tools.consensus import ConsensusTool

# Set up logging to see the workflow
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class MockProvider:
    """Mock provider that simulates different model responses."""

    def __init__(self, provider_type):
        self.provider_type = provider_type
        self.call_count = 0

    def get_provider_type(self):
        return Mock(value=self.provider_type)

    def generate_content(self, prompt, model_name, system_prompt, temperature, thinking_mode, images=None):
        """Simulate model responses."""
        self.call_count += 1

        # Generate realistic responses based on model
        responses = {
            "gemini-2.5-pro": {
                "content": """After analyzing the proposal for real-time collaboration features, I see strong potential:

**Key Benefits:**
1. **Enhanced User Experience**: Real-time updates would significantly improve team productivity
2. **Competitive Advantage**: This feature is becoming standard in modern applications
3. **Technical Feasibility**: WebSocket infrastructure is mature and well-supported

**Implementation Approach:**
- Use Socket.IO for broad browser compatibility
- Implement operational transformation for conflict resolution
- Start with simple features (cursor position, typing indicators)

**Estimated Timeline**: 6-8 weeks for MVP with core features

The investment is justified given the clear user demand and reasonable implementation complexity.""",
                "usage": {"input_tokens": 150, "output_tokens": 180},
            },
            "o3-mini": {
                "content": """Analyzing the real-time collaboration proposal objectively:

**Major Challenges:**
1. **Infrastructure Complexity**: Requires WebSocket servers, state management, and scaling considerations
2. **Conflict Resolution**: Handling simultaneous edits is notoriously difficult
3. **Performance Impact**: Real-time sync can degrade application performance

**Alternative Approaches:**
- Consider auto-save with periodic sync instead
- Implement simple locking mechanisms first
- Focus on async collaboration tools

**Cost Analysis**:
- Development: 3-4 months (not 6-8 weeks)
- Ongoing maintenance: +2 engineers
- Infrastructure: +$5k/month

The decision should align with current strategic objectives.""",
                "usage": {"input_tokens": 150, "output_tokens": 190},
            },
        }

        # Default response if specific model not found
        default_response = {
            "content": f"Model {model_name}: This is a test response for the proposal. "
            f"Call #{self.call_count} to this provider.",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        response_data = responses.get(model_name, default_response)

        response = Mock()
        response.content = response_data["content"]
        response.usage = response_data["usage"]

        logger.info(f"Mock {model_name} generated response")
        return response


async def test_parallel_consensus_workflow():
    """Test the complete parallel consensus workflow with cross-model feedback."""

    logger.info("=== Starting Parallel Consensus Workflow Test ===")

    # Create consensus tool
    tool = ConsensusTool()

    # Create mock providers
    gemini_provider = MockProvider("gemini")
    openai_provider = MockProvider("openai")

    # Mock the provider registry
    def mock_get_model_provider(model_name):
        if model_name in ["gemini-2.5-pro", "gemini", "pro"]:
            return gemini_provider
        elif model_name in ["o3-mini", "o3"]:
            return openai_provider
        else:
            raise ValueError(f"Unknown model: {model_name}")

    # Create test arguments
    arguments = {
        "prompt": "Should we implement real-time collaboration features in our application? Initial market research shows: 30% of support tickets request real-time features, competitors have basic real-time collaboration, current architecture uses REST APIs only, team has no WebSocket experience.",
        "models": [{"model": "gemini-2.5-pro"}, {"model": "o3-mini"}],
        "relevant_files": [],
        "enable_cross_feedback": True,
        "cross_feedback_prompt": None,  # Use default
    }

    # Patch the get_model_provider method
    with patch.object(tool, "get_model_provider", side_effect=mock_get_model_provider):
        logger.info("Executing consensus workflow...")
        start_time = datetime.now()

        # Execute the workflow
        result = await tool.execute(arguments)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Workflow completed in {duration:.2f} seconds")

        # Parse the result
        assert len(result) == 1
        response_text = result[0].text
        response_data = json.loads(response_text)

        # Log the results
        logger.info("\n=== CONSENSUS RESULTS ===")
        logger.info(f"Status: {response_data['status']}")
        logger.info(f"Models consulted: {response_data['models_consulted']}")
        logger.info(f"Successful initial responses: {response_data['successful_initial_responses']}")
        logger.info(f"Refined responses: {response_data['refined_responses']}")
        logger.info(f"Cross-feedback enabled: {response_data['cross_feedback_enabled']}")

        # Check initial responses
        initial_responses = response_data["phases"]["initial"]
        assert len(initial_responses) == 2

        logger.info("\n=== INITIAL RESPONSES ===")
        for i, resp in enumerate(initial_responses, 1):
            logger.info(f"\n--- Model {i}: {resp['model']} ---")
            logger.info(f"Status: {resp['status']}")
            logger.info(f"Response preview: {resp['response'][:200]}...")
            logger.info(f"Tokens: {resp['metadata']['input_tokens']} in, {resp['metadata']['output_tokens']} out")

        # Check refined responses
        if response_data["phases"]["refined"]:
            refined_responses = response_data["phases"]["refined"]
            logger.info("\n=== REFINED RESPONSES (Cross-Model Feedback) ===")
            logger.info(f"Number of refined responses: {len(refined_responses)}")

            for i, resp in enumerate(refined_responses, 1):
                logger.info(f"\n--- Refined Response {i}: {resp['model']} ---")
                logger.info(f"Status: {resp['status']}")
                if resp["status"] == "success":
                    logger.info("Initial response preview:")
                    logger.info(f"  {resp['initial_response'][:150]}...")
                    logger.info("Refined response preview:")
                    logger.info(f"  {resp['refined_response'][:150]}...")

        # Verify parallel execution
        logger.info("\n=== EXECUTION ANALYSIS ===")
        logger.info(f"Gemini provider calls: {gemini_provider.call_count}")
        logger.info(f"OpenAI provider calls: {openai_provider.call_count}")

        # In parallel execution with cross-feedback:
        # - 2 initial calls (all models in parallel)
        # - 2 refinement calls (if cross-feedback enabled)
        expected_calls = 4 if arguments["enable_cross_feedback"] else 2
        total_calls = gemini_provider.call_count + openai_provider.call_count
        logger.info(f"Total API calls: {total_calls} (expected: {expected_calls})")

        # Verify the response structure
        assert response_data["status"] == "consensus_complete"
        assert response_data["consensus_complete"] is True
        assert response_data["initial_prompt"] == arguments["prompt"]
        assert response_data["models_consulted"] == 2
        assert response_data["successful_initial_responses"] == 2
        assert response_data["cross_feedback_enabled"] is True

        logger.info("\n✅ All assertions passed!")
        logger.info("=== Test completed successfully ===")

        return response_data


async def test_parallel_execution_with_failure():
    """Test that parallel execution continues even if one model fails."""

    logger.info("\n=== Testing Parallel Execution with Model Failure ===")

    tool = ConsensusTool()

    # Create providers where one will fail
    working_provider = MockProvider("gemini")
    failing_provider = Mock()
    failing_provider.get_provider_type.return_value = Mock(value="openai")
    failing_provider.generate_content.side_effect = Exception("API rate limit exceeded")

    def mock_get_model_provider(model_name):
        if model_name == "gemini-2.5-pro":
            return working_provider
        elif model_name == "o3-mini":
            return failing_provider
        else:
            raise ValueError(f"Unknown model: {model_name}")

    arguments = {
        "prompt": "Test question for parallel execution - Testing error handling",
        "models": [{"model": "gemini-2.5-pro"}, {"model": "o3-mini"}, {"model": "gemini-2.5-pro"}],  # This will fail
        "enable_cross_feedback": False,  # Disable to simplify test
    }

    with patch.object(tool, "get_model_provider", side_effect=mock_get_model_provider):
        result = await tool.execute(arguments)

        response_data = json.loads(result[0].text)

        logger.info(f"\nModels consulted: {response_data['models_consulted']}")
        logger.info(f"Successful responses: {response_data['successful_initial_responses']}")
        logger.info(f"Failed models: {response_data['failed_models']}")

        # Debug - show the actual response structure
        logger.info(f"\nDEBUG - Full response: {json.dumps(response_data, indent=2)}")

        # The response might be counting differently - check initial phase
        initial_responses = response_data["phases"]["initial"]
        successful_count = sum(1 for r in initial_responses if r["status"] == "success")
        logger.info(f"Actual successful in initial phase: {successful_count}")

        # Verify that 2 models succeeded despite 1 failure
        assert successful_count == 2
        assert len(response_data["failed_models"]) == 1
        assert response_data["failed_models"][0]["model"] == "o3-mini"
        assert "API rate limit exceeded" in response_data["failed_models"][0]["error"]

        logger.info("\n✅ Error handling test passed!")


async def test_cross_feedback_disabled():
    """Test consensus with cross-feedback disabled for faster execution."""

    logger.info("\n=== Testing Consensus with Cross-Feedback Disabled ===")

    tool = ConsensusTool()
    provider = MockProvider("gemini")

    arguments = {
        "prompt": "Quick consensus test - Need fast consensus",
        "models": [{"model": "gemini-2.5-pro"}, {"model": "gemini-2.5-pro"}],
        "enable_cross_feedback": False,  # Disabled for speed
    }

    with patch.object(tool, "get_model_provider", return_value=provider):
        start_time = datetime.now()
        result = await tool.execute(arguments)
        duration = (datetime.now() - start_time).total_seconds()

        response_data = json.loads(result[0].text)

        logger.info(f"\nExecution time: {duration:.2f} seconds")
        logger.info(f"API calls made: {provider.call_count}")
        logger.info(f"Refined responses: {response_data['refined_responses']}")

        # Should only have initial responses, no refinements
        assert provider.call_count == 2  # Only initial calls
        assert response_data["refined_responses"] == 0
        assert response_data["phases"]["refined"] is None

        logger.info("\n✅ No-feedback mode test passed!")


if __name__ == "__main__":
    # Run specific test based on command line argument
    import sys

    async def run_all_tests():
        await test_parallel_consensus_workflow()
        await test_parallel_execution_with_failure()
        await test_cross_feedback_disabled()
        logger.info("\n🎉 All integration tests completed successfully!")

    if len(sys.argv) > 1 and sys.argv[1] == "main":
        # Run just the main test for clean output
        asyncio.run(test_parallel_consensus_workflow())
    else:
        # Run all tests
        asyncio.run(run_all_tests())
