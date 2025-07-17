"""
Zen MCP Server - FastMCP Implementation

This module implements the Zen MCP Server using the modern FastMCP approach
from the official MCP Python SDK. It provides the same functionality as the
original server but with simplified, decorator-based patterns.

Key Features:
- FastMCP decorator-based tool definitions
- Structured output support
- Conversation threading support
- Multi-model provider integration
- Advanced token management
- File handling and context management

The server maintains full compatibility with the original implementation while
leveraging modern MCP patterns for better maintainability and performance.
"""

import atexit
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

# Try to load environment variables from .env file if dotenv is available
try:
    from dotenv import load_dotenv

    script_dir = Path(__file__).parent
    env_file = script_dir / ".env"
    load_dotenv(dotenv_path=env_file)
except ImportError:
    pass

from mcp.server.fastmcp import Context, FastMCP

from config import (
    DEFAULT_MODEL,
    __version__,
)

# Configure logging using the same pattern as the original server
log_level = os.getenv("LOG_LEVEL", "DEBUG").upper()

class LocalTimeFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        """Override to use local timezone instead of UTC"""
        ct = self.converter(record.created)
        if datefmt:
            s = time.strftime(datefmt, ct)
        else:
            t = time.strftime("%Y-%m-%d %H:%M:%S", ct)
            s = f"{t},{record.msecs:03.0f}"
        return s

# Configure logging
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
root_logger = logging.getLogger()
root_logger.handlers.clear()

# Create and configure stderr handler
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(getattr(logging, log_level, logging.INFO))
stderr_handler.setFormatter(LocalTimeFormatter(log_format))
root_logger.addHandler(stderr_handler)
root_logger.setLevel(getattr(logging, log_level, logging.INFO))

# Add rotating file handler
try:
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    file_handler = RotatingFileHandler(
        log_dir / "mcp_server.log",
        maxBytes=20 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, log_level, logging.INFO))
    file_handler.setFormatter(LocalTimeFormatter(log_format))
    root_logger.addHandler(file_handler)

    # MCP activity logger
    mcp_logger = logging.getLogger("mcp_activity")
    mcp_file_handler = RotatingFileHandler(
        log_dir / "mcp_activity.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=2,
        encoding="utf-8",
    )
    mcp_file_handler.setLevel(logging.INFO)
    mcp_file_handler.setFormatter(LocalTimeFormatter("%(asctime)s - %(message)s"))
    mcp_logger.addHandler(mcp_file_handler)
    mcp_logger.setLevel(logging.INFO)
    mcp_logger.propagate = True

    logging.info(f"Logging to: {log_dir / 'mcp_server.log'}")
    logging.info(f"Process PID: {os.getpid()}")

except Exception as e:
    print(f"Warning: Could not set up file logging: {e}", file=sys.stderr)

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("zen-server")

def configure_providers():
    """Configure AI providers - same logic as original server"""
    logger.debug("Checking environment variables for API keys...")
    api_keys_to_check = ["OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY", "CUSTOM_API_URL"]
    for key in api_keys_to_check:
        value = os.getenv(key)
        logger.debug(f"  {key}: {'[PRESENT]' if value else '[MISSING]'}")

    from providers import ModelProviderRegistry
    from providers.base import ProviderType
    from providers.custom import CustomProvider
    from providers.gemini import GeminiModelProvider
    from providers.openai_provider import OpenAIProvider
    from providers.openrouter import OpenRouterProvider
    from providers.xai import XAIModelProvider
    from utils.model_restrictions import get_restriction_service

    valid_providers = []
    has_native_apis = False
    has_openrouter = False
    has_custom = False

    # Check for API keys and register providers (same logic as original)
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your_gemini_api_key_here":
        valid_providers.append("Gemini")
        has_native_apis = True
        logger.info("Gemini API key found - Gemini models available")

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and openai_key != "your_openai_api_key_here":
        valid_providers.append("OpenAI (o3)")
        has_native_apis = True
        logger.info("OpenAI API key found - o3 models available")

    xai_key = os.getenv("XAI_API_KEY")
    if xai_key and xai_key != "your_xai_api_key_here":
        valid_providers.append("X.AI (GROK)")
        has_native_apis = True
        logger.info("X.AI API key found - GROK models available")

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key and openrouter_key != "your_openrouter_api_key_here":
        valid_providers.append("OpenRouter")
        has_openrouter = True
        logger.info("OpenRouter API key found - Multiple models available via OpenRouter")

    custom_url = os.getenv("CUSTOM_API_URL")
    if custom_url:
        custom_key = os.getenv("CUSTOM_API_KEY", "")
        custom_model = os.getenv("CUSTOM_MODEL_NAME", "llama3.2")
        valid_providers.append(f"Custom API ({custom_url})")
        has_custom = True
        logger.info(f"Custom API endpoint found: {custom_url} with model {custom_model}")

    # Register providers in priority order
    if has_native_apis:
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
        if openai_key and openai_key != "your_openai_api_key_here":
            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIProvider)
        if xai_key and xai_key != "your_xai_api_key_here":
            ModelProviderRegistry.register_provider(ProviderType.XAI, XAIModelProvider)

    if has_custom:
        def custom_provider_factory(api_key=None):
            base_url = os.getenv("CUSTOM_API_URL", "")
            return CustomProvider(api_key=api_key or "", base_url=base_url)
        ModelProviderRegistry.register_provider(ProviderType.CUSTOM, custom_provider_factory)

    if has_openrouter:
        ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)

    if not valid_providers:
        raise ValueError(
            "At least one API configuration is required. Please set either:\n"
            "- GEMINI_API_KEY for Gemini models\n"
            "- OPENAI_API_KEY for OpenAI o3 model\n"
            "- XAI_API_KEY for X.AI GROK models\n"
            "- OPENROUTER_API_KEY for OpenRouter (multiple models)\n"
            "- CUSTOM_API_URL for local models (Ollama, vLLM, etc.)"
        )

    logger.info(f"Available providers: {', '.join(valid_providers)}")

    # Register cleanup function
    def cleanup_providers():
        try:
            registry = ModelProviderRegistry()
            if hasattr(registry, "_initialized_providers"):
                for provider in list(registry._initialized_providers.items()):
                    try:
                        if provider and hasattr(provider, "close"):
                            provider.close()
                    except Exception:
                        pass
        except Exception:
            pass

    atexit.register(cleanup_providers)

    # Check and log model restrictions
    restriction_service = get_restriction_service()
    restrictions = restriction_service.get_restriction_summary()

    if restrictions:
        logger.info("Model restrictions configured:")
        for provider_name, allowed_models in restrictions.items():
            if isinstance(allowed_models, list):
                logger.info(f"  {provider_name}: {', '.join(allowed_models)}")
            else:
                logger.info(f"  {provider_name}: {allowed_models}")

        # Validate restrictions
        provider_instances = {}
        provider_types_to_validate = [ProviderType.GOOGLE, ProviderType.OPENAI, ProviderType.XAI]
        for provider_type in provider_types_to_validate:
            provider = ModelProviderRegistry.get_provider(provider_type)
            if provider:
                provider_instances[provider_type] = provider

        if provider_instances:
            restriction_service.validate_against_known_models(provider_instances)
    else:
        logger.info("No model restrictions configured - all models allowed")

    # Check auto mode
    from config import IS_AUTO_MODE
    if IS_AUTO_MODE:
        available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)
        if not available_models:
            logger.error(
                "Auto mode is enabled but no models are available after applying restrictions."
            )
            raise ValueError(
                "No models available for auto mode due to restrictions."
            )

async def handle_conversation_threading(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle conversation threading - bridge to existing conversation memory system"""
    if "continuation_id" not in arguments or not arguments["continuation_id"]:
        return arguments

    # Import the conversation reconstruction logic from original server
    from utils.conversation_memory import add_turn, build_conversation_history, get_thread
    from utils.model_context import ModelContext

    continuation_id = arguments["continuation_id"]
    logger.debug(f"Resuming conversation thread: {continuation_id}")

    # Get thread context
    context = get_thread(continuation_id)
    if not context:
        raise ValueError(
            f"Conversation thread '{continuation_id}' was not found or has expired. "
            f"Please restart the conversation by providing your full question/prompt without the "
            f"continuation_id parameter."
        )

    # Add user's new input to the conversation
    user_prompt = arguments.get("prompt", "")
    if user_prompt:
        user_files = arguments.get("files", [])
        success = add_turn(continuation_id, "user", user_prompt, files=user_files)
        if not success:
            logger.warning(f"Failed to add user turn to thread {continuation_id}")

    # Create model context
    model_from_args = arguments.get("model")
    if not model_from_args and context.turns:
        for turn in reversed(context.turns):
            if turn.role == "assistant" and turn.model_name and turn.tool_name != "consensus":
                arguments["model"] = turn.model_name
                break

    # For consensus tool, handle differently
    if context.tool_name == "consensus" and not arguments.get("model"):
        from providers.registry import ModelProviderRegistry
        fallback_model = ModelProviderRegistry.get_preferred_fallback_model()
        model_context = ModelContext(fallback_model)
    else:
        model_context = ModelContext.from_arguments(arguments)

    # Build conversation history
    conversation_history, conversation_tokens = await build_conversation_history(context, model_context)

    # Generate follow-up instructions
    follow_up_instructions = get_follow_up_instructions(len(context.turns))

    # Enhance prompt with conversation history
    original_prompt = arguments.get("prompt", "")
    if conversation_history:
        enhanced_prompt = (
            f"{conversation_history}\n\n=== NEW USER INPUT ===\n{original_prompt}\n\n{follow_up_instructions}"
        )
    else:
        enhanced_prompt = f"{original_prompt}\n\n{follow_up_instructions}"

    # Update arguments
    enhanced_arguments = arguments.copy()
    enhanced_arguments["prompt"] = enhanced_prompt
    enhanced_arguments["_original_user_prompt"] = original_prompt

    # Calculate remaining token budget
    token_allocation = model_context.calculate_token_allocation()
    remaining_tokens = token_allocation.content_tokens - conversation_tokens
    enhanced_arguments["_remaining_tokens"] = max(0, remaining_tokens)
    enhanced_arguments["_model_context"] = model_context

    # Merge initial context
    if context.initial_context:
        for key, value in context.initial_context.items():
            if key not in enhanced_arguments and key not in ["temperature", "thinking_mode", "model"]:
                enhanced_arguments[key] = value

    logger.info(f"Reconstructed context for thread {continuation_id} (turn {len(context.turns)})")
    return enhanced_arguments

def get_follow_up_instructions(current_turn_count: int, max_turns: int = None) -> str:
    """
    Generate dynamic follow-up instructions based on conversation turn count.

    Args:
        current_turn_count: Current number of turns in the conversation
        max_turns: Maximum allowed turns before conversation ends (defaults to MAX_CONVERSATION_TURNS)

    Returns:
        Follow-up instructions to append to the tool prompt
    """
    if max_turns is None:
        from utils.conversation_memory import MAX_CONVERSATION_TURNS
        max_turns = MAX_CONVERSATION_TURNS

    if current_turn_count >= max_turns - 1:
        # We're at or approaching the turn limit - no more follow-ups
        return """
IMPORTANT: This is approaching the final exchange in this conversation thread.
Do NOT include any follow-up questions in your response. Provide your complete
final analysis and recommendations."""
    else:
        # Normal follow-up instructions
        remaining_turns = max_turns - current_turn_count - 1
        return f"""

CONVERSATION CONTINUATION: You can continue this discussion with Claude! ({remaining_turns} exchanges remaining)

Feel free to ask clarifying questions or suggest areas for deeper exploration naturally within your response.
If something needs clarification or you'd benefit from additional context, simply mention it conversationally.

IMPORTANT: When you suggest follow-ups or ask questions, you MUST explicitly instruct Claude to use the continuation_id
to respond. Use clear, direct language based on urgency:

For optional follow-ups: "Please continue this conversation using the continuation_id from this response if you'd "
"like to explore this further."

For needed responses: "Please respond using the continuation_id from this response - your input is needed to proceed."

For essential/critical responses: "RESPONSE REQUIRED: Please immediately continue using the continuation_id from "
"this response. Cannot proceed without your clarification/input."

This ensures Claude knows both HOW to maintain the conversation thread AND whether a response is optional, "
"needed, or essential.

The tool will automatically provide a continuation_id in the structured response that Claude can use in subsequent
tool calls to maintain full conversation context across multiple exchanges.

Remember: Only suggest follow-ups when they would genuinely add value to the discussion, and always instruct "
"Claude to use the continuation_id when you do."""

def parse_model_option(model_string: str) -> tuple[str, Optional[str]]:
    """Parse model:option format - same logic as original server"""
    if ":" in model_string and not model_string.startswith("http"):
        if "/" in model_string and model_string.count(":") == 1:
            parts = model_string.split(":", 1)
            suffix = parts[1].strip().lower()
            if suffix in ["free", "beta", "preview"]:
                return model_string.strip(), None

        parts = model_string.split(":", 1)
        model_name = parts[0].strip()
        model_option = parts[1].strip() if len(parts) > 1 else None
        return model_name, model_option
    return model_string.strip(), None

async def resolve_model_and_validate(arguments: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    """Resolve model and validate availability - same logic as original server"""
    from providers.registry import ModelProviderRegistry
    from utils.file_utils import check_total_file_size
    from utils.model_context import ModelContext

    # Get model from arguments or use default
    model_name = arguments.get("model") or DEFAULT_MODEL
    model_name, model_option = parse_model_option(model_name)

    # Handle auto mode
    if model_name.lower() == "auto":
        # Get appropriate model for tool category
        from tools import ChatTool, ConsensusTool
        if tool_name == "chat":
            tool_category = ChatTool().get_model_category()
        elif tool_name == "consensus":
            tool_category = ConsensusTool().get_model_category()
        else:
            from providers.base import ModelCategory
            tool_category = ModelCategory.CODING

        resolved_model = ModelProviderRegistry.get_preferred_fallback_model(tool_category)
        logger.info(f"Auto mode resolved to {resolved_model} for {tool_name}")
        model_name = resolved_model
        arguments["model"] = model_name

    # Skip validation for consensus tool (handles its own models)
    if tool_name == "consensus":
        return arguments

    # Validate model availability
    provider = ModelProviderRegistry.get_provider_for_model(model_name)
    if not provider:
        available_models = list(ModelProviderRegistry.get_available_models(respect_restrictions=True).keys())
        from tools import ChatTool
        tool_category = ChatTool().get_model_category()
        suggested_model = ModelProviderRegistry.get_preferred_fallback_model(tool_category)

        error_message = (
            f"Model '{model_name}' is not available with current API keys. "
            f"Available models: {', '.join(available_models)}. "
            f"Suggested model for {tool_name}: '{suggested_model}'"
        )
        raise ValueError(error_message)

    # Create model context
    model_context = ModelContext(model_name, model_option)
    arguments["_model_context"] = model_context
    arguments["_resolved_model_name"] = model_name

    # File size validation
    if "files" in arguments and arguments["files"]:
        file_size_check = check_total_file_size(arguments["files"], model_name)
        if file_size_check:
            raise ValueError(f"File size validation failed: {file_size_check['content']}")

    return arguments

@mcp.tool()
async def chat(
    prompt: str,
    model: str = "auto",
    files: Optional[List[str]] = None,
    continuation_id: Optional[str] = None,
    temperature: Optional[float] = None,
    use_websearch: bool = True,
    reasoning_effort: str = "medium",
    ctx: Context = None
) -> str:
    """
    Chat with AI models for general conversation, brainstorming, and assistance.
    
    This tool provides interactive conversational AI capabilities with support for:
    - Multiple AI model providers (Gemini, OpenAI, X.AI, OpenRouter, Custom)
    - File context integration
    - Conversation threading for multi-turn exchanges
    - Web search integration for up-to-date information
    - Configurable reasoning effort levels
    
    Args:
        prompt: Your question or message to the AI
        model: AI model to use (default: "auto" for automatic selection)
        files: List of file paths to include as context
        continuation_id: ID to continue previous conversation thread
        temperature: Response randomness (0.0-1.0, default varies by model)
        use_websearch: Enable web search for current information
        reasoning_effort: Depth of reasoning ("minimal", "low", "medium", "high", "max")
        ctx: FastMCP context (automatically provided)
    
    Returns:
        AI response as formatted text with optional continuation offer
    """
    logger.info(f"Chat tool called with model: {model}")

    # Build arguments dictionary
    arguments = {
        "prompt": prompt,
        "model": model,
        "files": files or [],
        "continuation_id": continuation_id,
        "temperature": temperature,
        "use_websearch": use_websearch,
        "reasoning_effort": reasoning_effort,
    }

    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}

    try:
        # Handle conversation threading
        arguments = await handle_conversation_threading(arguments)

        # Resolve model and validate
        arguments = await resolve_model_and_validate(arguments, "chat")

        # Execute chat tool
        from tools import ChatTool
        chat_tool = ChatTool()
        result = await chat_tool.execute(arguments)

        # Extract text content from result
        if result and len(result) > 0:
            return result[0].text
        else:
            return "No response generated"

    except Exception as e:
        logger.error(f"Chat tool error: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def consensus(
    prompt: str,
    models: List[Dict[str, str]],
    relevant_files: Optional[List[str]] = None,
    continuation_id: Optional[str] = None,
    enable_cross_feedback: bool = True,
    cross_feedback_prompt: Optional[str] = None,
    temperature: float = 0.2,
    ctx: Context = None
) -> Dict[str, Any]:
    """
    Gather consensus from multiple AI models with parallel execution and cross-model feedback.
    
    This tool enables multi-model consensus gathering with:
    - Parallel model execution for speed
    - Cross-model feedback and refinement
    - Structured output with both initial and refined responses
    - Robust error handling for partial failures
    - Conversation threading support
    
    Args:
        prompt: The question or problem to gather consensus on
        models: List of model configurations [{"model": "model_name"}, ...]
        relevant_files: List of file paths to include as context
        continuation_id: ID to continue previous conversation thread
        enable_cross_feedback: Enable refinement phase where models see others' responses
        cross_feedback_prompt: Custom prompt for refinement phase
        temperature: Response randomness (0.0-1.0, default: 0.2 for focused responses)
        ctx: FastMCP context (automatically provided)
    
    Returns:
        Structured consensus result with initial and refined responses from all models
    """
    logger.info(f"Consensus tool called with {len(models)} models")

    # Build arguments dictionary
    arguments = {
        "prompt": prompt,
        "models": models,
        "relevant_files": relevant_files or [],
        "continuation_id": continuation_id,
        "enable_cross_feedback": enable_cross_feedback,
        "cross_feedback_prompt": cross_feedback_prompt,
        "temperature": temperature,
    }

    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}

    try:
        # Handle conversation threading
        arguments = await handle_conversation_threading(arguments)

        # Consensus tool handles its own model validation
        # No need to call resolve_model_and_validate

        # Execute consensus tool
        from tools import ConsensusTool
        consensus_tool = ConsensusTool()
        result = await consensus_tool.execute(arguments)

        # Parse JSON result
        if result and len(result) > 0:
            import json
            try:
                return json.loads(result[0].text)
            except json.JSONDecodeError:
                return {"error": "Failed to parse consensus result", "raw_result": result[0].text}
        else:
            return {"error": "No consensus result generated"}

    except Exception as e:
        logger.error(f"Consensus tool error: {e}")
        return {"error": str(e)}

@mcp.tool()
async def test_custom_openai(ctx: Context = None) -> str:
    """
    Test tool for CustomOpenAI provider with 150k character payload.
    
    This tool tests the CustomOpenAI provider with a large payload to verify
    it doesn't deadlock on large inputs. It uses o3-mini model directly.
    """
    try:
        # Execute test tool
        from tools.test_custom_openai import TestCustomOpenAITool
        test_tool = TestCustomOpenAITool()
        result = await test_tool.execute({})
        
        # Parse JSON result and return as formatted string
        if result and len(result) > 0:
            import json
            try:
                result_data = json.loads(result[0].text)
                
                # Format the result as a readable string
                if result_data.get("status") == "success":
                    metadata = result_data.get("metadata", {})
                    return f"""CustomOpenAI Provider Test Results:

Status: ✅ SUCCESS
Model: {metadata.get('model', 'o3-mini')}
Provider: {metadata.get('provider', 'CustomOpenAI')}
Prompt Length: {metadata.get('prompt_length', 'unknown'):,} characters
Response Length: {metadata.get('response_length', 'unknown'):,} characters
Response Time: {metadata.get('response_time', 'unknown'):.2f} seconds
Tokens Used: {metadata.get('tokens_used', {}).get('total_tokens', 'unknown')}

The CustomOpenAI provider successfully processed a large payload without deadlocking.

Response Content:
{result_data.get('content', 'No content available')}"""
                else:
                    # Error case
                    return f"""CustomOpenAI Provider Test Results:

Status: ❌ ERROR
Error: {result_data.get('content', 'Unknown error')}

The test failed. Check the error details above."""
                    
            except json.JSONDecodeError:
                return f"Error: Failed to parse test result.\nRaw result: {result[0].text}"
        else:
            return "Error: No test result generated"
    
    except Exception as e:
        logger.error(f"Test custom openai tool error: {e}")
        return f"Error: {str(e)}"

@mcp.prompt(title="Chat Prompt")
def chat_prompt(topic: str = "general") -> str:
    """Generate a chat prompt for the specified topic"""
    return f"Let's chat about {topic}. What would you like to discuss?"

@mcp.prompt(title="Consensus Prompt")
def consensus_prompt(question: str = "a complex decision") -> str:
    """Generate a consensus prompt for multi-model analysis"""
    return f"Let's gather consensus on {question} using multiple AI models for diverse perspectives."

def run():
    """Main entry point for the server - used by uvx and script installations"""
    try:
        # Configure providers
        configure_providers()

        # Log startup
        logger.info("Zen FastMCP Server starting up...")
        logger.info(f"Log level: {log_level}")
        logger.info(f"Server version: {__version__}")

        from config import IS_AUTO_MODE
        if IS_AUTO_MODE:
            logger.info("Model mode: AUTO (Claude will select the best model for each task)")
        else:
            logger.info(f"Model mode: Fixed model '{DEFAULT_MODEL}'")

        logger.info("Available tools: chat, consensus, test_custom_openai")
        logger.info("Server ready - waiting for tool requests...")

        # Run the FastMCP server with default transport
        mcp.run()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    run()
