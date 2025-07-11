"""
Communication Simulator Tests Package

This package contains individual test modules for the Zen MCP Communication Simulator.
Each test is in its own file for better organization and maintainability.
"""

from .base_test import BaseSimulatorTest
from .test_basic_conversation import BasicConversationTest
from .test_chat_simple_validation import ChatSimpleValidationTest
from .test_consensus_conversation import TestConsensusConversation
from .test_consensus_three_models import TestConsensusThreeModels
from .test_consensus_workflow_accurate import TestConsensusWorkflowAccurate
from .test_content_validation import ContentValidationTest
from .test_line_number_validation import LineNumberValidationTest
from .test_logs_validation import LogsValidationTest
from .test_model_thinking_config import TestModelThinkingConfig
from .test_o3_model_selection import O3ModelSelectionTest
from .test_o3_pro_expensive import O3ProExpensiveTest
from .test_ollama_custom_url import OllamaCustomUrlTest
from .test_openrouter_fallback import OpenRouterFallbackTest
from .test_openrouter_models import OpenRouterModelsTest
from .test_per_tool_deduplication import PerToolDeduplicationTest
from .test_prompt_size_limit_bug import PromptSizeLimitBugTest
from .test_token_allocation_validation import TokenAllocationValidationTest
from .test_vision_capability import VisionCapabilityTest
from .test_xai_models import XAIModelsTest

# Test registry for dynamic loading
TEST_REGISTRY = {
    "basic_conversation": BasicConversationTest,
    "chat_validation": ChatSimpleValidationTest,
    "content_validation": ContentValidationTest,
    "per_tool_deduplication": PerToolDeduplicationTest,
    "line_number_validation": LineNumberValidationTest,
    "logs_validation": LogsValidationTest,
    "model_thinking_config": TestModelThinkingConfig,
    "o3_model_selection": O3ModelSelectionTest,
    "ollama_custom_url": OllamaCustomUrlTest,
    "openrouter_fallback": OpenRouterFallbackTest,
    "openrouter_models": OpenRouterModelsTest,
    "token_allocation_validation": TokenAllocationValidationTest,
    "vision_capability": VisionCapabilityTest,
    "xai_models": XAIModelsTest,
    "consensus_conversation": TestConsensusConversation,
    "consensus_workflow_accurate": TestConsensusWorkflowAccurate,
    "consensus_three_models": TestConsensusThreeModels,
    "prompt_size_limit_bug": PromptSizeLimitBugTest,
    # "o3_pro_expensive": O3ProExpensiveTest,  # COMMENTED OUT - too expensive to run by default
}

__all__ = [
    "BaseSimulatorTest",
    "BasicConversationTest",
    "ChatSimpleValidationTest",
    "ContentValidationTest",
    "PerToolDeduplicationTest",
    "LineNumberValidationTest",
    "LogsValidationTest",
    "TestModelThinkingConfig",
    "O3ModelSelectionTest",
    "O3ProExpensiveTest",
    "OllamaCustomUrlTest",
    "OpenRouterFallbackTest",
    "OpenRouterModelsTest",
    "TokenAllocationValidationTest",
    "VisionCapabilityTest",
    "XAIModelsTest",
    "TestConsensusConversation",
    "TestConsensusWorkflowAccurate",
    "TestConsensusThreeModels",
    "PromptSizeLimitBugTest",
    "TEST_REGISTRY",
]
