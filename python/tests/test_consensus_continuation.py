"""Test consensus tool continuation functionality."""

import unittest
from unittest.mock import patch

from server import reconstruct_thread_context
from tools.consensus import ConsensusTool
from utils.conversation_memory import ConversationTurn, ThreadContext


class TestConsensusContinuation(unittest.TestCase):
    """Test consensus tool continuation without model inheritance issues."""

    def setUp(self):
        """Set up test fixtures."""
        self.consensus_tool = ConsensusTool()

    @patch("utils.conversation_memory.add_turn")
    @patch("utils.conversation_memory.get_thread")
    def test_consensus_continuation_skips_model_inheritance(self, mock_get_thread, mock_add_turn):
        """Test that consensus continuations don't inherit model names from consensus turns."""
        # Mock add_turn to return True
        mock_add_turn.return_value = True

        # Create a thread with consensus turn
        thread_id = "test-thread-123"
        thread_context = ThreadContext(
            thread_id=thread_id,
            created_at="2024-01-01T00:00:00Z",
            last_updated_at="2024-01-01T00:00:00Z",
            tool_name="consensus",
            turns=[
                ConversationTurn(
                    role="user", content="What is 2+2?", timestamp="2024-01-01T00:00:00Z", tool_name="consensus"
                ),
                ConversationTurn(
                    role="assistant",
                    content='{"status": "consensus_complete", "responses": [...]}',
                    timestamp="2024-01-01T00:01:00Z",
                    tool_name="consensus",
                    model_name="gemini-pro, o3",  # This should NOT be inherited
                    model_provider="multi-model-consensus",
                ),
            ],
            initial_context={"models": [{"model": "gemini-pro"}, {"model": "o3"}]},
        )

        # Mock get_thread to return our thread context
        mock_get_thread.return_value = thread_context

        # Test reconstruct_thread_context
        arguments = {
            "continuation_id": thread_id,
            "prompt": "What is 4+4?",
            "models": [{"model": "gemini-pro"}, {"model": "o3"}, {"model": "grok"}],
        }

        # Run the async function
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(reconstruct_thread_context(arguments))

            # Verify that 'model' was NOT set to the consensus model names
            self.assertNotEqual(result.get("model"), "gemini-pro, o3")

            # The model should either be None or a valid fallback for consensus
            # (consensus tool doesn't require a model anyway)
            if "model" in result:
                # Should not contain comma-separated model list
                self.assertNotIn(",", str(result.get("model", "")))

        finally:
            loop.close()

    def test_consensus_requires_model_returns_false(self):
        """Verify consensus tool doesn't require model resolution."""
        self.assertFalse(self.consensus_tool.requires_model())

    def test_consensus_tool_does_not_inherit_model(self):
        """Test that consensus tool skips model resolution entirely."""
        # Verify the tool metadata
        self.assertEqual(self.consensus_tool.get_name(), "consensus")
        self.assertFalse(self.consensus_tool.requires_model())


if __name__ == "__main__":
    unittest.main()
