"""
Consensus tool - Parallel multi-model consensus with cross-model feedback

This tool provides a structured workflow for gathering consensus from multiple models.
It sends the initial prompt to all models in parallel, then allows each model to see
the others' responses and refine their answer based on the collective insights.

Key features:
- Parallel model consultation for faster execution
- Two-phase approach: initial responses + refinement based on cross-model feedback
- Context-aware file embedding
- Comprehensive responses showing both initial and refined perspectives
- Robust error handling - if one model fails, others continue
"""

from __future__ import annotations

import asyncio
import json
import logging

# Global lock for thread extraction to prevent race conditions
_extraction_lock = asyncio.Lock()
# Semaphore to limit concurrent asyncio.to_thread operations
# Set to 5 to handle up to 5 models in parallel (common use case)
# This prevents thread exhaustion while allowing sufficient parallelism
_thread_semaphore = asyncio.Semaphore(5)

# Custom thread pool executor to avoid default pool exhaustion
import concurrent.futures
_thread_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=10,
    thread_name_prefix="consensus-worker"
)

import os
import time
from typing import TYPE_CHECKING, Any

from pydantic import Field, model_validator

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from mcp.types import TextContent

from systemprompts import CONSENSUS_PROMPT
from tools.shared.base_models import ToolRequest

from .simple.base import SimpleTool

logger = logging.getLogger(__name__)

# Tool-specific field descriptions for consensus
CONSENSUS_FIELD_DESCRIPTIONS = {
    "prompt": "The problem or proposal to gather consensus on. Include context.",
    "models": "List of models to consult. Example: [{'model': 'o3'}, {'model': 'flash'}]",
    "relevant_files": "Optional files for additional context (absolute paths).",
    "images": "Optional images for visual context (absolute paths or base64).",
    "enable_cross_feedback": "Enable refinement phase where models see others' responses. Default: True.",
    "cross_feedback_prompt": "Optional custom prompt for refinement phase.",
}


class ConsensusRequest(ToolRequest):
    """Request model for consensus tool"""

    model_config = {"extra": "allow"}  # Allow extra fields like _original_user_prompt

    # Required fields
    prompt: str = Field(..., description=CONSENSUS_FIELD_DESCRIPTIONS["prompt"])
    models: list[dict] = Field(..., description=CONSENSUS_FIELD_DESCRIPTIONS["models"])

    # Optional fields
    relevant_files: list[str] | None = Field(
        default_factory=list,
        description=CONSENSUS_FIELD_DESCRIPTIONS["relevant_files"],
    )
    images: list[str] | None = Field(default=None, description=CONSENSUS_FIELD_DESCRIPTIONS["images"])
    enable_cross_feedback: bool = Field(
        default=True,
        description=CONSENSUS_FIELD_DESCRIPTIONS["enable_cross_feedback"],
    )
    cross_feedback_prompt: str | None = Field(
        default=None,
        description=CONSENSUS_FIELD_DESCRIPTIONS["cross_feedback_prompt"],
    )
    temperature: float | None = Field(
        0.2,
        ge=0.0,
        le=1.0,
        description="Temperature for response (0.0 to 1.0). Default: 0.2 for analytical/focused responses.",
    )

    @model_validator(mode="after")
    def validate_consensus_requirements(self):
        """Ensure consensus request has required models field."""
        if not self.models or len(self.models) == 0:
            raise ValueError("Consensus requires at least one model in 'models' field")
        return self


class ConsensusTool(SimpleTool):
    """
    Parallel consensus tool with cross-model feedback.

    This tool implements a two-phase consensus workflow:
    1. Initial Phase: Consults all specified models in parallel with the same prompt
    2. Refinement Phase: Each model sees others' responses and can refine their answer

    All processing happens in a single tool call, returning both initial and refined responses.
    Robust error handling ensures that if one model fails, others continue processing.
    """

    def __init__(self):
        super().__init__()
        self.initial_prompt: str | None = None
        self.models_to_consult: list[dict] = []
        # Cache for model timeouts to prevent repeated get_capabilities calls
        self._timeout_cache: dict[str, float] = {}

    def get_name(self) -> str:
        return "consensus"

    def get_description(self) -> str:
        return (
            "PARALLEL CONSENSUS WITH CROSS-MODEL FEEDBACK - Gathers perspectives from multiple AI models simultaneously. "
            "Models provide initial responses, then optionally refine based on others' insights. "
            "Returns both phases in a single call. Handles partial failures gracefully. "
            "For: complex decisions, architectural choices, technical evaluations."
        )

    def get_system_prompt(self) -> str:
        # Return the consensus prompt without stance placeholder
        return CONSENSUS_PROMPT

    def get_default_temperature(self) -> float:
        # Default is now defined in ConsensusRequest model
        return 0.2

    def get_model_category(self) -> ToolModelCategory:
        """Consensus workflow requires extended reasoning"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def get_request_model(self):
        """Return the consensus-specific request model."""
        return ConsensusRequest

    def get_input_schema(self) -> dict[str, Any]:
        """Generate input schema for consensus tool."""
        schema = {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": CONSENSUS_FIELD_DESCRIPTIONS["prompt"],
                },
                "models": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "model": {"type": "string"},
                        },
                        "required": ["model"],
                    },
                    "description": CONSENSUS_FIELD_DESCRIPTIONS["models"],
                },
                "relevant_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": CONSENSUS_FIELD_DESCRIPTIONS["relevant_files"],
                },
                "images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": CONSENSUS_FIELD_DESCRIPTIONS["images"],
                },
                "enable_cross_feedback": {
                    "type": "boolean",
                    "default": True,
                    "description": CONSENSUS_FIELD_DESCRIPTIONS["enable_cross_feedback"],
                },
                "cross_feedback_prompt": {
                    "type": "string",
                    "description": CONSENSUS_FIELD_DESCRIPTIONS["cross_feedback_prompt"],
                },
                "continuation_id": {
                    "type": "string",
                    "description": "Thread continuation ID for multi-turn conversations.",
                },
                "temperature": {
                    "type": "number",
                    "description": "Temperature for response (0.0 to 1.0). Default: 0.2 for analytical/focused responses.",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.2,
                },
            },
            "required": ["prompt", "models"],
        }
        return schema

    def requires_model(self) -> bool:
        """
        Consensus tool doesn't require model resolution at the MCP boundary.

        Uses it's own set of models

        Returns:
            bool: False
        """
        return False

    def _get_consensus_timeout(self) -> float:
        """Get the timeout for consensus model calls.

        Uses environment variable CONSENSUS_MODEL_TIMEOUT if set, otherwise defaults to 10 minutes.
        This is separate from provider-level HTTP timeouts and specifically controls how long
        to wait for each model in the consensus workflow.

        Returns:
            float: Timeout in seconds
        """
        default_timeout = 600.0  # 10 minutes default
        timeout_str = os.getenv("CONSENSUS_MODEL_TIMEOUT", str(default_timeout))

        try:
            timeout = float(timeout_str)
            if timeout <= 0:
                logger.warning(
                    f"Invalid CONSENSUS_MODEL_TIMEOUT value ({timeout}), using default of {default_timeout} seconds"
                )
                return default_timeout
            return timeout
        except (ValueError, TypeError):
            logger.warning(
                f"Invalid CONSENSUS_MODEL_TIMEOUT value ('{timeout_str}'), using default of {default_timeout} seconds"
            )
            return default_timeout

    def _get_model_timeout(self, model_name: str) -> float:
        """Get model-specific timeout from capabilities.

        Uses the timeout defined in model capabilities if available,
        otherwise falls back to consensus timeout. Caches results to prevent
        repeated get_capabilities calls that can cause deadlocks.

        Args:
            model_name: The model name to get timeout for

        Returns:
            float: Timeout in seconds for this specific model
        """
        # Check cache first
        if model_name in self._timeout_cache:
            logger.debug(f"[CONSENSUS] Using cached timeout for {model_name}: {self._timeout_cache[model_name]}s")
            return self._timeout_cache[model_name]
        
        logger.debug(f"[CONSENSUS] Getting timeout for model {model_name} (not cached)")
        timeout = self._get_consensus_timeout()  # Default fallback
        
        try:
            # Get the provider for this model
            provider = self.get_model_provider(model_name)
            logger.debug(f"[CONSENSUS] Got provider for {model_name}: {provider}")
            if provider:
                # Get model capabilities which include timeout
                logger.debug(f"[CONSENSUS] Getting capabilities for {model_name}")
                capabilities = provider.get_capabilities(model_name)
                logger.debug(f"[CONSENSUS] Got capabilities for {model_name}: {capabilities}")
                if hasattr(capabilities, "timeout"):
                    timeout = capabilities.timeout
                    # Log if using extended timeout
                    if timeout > 300:  # More than 5 minutes
                        logger.info(f"Using extended timeout of {timeout}s for model {model_name}")
        except Exception as e:
            logger.debug(f"Could not get model-specific timeout for {model_name}: {e}")

        # Cache the result
        self._timeout_cache[model_name] = timeout
        logger.debug(f"[CONSENSUS] Cached timeout for {model_name}: {timeout}s")
        return timeout

    def _get_phase_timeout(self, model_configs: list[dict]) -> float:
        """Calculate appropriate timeout for a consensus phase.

        Takes the maximum timeout among all models being consulted
        and adds a buffer for coordination overhead.

        Args:
            model_configs: List of model configurations being consulted

        Returns:
            float: Phase timeout in seconds
        """
        # Get the maximum timeout needed among all models
        max_model_timeout = 0.0
        for config in model_configs:
            model_name = config.get("model", "")
            model_timeout = self._get_model_timeout(model_name)
            max_model_timeout = max(max_model_timeout, model_timeout)

        # Add 60 second buffer for coordination overhead
        phase_timeout = max_model_timeout + 60.0
        logger.debug(
            f"Phase timeout calculated: {phase_timeout}s (max model timeout: {max_model_timeout}s + 60s buffer)"
        )
        return phase_timeout

    async def execute(self, arguments: dict[str, Any]) -> list:
        """Execute parallel consensus with optional cross-model feedback."""
        logger.debug(f"[CONSENSUS] Execute called with continuation_id: {arguments.get('continuation_id', 'None')}")
        
        # Clear timeout cache for fresh execution
        self._timeout_cache.clear()
        logger.debug("[CONSENSUS] Cleared timeout cache for new execution")

        # Validate request
        request = self.get_request_model()(**arguments)

        # Store initial state
        # Use original user prompt to avoid duplication when server adds conversation history
        # The server enhances 'prompt' with full conversation history for continuations,
        # but consensus tool adds its own model-specific history, so we need just the user's new question
        self.initial_prompt = getattr(request, "_original_user_prompt", None) or request.prompt
        self.models_to_consult = request.models
        logger.debug(
            f"[CONSENSUS] Initial prompt length: {len(self.initial_prompt)} chars, consulting {len(self.models_to_consult)} models"
        )

        try:
            # Phase 1: Parallel initial model consultations
            logger.info(f"Starting parallel consensus for {len(self.models_to_consult)} models")

            # Get providers and create model contexts before async tasks to avoid concurrent access
            from utils.model_context import ModelContext
            
            # Get system prompt once for all models
            system_prompt = self.get_system_prompt()
            logger.debug(f"[CONSENSUS] System prompt length: {len(system_prompt)} chars")
            
            model_resources = []
            for model_config in self.models_to_consult:
                model_name = model_config.get("model")
                provider = self.get_model_provider(model_name)
                model_context = ModelContext(model_name)
                model_resources.append((model_config, provider, model_context))
                logger.debug(f"[CONSENSUS] Pre-created resources for {model_name}")
            
            # Create tasks as coroutines for better control
            initial_tasks = [
                asyncio.create_task(self._consult_model(
                    model_config, request, phase="initial", provider=provider, 
                    model_context=model_context, system_prompt=system_prompt
                ))
                for model_config, provider, model_context in model_resources
            ]

            # Calculate phase timeout based on model requirements
            phase_timeout = self._get_phase_timeout(self.models_to_consult)
            logger.info(f"Phase 1 timeout set to {phase_timeout}s")

            # Execute all initial consultations in parallel with phase timeout
            # Using asyncio.wait() to preserve partial results on timeout
            done, pending = await asyncio.wait(initial_tasks, timeout=phase_timeout)

            # Cancel any pending tasks
            for task in pending:
                task.cancel()

            # Process results and handle any errors
            successful_initial = []
            failed_models = []

            # Build ordered responses list to maintain original model order
            ordered_responses = []
            for i, task in enumerate(initial_tasks):
                if task in done:
                    try:
                        result = task.result()
                        ordered_responses.append(result)
                    except Exception as e:
                        ordered_responses.append(e)
                else:  # task in pending (timed out)
                    model_name = self.models_to_consult[i].get("model", "unknown")
                    timeout_error = TimeoutError(f"Phase timeout exceeded ({phase_timeout}s) for model {model_name}")
                    ordered_responses.append(timeout_error)

            # Now process ordered responses as before
            for i, response in enumerate(ordered_responses):
                if isinstance(response, Exception):
                    model_name = self.models_to_consult[i].get("model", "unknown")
                    error_msg = str(response)

                    if isinstance(response, TimeoutError):
                        logger.warning(f"Model {model_name} failed: {error_msg}")
                    else:
                        logger.error(f"Model {model_name} failed: {error_msg}")

                    failed_models.append(
                        {
                            "model": model_name,
                            "error": error_msg,
                            "phase": "initial",
                        }
                    )
                else:
                    successful_initial.append(response)

            # Phase 2: Cross-model feedback (if enabled and we have multiple successful responses)
            refined_responses = []
            if request.enable_cross_feedback and len(successful_initial) > 1:
                logger.info(f"Starting cross-model feedback phase for {len(successful_initial)} models")

                refinement_tasks = []
                for i, response in enumerate(successful_initial):
                    if response.get("status") == "success":
                        # Get other models' responses (excluding this model's own response)
                        other_responses = [
                            r for j, r in enumerate(successful_initial) if j != i and r.get("status") == "success"
                        ]

                        # Find the original model config for this response
                        model_config = None
                        for mc in self.models_to_consult:
                            if mc.get("model") == response.get("model"):
                                model_config = mc
                                break

                        if model_config and other_responses:
                            logger.debug(f"[CONSENSUS] Creating refinement task for {model_config.get('model')}")
                            # Get provider before creating async task to avoid concurrent registry access
                            provider = self.get_model_provider(model_config.get("model"))
                            refinement_tasks.append(
                                self._consult_model_with_feedback(
                                    model_config, request, response, other_responses, 
                                    phase="refinement", provider=provider, system_prompt=system_prompt
                                )
                            )
                            logger.debug(f"[CONSENSUS] Refinement task created for {model_config.get('model')}")

                # Execute refinement tasks in parallel with phase timeout
                if refinement_tasks:
                    # Create tasks for better control
                    refinement_coroutines = [asyncio.create_task(task) for task in refinement_tasks]

                    # Calculate timeout for refinement phase
                    # Use the same models that succeeded in initial phase
                    refinement_model_configs = [
                        mc
                        for mc in self.models_to_consult
                        if any(
                            r.get("model") == mc.get("model")
                            for r in successful_initial
                            if r.get("status") == "success"
                        )
                    ]
                    refinement_timeout = self._get_phase_timeout(refinement_model_configs)
                    logger.info(f"Phase 2 (refinement) timeout set to {refinement_timeout}s")

                    # Wait with timeout
                    done, pending = await asyncio.wait(refinement_coroutines, timeout=refinement_timeout)

                    # Cancel any pending tasks
                    for task in pending:
                        task.cancel()
                        logger.warning("Refinement task timed out at phase level")

                    # Process completed refinement tasks
                    for task in done:
                        try:
                            result = task.result()
                            refined_responses.append(result)
                        except Exception as e:
                            logger.error(f"Refinement phase error: {e}")
                            # Continue without this refinement

            # Prepare final responses - use refined if available, otherwise initial
            final_responses = []

            # Build a map of refined responses by model name for easy lookup
            refined_by_model = {r["model"]: r for r in refined_responses if r.get("status") == "success"}

            # For each successful initial response, use refined if available
            for initial in successful_initial:
                if initial.get("status") == "success":
                    model_name = initial["model"]
                    if model_name in refined_by_model:
                        # Use refined response but with combined metadata
                        refined = refined_by_model[model_name]
                        # Combine metadata to show both initial and refinement times
                        combined_metadata = initial["metadata"].copy()
                        combined_metadata.update(
                            {
                                "initial_response_time": initial["metadata"]["response_time"],
                                "refinement_response_time": refined["metadata"]["response_time"],
                                "total_response_time": initial["metadata"]["response_time"]
                                + refined["metadata"]["response_time"],
                                "input_tokens_initial": initial["metadata"].get("input_tokens", 0),
                                "output_tokens_initial": initial["metadata"].get("output_tokens", 0),
                                "input_tokens_refinement": refined["metadata"].get("input_tokens", 0),
                                "output_tokens_refinement": refined["metadata"].get("output_tokens", 0),
                                "total_input_tokens": initial["metadata"].get("input_tokens", 0)
                                + refined["metadata"].get("input_tokens", 0),
                                "total_output_tokens": initial["metadata"].get("output_tokens", 0)
                                + refined["metadata"].get("output_tokens", 0),
                            }
                        )
                        # Remove the single response_time, input_tokens, and output_tokens fields
                        combined_metadata.pop("response_time", None)
                        combined_metadata.pop("input_tokens", None)
                        combined_metadata.pop("output_tokens", None)

                        final_responses.append(
                            {
                                "model": model_name,
                                "status": "success",
                                "response": refined["refined_response"],
                                "metadata": combined_metadata,
                            }
                        )
                    else:
                        # Use initial response - rename response_time to initial_response_time for consistency
                        metadata = initial["metadata"].copy()
                        if "response_time" in metadata:
                            metadata["initial_response_time"] = metadata.pop("response_time")
                            metadata["total_response_time"] = metadata["initial_response_time"]
                        final_responses.append(
                            {
                                "model": model_name,
                                "status": "success",
                                "response": initial["response"],
                                "metadata": metadata,
                            }
                        )

            # Prepare comprehensive response
            response_data = {
                "status": "consensus_complete",
                "consensus_complete": True,
                "initial_prompt": self.initial_prompt,
                "models_consulted": len(self.models_to_consult),
                "successful_responses": len(final_responses),
                "failed_models": failed_models,
                "cross_feedback_enabled": request.enable_cross_feedback,
                "responses": final_responses,
                "next_steps": (
                    "PARALLEL CONSENSUS GATHERING IS COMPLETE. Please synthesize the responses:\n"
                    "1. Review the responses from all models\n"
                    "2. Identify key points of AGREEMENT across models\n"
                    "3. Note key points of DISAGREEMENT and underlying reasons\n"
                    "4. Provide your final recommendation based on the collective insights\n"
                    "5. Suggest specific, actionable next steps"
                ),
                "metadata": {
                    "tool_name": self.get_name(),
                    "workflow_type": "parallel_consensus_with_feedback" if refined_responses else "parallel_consensus",
                    "total_models": len(self.models_to_consult),
                    "successful_models": len(final_responses),
                    "models_with_refinements": len(refined_responses),
                },
            }

            # Handle continuation - store consensus result and create continuation offer
            continuation_offer = None
            if len(final_responses) > 0:  # Only offer continuation if we have successful responses
                # Store the consensus result in conversation memory
                from utils.conversation_memory import MAX_CONVERSATION_TURNS, add_turn, create_thread, get_thread

                if request.continuation_id:
                    # Continuing existing conversation
                    thread_context = await asyncio.to_thread(get_thread, request.continuation_id)
                    if thread_context and thread_context.turns:
                        turn_count = len(thread_context.turns)
                        if turn_count < MAX_CONVERSATION_TURNS - 1:
                            # Add consensus result as assistant turn
                            # Store actual model names instead of "n models"
                            consulted_models = [r["model"] for r in final_responses if r.get("status") == "success"]
                            model_names_str = (
                                ", ".join(consulted_models) if consulted_models else "no successful models"
                            )

                            # Format storage content in thread pool
                            formatted_content = await asyncio.to_thread(
                                self._format_consensus_for_storage, response_data
                            )
                            
                            await asyncio.to_thread(
                                add_turn,
                                request.continuation_id,
                                "assistant",
                                formatted_content,
                                tool_name="consensus",
                                model_provider="multi-model-consensus",
                                model_name=model_names_str,
                                model_metadata={
                                    "consensus_data": {
                                        "responses": [
                                            {
                                                "model": r["model"],
                                                "response": r["response"],
                                                "status": r["status"]
                                            }
                                            for r in final_responses
                                        ]
                                    },
                                    "consulted_models": consulted_models
                                },
                            )

                            remaining_turns = MAX_CONVERSATION_TURNS - turn_count - 1
                            continuation_offer = {
                                "continuation_id": request.continuation_id,
                                "remaining_turns": remaining_turns,
                                "note": f"Claude can continue this conversation for {remaining_turns} more exchanges.",
                            }
                else:
                    # New conversation - create thread
                    # Convert request to dict for initial_context
                    initial_request_dict = {
                        "prompt": request.prompt,
                        "models": request.models,
                        "relevant_files": request.relevant_files,
                        "enable_cross_feedback": request.enable_cross_feedback,
                        "temperature": request.temperature,
                        "reasoning_effort": request.reasoning_effort,
                    }

                    new_thread_id = await asyncio.to_thread(
                        create_thread, tool_name="consensus", initial_request=initial_request_dict
                    )

                    # Add user's initial turn
                    await asyncio.to_thread(
                        add_turn,
                        new_thread_id,
                        "user",
                        request.prompt,
                        files=request.relevant_files,
                        images=request.images,
                        tool_name="consensus",
                    )

                    # Add consensus result as assistant turn
                    # Store actual model names instead of "n models"
                    consulted_models = [r["model"] for r in final_responses if r.get("status") == "success"]
                    model_names_str = ", ".join(consulted_models) if consulted_models else "no successful models"

                    # Format storage content in thread pool
                    formatted_content = await asyncio.to_thread(
                        self._format_consensus_for_storage, response_data
                    )
                    
                    await asyncio.to_thread(
                        add_turn,
                        new_thread_id,
                        "assistant",
                        formatted_content,
                        tool_name="consensus",
                        model_provider="multi-model-consensus",
                        model_name=model_names_str,
                        model_metadata={
                            "consensus_data": {
                                "responses": [
                                    {
                                        "model": r["model"],
                                        "response": r["response"],
                                        "status": r["status"]
                                    }
                                    for r in final_responses
                                ]
                            },
                            "consulted_models": consulted_models
                        },
                    )

                    continuation_offer = {
                        "continuation_id": new_thread_id,
                        "remaining_turns": MAX_CONVERSATION_TURNS - 1,
                        "note": f"Claude can continue this conversation for {MAX_CONVERSATION_TURNS - 1} more exchanges.",
                    }

            # Add continuation offer to response if available
            if continuation_offer:
                response_data["continuation_offer"] = continuation_offer

            # Serialize response data in thread pool to avoid blocking
            json_response = await asyncio.to_thread(
                json.dumps, response_data, indent=2, ensure_ascii=False
            )
            return [TextContent(type="text", text=json_response)]

        except Exception as e:
            logger.exception("Error in consensus workflow execution")
            error_response = {
                "status": "error",
                "error": str(e),
                "metadata": {"tool_name": self.get_name(), "workflow_type": "parallel_consensus"},
            }
            # Serialize error response in thread pool
            json_error = await asyncio.to_thread(
                json.dumps, error_response, indent=2, ensure_ascii=False
            )
            return [TextContent(type="text", text=json_error)]

    async def _consult_model(self, model_config: dict, request, phase: str = "initial", provider=None, model_context=None, system_prompt=None) -> dict:
        """Consult a single model and return its response."""
        try:
            # Get the provider for this model
            model_name = model_config["model"]
            logger.debug(f"[CONSENSUS] Starting consultation of model {model_name} in {phase} phase")

            if provider is None:
                provider = self.get_model_provider(model_name)
            logger.debug(
                f"[CONSENSUS] Got provider {provider.get_provider_type().value if provider else 'None'} for model {model_name}"
            )

            # Create model context for this specific model if not provided
            if model_context is None:
                from utils.model_context import ModelContext
                logger.debug(f"[CONSENSUS] Creating ModelContext for {model_name}")
                model_context = ModelContext(model_name)
                logger.debug(f"[CONSENSUS] ModelContext created for {model_name}")
            else:
                logger.debug(f"[CONSENSUS] Using pre-created ModelContext for {model_name}")

            # Prepare the prompt with any relevant files
            prompt = self.initial_prompt
            logger.debug(f"[CONSENSUS] Initial prompt length: {len(prompt)} chars")

            # Add model-specific continuation history for initial phase only
            if request.continuation_id and phase == "initial":
                logger.debug(f"[CONSENSUS] Building model-specific history for {model_name}")
                model_history = self._build_model_specific_history(model_name, request.continuation_id, request.models)

                if model_history:
                    prompt = f"{model_history}\n\nNEW QUESTION:\n{prompt}"
                    logger.debug(f"[CONSENSUS] Prompt with history length: {len(prompt)} chars")

            if request.relevant_files:
                logger.debug(f"[CONSENSUS] Preparing file content for {len(request.relevant_files)} files")
                file_content, _ = await self._prepare_file_content_for_prompt(
                    request.relevant_files,
                    request.continuation_id,
                    "Context files",
                    model_context=model_context,
                )
                if file_content:
                    prompt = f"{prompt}\n\n=== CONTEXT FILES ===\n{file_content}\n=== END CONTEXT ==="
                    logger.debug(f"[CONSENSUS] Prompt with files length: {len(prompt)} chars")

            # Use the consensus system prompt if not provided
            if system_prompt is None:
                system_prompt = self.get_system_prompt()
                logger.debug(f"[CONSENSUS] System prompt length: {len(system_prompt)} chars")
            else:
                logger.debug(f"[CONSENSUS] Using pre-fetched system prompt")

            # Validate prompt size using the standard validation method
            combined_prompt = f"{system_prompt}\n\n{prompt}"
            try:
                self._validate_token_limit(combined_prompt, f"Consensus prompt for {model_name}")
            except ValueError as e:
                logger.error(f"[CONSENSUS] Prompt too large for {model_name}: {e}")
                # Truncate the conversation history to fit within limits
                truncated_prompt = f"[Previous conversation history truncated due to size limits]\n\nNEW QUESTION:\n{self.initial_prompt}"
                if request.relevant_files and file_content:
                    truncated_prompt = (
                        f"{truncated_prompt}\n\n=== CONTEXT FILES ===\n{file_content}\n=== END CONTEXT ==="
                    )

                # Try again with truncated prompt
                combined_prompt = f"{system_prompt}\n\n{truncated_prompt}"
                try:
                    self._validate_token_limit(combined_prompt, f"Truncated consensus prompt for {model_name}")
                    prompt = truncated_prompt
                    logger.info(f"[CONSENSUS] Using truncated prompt for {model_name}")
                except ValueError as e2:
                    # Even truncated prompt is too large, likely due to files
                    logger.error(f"[CONSENSUS] Even truncated prompt too large: {e2}")
                    raise ValueError(f"Unable to fit prompt within token limits for {model_name}: {e2}")

            # Call the model with timing and pass timeout to provider (use asyncio.to_thread for parallel execution)
            start_time = time.time()
            model_timeout = self._get_model_timeout(model_name)
            logger.debug(f"[CONSENSUS] Calling {model_name} with timeout {model_timeout}s")

            # Use semaphore to limit concurrent thread operations
            async with _thread_semaphore:
                # Get current event loop
                loop = asyncio.get_event_loop()
                
                try:
                    # Use custom thread pool executor instead of default
                    # Create a wrapper function to pass timeout as keyword argument
                    def generate_with_timeout():
                        return provider.generate_content(
                            prompt,
                            model_name,
                            system_prompt,
                            request.temperature if request.temperature is not None else 0.2,
                            None,  # max_output_tokens
                            reasoning_effort=request.reasoning_effort,
                            images=request.images if request.images else None,
                            timeout=model_timeout,
                        )
                    
                    response = await loop.run_in_executor(
                        _thread_pool,
                        generate_with_timeout
                    )
                finally:
                    # NOTE: We cannot close providers here because they are singleton instances
                    # shared across multiple models. Closing after one model finishes would
                    # break it for other models using the same provider (e.g., both gemini-2.5-flash
                    # and gemini-2.5-pro use the same GOOGLE provider instance).
                    # Providers are properly cleaned up at server shutdown.
                    pass

            logger.debug(f"[CONSENSUS] {model_name} response received after {time.time() - start_time:.2f}s")

            end_time = time.time()
            response_time = end_time - start_time

            return {
                "model": model_name,
                "status": "success",
                "phase": phase,
                "response": response.content,
                "metadata": {
                    "provider": provider.get_provider_type().value,
                    "model_name": model_name,
                    "input_tokens": response.usage.get("input_tokens", 0) if response.usage else 0,
                    "output_tokens": response.usage.get("output_tokens", 0) if response.usage else 0,
                    "response_time": response_time,
                },
            }

        except Exception as e:
            logger.exception("Error consulting model %s in %s phase", model_config, phase)
            return {
                "model": model_config.get("model", "unknown"),
                "status": "error",
                "phase": phase,
                "error": str(e),
            }

    async def _consult_model_with_feedback(
        self,
        model_config: dict,
        request,
        initial_response: dict,
        other_responses: list[dict],
        phase: str = "refinement",
        provider=None,
        system_prompt=None,
    ) -> dict:
        """Consult a model with feedback from other models' responses."""
        try:
            # Get the provider for this model
            model_name = model_config["model"]
            if provider is None:
                provider = self.get_model_provider(model_name)

            # Build the feedback prompt
            feedback_prompt = self._build_cross_feedback_prompt(
                initial_response, other_responses, request.cross_feedback_prompt
            )

            # Use the consensus system prompt if not provided
            if system_prompt is None:
                system_prompt = self.get_system_prompt()

            # Call the model with the feedback and timing, pass timeout to provider (use asyncio.to_thread for parallel execution)
            start_time = time.time()
            model_timeout = self._get_model_timeout(model_name)
            
            # Use semaphore to limit concurrent thread operations
            async with _thread_semaphore:
                # Get current event loop
                loop = asyncio.get_event_loop()
                
                try:
                    # Use custom thread pool executor instead of default
                    # Create a wrapper function to pass timeout as keyword argument
                    def generate_with_timeout():
                        return provider.generate_content(
                            feedback_prompt,
                            model_name,
                            system_prompt,
                            request.temperature if request.temperature is not None else 0.2,
                            None,  # max_output_tokens
                            reasoning_effort=request.reasoning_effort,
                            images=request.images if request.images else None,
                            timeout=model_timeout,
                        )
                    
                    response = await loop.run_in_executor(
                        _thread_pool,
                        generate_with_timeout
                    )
                finally:
                    # NOTE: We cannot close providers here because they are singleton instances
                    # shared across multiple models. Closing after one model finishes would
                    # break it for other models using the same provider (e.g., both gemini-2.5-flash
                    # and gemini-2.5-pro use the same GOOGLE provider instance).
                    # Providers are properly cleaned up at server shutdown.
                    pass

            end_time = time.time()
            response_time = end_time - start_time

            return {
                "model": model_name,
                "status": "success",
                "phase": phase,
                "initial_response": initial_response.get("response"),
                "refined_response": response.content,
                "metadata": {
                    "provider": provider.get_provider_type().value,
                    "model_name": model_name,
                    "input_tokens": response.usage.get("input_tokens", 0) if response.usage else 0,
                    "output_tokens": response.usage.get("output_tokens", 0) if response.usage else 0,
                    "response_time": response_time,
                },
            }

        except Exception as e:
            logger.exception("Error in refinement phase for model %s", model_config)
            return {
                "model": model_config.get("model", "unknown"),
                "status": "error",
                "phase": phase,
                "error": str(e),
            }

    def _build_cross_feedback_prompt(
        self, initial_response: dict, other_responses: list[dict], custom_prompt: str | None = None
    ) -> str:
        """Build the prompt for cross-model feedback phase."""
        if custom_prompt:
            # Use custom prompt template exactly as provided
            return custom_prompt

        # Default cross-feedback prompt
        prompt = f"""You previously analyzed the following question/proposal:

{self.initial_prompt}

Your initial response was:
{initial_response.get('response', 'No response available')}

Other AI models have also provided their perspectives on this same question. Here are their responses:

"""

        # Add other models' responses
        for i, other in enumerate(other_responses, 1):
            model_info = f"{other.get('model', 'Unknown')}"
            prompt += f"\n=== Response {i} from {model_info} ===\n"
            prompt += other.get("response", "No response available")
            prompt += "\n"

        # Add refinement instructions
        prompt += """
=== OTHER APPROACHES ===

Review all solutions including yours. Focus on:

1. Is there a better approach here that you missed?
2. Does someone have a key insight that makes the problem simpler?
3. Can you improve on the best approach you see?

If you see a superior solution, adopt and enhance it.
If your approach remains best, explain why clearly.
Don't defend for the sake of defending - find what actually works best.

IMPORTANT: Your response will replace your initial one, so make it complete and self-contained.
Use the same format as before (## Approach, ## Why This Works, ## Implementation, ## Trade-offs).
"""

        return prompt

    def _extract_previous_consensus(self, continuation_id: str) -> dict[str, str]:
        """Extract model responses from previous consensus turns in the conversation."""
        logger.debug(f"[CONSENSUS] Extracting previous consensus for continuation_id: {continuation_id}")
        
        from utils.conversation_memory import get_thread

        logger.debug(f"[CONSENSUS] About to call get_thread")
        thread = get_thread(continuation_id)
        logger.debug(f"[CONSENSUS] get_thread returned: {thread is not None}")
        
        if not thread:
            logger.debug(f"[CONSENSUS] No thread found for continuation_id: {continuation_id}")
            return {}

        consensus_responses = {}
        logger.debug(f"[CONSENSUS] Found thread with {len(thread.turns)} turns")
        
        # Check thread size to see if data explosion is happening
        try:
            import sys
            thread_size = sys.getsizeof(thread)
            logger.debug(f"[CONSENSUS] Thread object size: {thread_size} bytes")
            for i, turn in enumerate(thread.turns[:5]):  # Check first 5 turns
                turn_size = sys.getsizeof(turn)
                logger.debug(f"[CONSENSUS] Turn {i} size: {turn_size} bytes")
        except Exception as e:
            logger.warning(f"[CONSENSUS] Could not measure thread size: {e}")

        # Walk through turns to find consensus responses
        for i, turn in enumerate(thread.turns):
            logger.debug(f"[CONSENSUS] Processing turn {i}, tool: {getattr(turn, 'tool_name', 'None')}, role: {getattr(turn, 'role', 'None')}")
            
            # Special logging for turn 5 which seems to be where it hangs
            if i == 5:
                logger.debug(f"[CONSENSUS] CRITICAL: Starting to process turn 5")
                logger.debug(f"[CONSENSUS] Turn 5 has model_metadata: {hasattr(turn, 'model_metadata') and turn.model_metadata is not None}")
                if hasattr(turn, 'model_metadata') and turn.model_metadata:
                    logger.debug(f"[CONSENSUS] Turn 5 model_metadata keys: {list(turn.model_metadata.keys())}")
                    
            try:
                if turn.tool_name == "consensus" and turn.role == "assistant":
                    logger.debug(f"[CONSENSUS] Found consensus turn at index {i}")
                    # Check if we have consensus data in metadata
                    logger.debug(f"[CONSENSUS] Checking model_metadata existence")
                    if turn.model_metadata and "consensus_data" in turn.model_metadata:
                        logger.debug(f"[CONSENSUS] Found consensus_data in turn {i}")
                        consensus_data = turn.model_metadata["consensus_data"]
                        if isinstance(consensus_data, dict) and "responses" in consensus_data:
                            responses = consensus_data.get("responses", [])
                            if not isinstance(responses, list):
                                logger.warning(f"[CONSENSUS] Invalid responses type at turn {i}: {type(responses)}")
                                continue
                            
                            for j, response in enumerate(responses):
                                if not isinstance(response, dict):
                                    logger.warning(f"[CONSENSUS] Invalid response type at turn {i}, response {j}: {type(response)}")
                                    continue
                                    
                                model = response.get("model")
                                content = response.get("response")
                                if model and content and response.get("status") == "success":
                                    consensus_responses[model] = content
                                    logger.debug(
                                        f"[CONSENSUS] Extracted response from {model}, length: {len(content)} chars"
                                    )
            except Exception as e:
                logger.error(f"[CONSENSUS] Error processing turn {i}: {type(e).__name__}: {str(e)}")
                continue
        
        logger.debug(f"[CONSENSUS] Finished processing all {len(thread.turns)} turns")
        logger.debug(f"[CONSENSUS] Total consensus responses extracted: {len(consensus_responses)}")
        return consensus_responses

    def _build_model_specific_history(self, current_model: str, continuation_id: str, all_current_models: list) -> str:
        """Build conversation history specific to each model based on continuation context."""
        logger.debug(f"[CONSENSUS] Building history for model {current_model}, continuation_id: {continuation_id}")

        # Get previous consensus responses
        previous_consensus = self._extract_previous_consensus(continuation_id)
        if not previous_consensus:
            logger.debug("[CONSENSUS] No previous consensus responses found")
            return ""

        logger.debug(f"[CONSENSUS] Found {len(previous_consensus)} previous consensus responses")

        # Case 1: If this model participated before, show only its own response
        if current_model in previous_consensus:
            history = f"=== YOUR PREVIOUS RESPONSE ===\n\n{previous_consensus[current_model]}\n"
            logger.debug(f"[CONSENSUS] Model {current_model} participated before, history length: {len(history)} chars")
            return history

        # Case 2: New model - show all previous responses with attribution
        history = "=== PREVIOUS MODEL RESPONSES ===\n"
        for model, response in previous_consensus.items():
            history += f"\n--- {model}'s response ---\n{response}\n"

        logger.debug(
            f"[CONSENSUS] Model {current_model} is new, showing all responses, history length: {len(history)} chars"
        )
        return history

    def _format_consensus_for_storage(self, response_data: dict) -> str:
        """Format consensus results for conversation storage - store only essential data."""
        # Extract only essential information to prevent exponential prompt growth
        # DO NOT store the full JSON response which contains entire conversation history

        summary_parts = []
        summary_parts.append(f"Consensus gathering complete - {response_data['successful_responses']} models responded")

        # Store full model responses but NOT the JSON structure
        if response_data.get("responses"):
            summary_parts.append("\n\nModel responses:")
            for resp in response_data["responses"]:
                if resp.get("status") == "success":
                    model = resp.get("model", "Unknown")
                    # Store the full response content
                    content = resp.get("response", "")
                    summary_parts.append(f"\n\n--- {model} ---\n{content}")

        # Note any failed models
        if response_data.get("failed_models"):
            summary_parts.append(f"\n\nFailed models: {len(response_data['failed_models'])}")
            for failed in response_data["failed_models"]:
                summary_parts.append(f"\n- {failed.get('model', 'Unknown')}: {failed.get('error', 'Unknown error')}")

        return "".join(summary_parts)

    # Required abstract methods from SimpleTool
    def get_tool_fields(self) -> dict[str, dict[str, Any]]:
        """Tool-specific field definitions for consensus."""
        return {
            "prompt": {
                "type": "string",
                "description": CONSENSUS_FIELD_DESCRIPTIONS["prompt"],
            },
            "models": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                    },
                    "required": ["model"],
                },
                "description": CONSENSUS_FIELD_DESCRIPTIONS["models"],
            },
            "relevant_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": CONSENSUS_FIELD_DESCRIPTIONS["relevant_files"],
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": CONSENSUS_FIELD_DESCRIPTIONS["images"],
            },
            "enable_cross_feedback": {
                "type": "boolean",
                "default": True,
                "description": CONSENSUS_FIELD_DESCRIPTIONS["enable_cross_feedback"],
            },
            "cross_feedback_prompt": {
                "type": "string",
                "description": CONSENSUS_FIELD_DESCRIPTIONS["cross_feedback_prompt"],
            },
        }

    def get_required_fields(self) -> list[str]:
        """Required fields for consensus tool."""
        return ["prompt", "models"]

    async def prepare_prompt(self, request: ConsensusRequest) -> str:
        """Not used - consensus uses execute() directly."""
        return ""
