"""
Test suite for observability callbacks in the LiteLLM provider.

This test suite validates that the observability system correctly integrates
with the LiteLLM provider and logs appropriate metrics.
"""

import logging
import unittest
from unittest.mock import Mock, patch

from observability.callbacks import (
    CostTracker,
    LatencyTracker,
    SecureLogger,
    ZenObservabilityHandler,
    configure_litellm_callbacks,
)
from providers.litellm_provider import LiteLLMProvider


class TestSecureLogger(unittest.TestCase):
    """Test the SecureLogger class for PII redaction."""

    def test_email_redaction(self):
        """Test email address redaction."""
        text = "Contact me at john.doe@example.com for more info"
        redacted = SecureLogger.redact_pii(text)
        self.assertIn("[EMAIL]", redacted)
        self.assertNotIn("john.doe@example.com", redacted)

    def test_phone_redaction(self):
        """Test phone number redaction."""
        text = "Call me at 123-456-7890"
        redacted = SecureLogger.redact_pii(text)
        self.assertIn("[PHONE]", redacted)
        self.assertNotIn("123-456-7890", redacted)

    def test_ssn_redaction(self):
        """Test SSN redaction."""
        text = "My SSN is 123-45-6789"
        redacted = SecureLogger.redact_pii(text)
        self.assertIn("[SSN]", redacted)
        self.assertNotIn("123-45-6789", redacted)

    def test_api_key_redaction(self):
        """Test API key redaction."""
        text = "Use API key sk-1234567890abcdefghijklmnopqrstuvwxyz1234567890"
        redacted = SecureLogger.redact_pii(text)
        self.assertIn("[API_KEY]", redacted)
        self.assertNotIn("sk-1234567890abcdefghijklmnopqrstuvwxyz1234567890", redacted)

    def test_password_redaction(self):
        """Test password redaction."""
        text = "Password: secret123"
        redacted = SecureLogger.redact_pii(text)
        self.assertIn("[REDACTED]", redacted)
        self.assertNotIn("secret123", redacted)

    def test_safe_log_content_truncation(self):
        """Test content truncation in safe_log_content."""
        long_text = "a" * 2000
        safe_content = SecureLogger.safe_log_content(long_text, max_length=100)
        self.assertLess(len(safe_content), 200)  # Should be truncated + marker
        self.assertIn("[TRUNCATED]", safe_content)

    def test_redaction_disabled(self):
        """Test PII redaction can be disabled."""
        text = "Email: john@example.com"

        with patch.dict("os.environ", {"OBSERVABILITY_REDACT_PII": "false"}):
            redacted = SecureLogger.redact_pii(text)
            self.assertIn("john@example.com", redacted)
            self.assertNotIn("[EMAIL]", redacted)


class TestCostTracker(unittest.TestCase):
    """Test the CostTracker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_logger = Mock(spec=logging.Logger)
        self.cost_tracker = CostTracker(self.mock_logger)

    def test_track_cost_success(self):
        """Test successful cost tracking."""
        kwargs = {
            "response_cost": 0.002,
            "model": "gpt-4o",
        }

        mock_response = Mock()
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150

        self.cost_tracker.track_cost(kwargs, mock_response)

        # Verify cost was tracked
        self.assertEqual(self.cost_tracker.total_cost, 0.002)
        self.assertEqual(self.cost_tracker.call_count, 1)

        # Verify logging
        self.mock_logger.info.assert_called_once()
        log_call = self.mock_logger.info.call_args[0][0]
        self.assertIn("COST_TRACKING", log_call)
        self.assertIn("gpt-4o", log_call)

    def test_track_cost_no_usage(self):
        """Test cost tracking without usage information."""
        kwargs = {
            "response_cost": 0.001,
            "model": "test-model",
        }

        mock_response = Mock()
        mock_response.usage = None

        self.cost_tracker.track_cost(kwargs, mock_response)

        # Should still track cost
        self.assertEqual(self.cost_tracker.total_cost, 0.001)
        self.assertEqual(self.cost_tracker.call_count, 1)

    def test_get_stats(self):
        """Test getting cost statistics."""
        # Track some costs
        kwargs1 = {"response_cost": 0.001, "model": "model1"}
        kwargs2 = {"response_cost": 0.002, "model": "model2"}

        mock_response = Mock()
        mock_response.usage = None

        self.cost_tracker.track_cost(kwargs1, mock_response)
        self.cost_tracker.track_cost(kwargs2, mock_response)

        stats = self.cost_tracker.get_stats()

        self.assertEqual(stats["total_cost"], 0.003)
        self.assertEqual(stats["call_count"], 2)
        self.assertEqual(stats["average_cost"], 0.0015)


class TestLatencyTracker(unittest.TestCase):
    """Test the LatencyTracker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_logger = Mock(spec=logging.Logger)
        self.latency_tracker = LatencyTracker(self.mock_logger)

    def test_track_latency_success(self):
        """Test successful latency tracking."""
        kwargs = {"model": "gpt-4o"}
        start_time = 1000.0
        end_time = 1002.5

        self.latency_tracker.track_latency(kwargs, start_time, end_time)

        # Verify latency was tracked
        self.assertEqual(self.latency_tracker.total_latency, 2.5)
        self.assertEqual(self.latency_tracker.call_count, 1)

        # Verify logging
        self.mock_logger.info.assert_called_once()
        log_call = self.mock_logger.info.call_args[0][0]
        self.assertIn("LATENCY_TRACKING", log_call)
        self.assertIn("gpt-4o", log_call)
        self.assertIn("2.500s", log_call)

    def test_get_stats(self):
        """Test getting latency statistics."""
        kwargs = {"model": "test-model"}

        self.latency_tracker.track_latency(kwargs, 1000.0, 1001.0)
        self.latency_tracker.track_latency(kwargs, 2000.0, 2003.0)

        stats = self.latency_tracker.get_stats()

        self.assertEqual(stats["total_latency"], 4.0)
        self.assertEqual(stats["call_count"], 2)
        self.assertEqual(stats["average_latency"], 2.0)


class TestZenObservabilityHandler(unittest.TestCase):
    """Test the ZenObservabilityHandler class."""

    def setUp(self):
        """Set up test fixtures."""
        self.handler = ZenObservabilityHandler()

    def test_initialization(self):
        """Test handler initialization."""
        self.assertIsNotNone(self.handler.logger)
        self.assertIsNotNone(self.handler.mcp_activity_logger)
        self.assertIsNotNone(self.handler.cost_tracker)
        self.assertIsNotNone(self.handler.latency_tracker)

    @patch("observability.callbacks.logging.getLogger")
    def test_log_pre_api_call(self, mock_get_logger):
        """Test pre-API call logging."""
        mock_activity_logger = Mock()
        mock_get_logger.return_value = mock_activity_logger

        handler = ZenObservabilityHandler()
        handler.mcp_activity_logger = mock_activity_logger

        model = "gpt-4o"
        messages = [{"role": "user", "content": "Hello"}]
        kwargs = {"temperature": 0.7}

        handler.log_pre_api_call(model, messages, kwargs)

        # Verify MCP activity logging
        mock_activity_logger.info.assert_called_with("LLM_CALL_START: model=gpt-4o")

    @patch("observability.callbacks.logging.getLogger")
    def test_log_success_event(self, mock_get_logger):
        """Test success event logging."""
        mock_activity_logger = Mock()
        mock_main_logger = Mock()

        # Mock the different loggers
        def get_logger_side_effect(name):
            if name == "mcp_activity":
                return mock_activity_logger
            elif name == "zen_observability":
                return mock_main_logger
            else:
                return Mock()

        mock_get_logger.side_effect = get_logger_side_effect

        handler = ZenObservabilityHandler()

        kwargs = {
            "model": "gpt-4o",
            "response_cost": 0.002,
        }

        mock_response = Mock()
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150

        handler.log_success_event(kwargs, mock_response, 1000.0, 1002.0)

        # Verify MCP activity logging (should be called)
        mock_activity_logger.info.assert_called_with("LLM_SUCCESS: model=gpt-4o")

        # Verify cost tracking is logged to main logger
        mock_main_logger.info.assert_called()

    @patch("observability.callbacks.logging.getLogger")
    def test_log_failure_event(self, mock_get_logger):
        """Test failure event logging."""
        mock_activity_logger = Mock()
        mock_logger = Mock()
        mock_get_logger.side_effect = [mock_logger, mock_activity_logger]

        handler = ZenObservabilityHandler()
        handler.mcp_activity_logger = mock_activity_logger
        handler.logger = mock_logger

        kwargs = {"model": "gpt-4o"}
        error = Exception("Test error")

        handler.log_failure_event(kwargs, error, 1000.0, 1002.0)

        # Verify MCP activity logging
        mock_activity_logger.info.assert_called_with("LLM_FAILURE: model=gpt-4o error=Exception")

    def test_get_stats(self):
        """Test getting observability statistics."""
        stats = self.handler.get_stats()

        self.assertIn("cost_stats", stats)
        self.assertIn("latency_stats", stats)
        self.assertIn("total_cost", stats["cost_stats"])
        self.assertIn("total_latency", stats["latency_stats"])


class TestObservabilityIntegration(unittest.TestCase):
    """Test observability integration with LiteLLM provider."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset any existing callbacks
        import litellm

        litellm.callbacks = []
        litellm.success_callback = []
        litellm.failure_callback = []

    def test_configure_litellm_callbacks(self):
        """Test configuring LiteLLM callbacks."""
        import litellm

        # Initially no callbacks
        self.assertEqual(len(litellm.callbacks), 0)

        # Configure callbacks
        configure_litellm_callbacks(enable_observability=True)

        # Verify callbacks were added
        self.assertGreater(len(litellm.callbacks), 0)
        self.assertIn("zen_observability", litellm.success_callback)
        self.assertIn("zen_observability", litellm.failure_callback)

    def test_configure_litellm_callbacks_disabled(self):
        """Test disabling observability callbacks."""
        import litellm

        # Configure with disabled observability
        configure_litellm_callbacks(enable_observability=False)

        # Should not add callbacks
        self.assertEqual(len(litellm.callbacks), 0)

    @patch.dict("os.environ", {"OBSERVABILITY_ENABLED": "true"})
    @patch("observability.callbacks.configure_litellm_callbacks")
    def test_provider_initialization_with_observability(self, mock_configure):
        """Test LiteLLM provider initialization with observability enabled."""
        LiteLLMProvider()

        # Verify observability configuration was called
        mock_configure.assert_called_once_with(enable_observability=True)

    @patch.dict("os.environ", {"OBSERVABILITY_ENABLED": "false"})
    @patch("observability.callbacks.configure_litellm_callbacks")
    def test_provider_initialization_without_observability(self, mock_configure):
        """Test LiteLLM provider initialization with observability disabled."""
        LiteLLMProvider()

        # Should not call observability configuration
        mock_configure.assert_not_called()

    def test_provider_get_observability_stats(self):
        """Test getting observability stats from provider."""
        provider = LiteLLMProvider()

        # Should return stats structure
        stats = provider.get_observability_stats()
        self.assertIsInstance(stats, dict)

        # Should have either actual stats or error message
        self.assertTrue("cost_stats" in stats or "error" in stats)


if __name__ == "__main__":
    unittest.main()
