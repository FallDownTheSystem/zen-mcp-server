"""
LiteLLM callback handlers for observability, monitoring, and cost tracking.

This module implements custom callback handlers that integrate with LiteLLM's
callback system to provide:
- Cost tracking and usage metrics
- Latency and performance monitoring
- Secure logging (PII prevention)
- Integration with existing MCP activity logging

The callbacks are designed to be lightweight and non-intrusive, ensuring
they don't impact the performance of LLM calls.
"""

import logging
import os
import re
from typing import Any

import litellm
from litellm.integrations.custom_logger import CustomLogger


class SecureLogger:
    """Utility class for secure logging with PII prevention."""

    # Patterns to identify and redact sensitive information
    PII_PATTERNS = [
        # Email addresses
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]"),
        # Phone numbers (various formats)
        (r"\b\d{3}-\d{3}-\d{4}\b", "[PHONE]"),
        (r"\b\(\d{3}\)\s*\d{3}-\d{4}\b", "[PHONE]"),
        # Social security numbers
        (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]"),
        # Credit card numbers (simple pattern)
        (r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b", "[CARD]"),
        # API keys (common patterns)
        (r"\b(sk-[a-zA-Z0-9]{48})\b", "[API_KEY]"),
        (r"\b(sk-[a-zA-Z0-9-]{20,})\b", "[API_KEY]"),
        # Generic secrets
        (r'\b(secret|password|token|key)[\s]*[=:][\s]*[\'"]?([^\s\'"]+)[\'"]?\b', lambda m: f"{m.group(1)}=[REDACTED]"),
    ]

    @classmethod
    def redact_pii(cls, text: str) -> str:
        """Redact PII from text content."""
        if not text or not isinstance(text, str):
            return text

        # Skip redaction in development/debug mode
        if os.getenv("OBSERVABILITY_REDACT_PII", "true").lower() == "false":
            return text

        redacted_text = text
        for pattern, replacement in cls.PII_PATTERNS:
            if callable(replacement):
                redacted_text = re.sub(pattern, replacement, redacted_text, flags=re.IGNORECASE)
            else:
                redacted_text = re.sub(pattern, replacement, redacted_text, flags=re.IGNORECASE)

        return redacted_text

    @classmethod
    def safe_log_content(cls, content: Any, max_length: int = 1000) -> str:
        """Safely log content with PII redaction and length limits."""
        if content is None:
            return "None"

        # Convert to string
        text = str(content)

        # Redact PII
        text = cls.redact_pii(text)

        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length] + "... [TRUNCATED]"

        return text


class CostTracker:
    """Tracks and logs cost information for LLM API calls."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.total_cost = 0.0
        self.call_count = 0

    def track_cost(self, kwargs: dict[str, Any], response_obj: Any) -> None:
        """Track cost for a successful API call."""
        try:
            response_cost = kwargs.get("response_cost", 0.0)
            model_name = kwargs.get("model", "unknown")

            # Update totals
            self.total_cost += response_cost
            self.call_count += 1

            # Extract usage information
            usage = {}
            if hasattr(response_obj, "usage") and response_obj.usage:
                usage = {
                    "input_tokens": getattr(response_obj.usage, "prompt_tokens", 0),
                    "output_tokens": getattr(response_obj.usage, "completion_tokens", 0),
                    "total_tokens": getattr(response_obj.usage, "total_tokens", 0),
                }

            # Log cost information
            self.logger.info(
                f"COST_TRACKING: model={model_name} cost=${response_cost:.6f} "
                f"usage={usage} total_cost=${self.total_cost:.6f} calls={self.call_count}"
            )

        except Exception as e:
            self.logger.warning(f"Cost tracking failed: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get cost tracking statistics."""
        return {
            "total_cost": self.total_cost,
            "call_count": self.call_count,
            "average_cost": self.total_cost / self.call_count if self.call_count > 0 else 0.0,
        }


class LatencyTracker:
    """Tracks and logs latency metrics for LLM API calls."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.total_latency = 0.0
        self.call_count = 0

    def track_latency(self, kwargs: dict[str, Any], start_time: float, end_time: float) -> None:
        """Track latency for an API call."""
        try:
            latency = end_time - start_time
            model_name = kwargs.get("model", "unknown")

            # Update totals
            self.total_latency += latency
            self.call_count += 1

            # Log latency information
            self.logger.info(
                f"LATENCY_TRACKING: model={model_name} latency={latency:.3f}s "
                f"avg_latency={self.total_latency / self.call_count:.3f}s calls={self.call_count}"
            )

        except Exception as e:
            self.logger.warning(f"Latency tracking failed: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get latency tracking statistics."""
        return {
            "total_latency": self.total_latency,
            "call_count": self.call_count,
            "average_latency": self.total_latency / self.call_count if self.call_count > 0 else 0.0,
        }


class ZenObservabilityHandler(CustomLogger):
    """
    Custom LiteLLM callback handler for Zen MCP Server observability.

    This handler integrates with the existing logging infrastructure to provide:
    - Cost tracking and usage metrics
    - Latency monitoring
    - Secure logging with PII prevention
    - Integration with mcp_activity logger
    """

    def __init__(self):
        super().__init__()

        # Set up loggers
        self.logger = logging.getLogger("zen_observability")
        self.mcp_activity_logger = logging.getLogger("mcp_activity")

        # Initialize trackers
        self.cost_tracker = CostTracker(self.logger)
        self.latency_tracker = LatencyTracker(self.logger)

        # Configuration
        self.log_requests = os.getenv("OBSERVABILITY_LOG_REQUESTS", "false").lower() == "true"
        self.log_responses = os.getenv("OBSERVABILITY_LOG_RESPONSES", "false").lower() == "true"

        self.logger.info("ZenObservabilityHandler initialized")

    def log_pre_api_call(self, model: str, messages: list, kwargs: dict[str, Any]) -> None:
        """Log information before API call."""
        try:
            # Log to MCP activity for monitoring
            self.mcp_activity_logger.info(f"LLM_CALL_START: model={model}")

            # Detailed logging if enabled
            if self.log_requests:
                safe_messages = [
                    {
                        "role": msg.get("role", "unknown"),
                        "content": SecureLogger.safe_log_content(msg.get("content", ""), 200),
                    }
                    for msg in messages[-2:]  # Only log last 2 messages
                ]
                self.logger.debug(f"REQUEST: model={model} messages={safe_messages}")

        except Exception as e:
            self.logger.warning(f"Pre-API call logging failed: {e}")

    def log_post_api_call(self, kwargs: dict[str, Any], response_obj: Any, start_time: float, end_time: float) -> None:
        """Log information after API call."""
        try:
            model_name = kwargs.get("model", "unknown")

            # Log completion to MCP activity
            self.mcp_activity_logger.info(f"LLM_CALL_END: model={model_name}")

            # Track latency
            self.latency_tracker.track_latency(kwargs, start_time, end_time)

        except Exception as e:
            self.logger.warning(f"Post-API call logging failed: {e}")

    def log_success_event(self, kwargs: dict[str, Any], response_obj: Any, start_time: float, end_time: float) -> None:
        """Log successful API call."""
        try:
            model_name = kwargs.get("model", "unknown")

            # Log success to MCP activity
            self.mcp_activity_logger.info(f"LLM_SUCCESS: model={model_name}")

            # Track cost
            self.cost_tracker.track_cost(kwargs, response_obj)

            # Log response if enabled
            if self.log_responses and hasattr(response_obj, "choices") and response_obj.choices:
                content = response_obj.choices[0].message.content
                safe_content = SecureLogger.safe_log_content(content, 300)
                self.logger.debug(f"RESPONSE: model={model_name} content={safe_content}")

        except Exception as e:
            self.logger.warning(f"Success event logging failed: {e}")

    def log_failure_event(self, kwargs: dict[str, Any], response_obj: Any, start_time: float, end_time: float) -> None:
        """Log failed API call."""
        try:
            model_name = kwargs.get("model", "unknown")
            error_type = type(response_obj).__name__ if response_obj else "Unknown"
            error_msg = str(response_obj) if response_obj else "Unknown error"

            # Redact PII from error message
            safe_error_msg = SecureLogger.safe_log_content(error_msg, 500)

            # Log failure to MCP activity
            self.mcp_activity_logger.info(f"LLM_FAILURE: model={model_name} error={error_type}")

            # Log detailed error
            self.logger.error(f"LLM_ERROR: model={model_name} type={error_type} msg={safe_error_msg}")

        except Exception as e:
            self.logger.warning(f"Failure event logging failed: {e}")

    # Async versions for async API calls
    async def async_log_success_event(
        self, kwargs: dict[str, Any], response_obj: Any, start_time: float, end_time: float
    ) -> None:
        """Async version of log_success_event."""
        self.log_success_event(kwargs, response_obj, start_time, end_time)

    async def async_log_failure_event(
        self, kwargs: dict[str, Any], response_obj: Any, start_time: float, end_time: float
    ) -> None:
        """Async version of log_failure_event."""
        self.log_failure_event(kwargs, response_obj, start_time, end_time)

    def get_stats(self) -> dict[str, Any]:
        """Get observability statistics."""
        return {
            "cost_stats": self.cost_tracker.get_stats(),
            "latency_stats": self.latency_tracker.get_stats(),
        }


def configure_litellm_callbacks(enable_observability: bool = True) -> None:
    """
    Configure LiteLLM callbacks for observability.

    Args:
        enable_observability: Whether to enable observability callbacks
    """
    if not enable_observability:
        return

    # Create and register the observability handler
    handler = ZenObservabilityHandler()

    # Register with LiteLLM
    if handler not in litellm.callbacks:
        litellm.callbacks.append(handler)

    # Also register for success/failure callbacks if needed
    if "zen_observability" not in litellm.success_callback:
        litellm.success_callback.append("zen_observability")
    if "zen_observability" not in litellm.failure_callback:
        litellm.failure_callback.append("zen_observability")

    # Configure LiteLLM settings
    litellm.set_verbose = os.getenv("OBSERVABILITY_VERBOSE", "false").lower() == "true"

    logger = logging.getLogger("zen_observability")
    logger.info("LiteLLM observability callbacks configured")
