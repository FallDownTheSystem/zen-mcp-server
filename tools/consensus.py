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
                logger.warning(f"Invalid CONSENSUS_MODEL_TIMEOUT value ({timeout}), using default of {default_timeout} seconds")
                return default_timeout
            return timeout
        except (ValueError, TypeError):
            logger.warning(f"Invalid CONSENSUS_MODEL_TIMEOUT value ('{timeout_str}'), using default of {default_timeout} seconds")
            return default_timeout

    async def execute(self, arguments: dict[str, Any]) -> list:
        """Execute parallel consensus with optional cross-model feedback."""

        # Validate request
        request = self.get_request_model()(**arguments)

        # Store initial state
        self.initial_prompt = request.prompt
        self.models_to_consult = request.models

        try:
            # Phase 1: Parallel initial model consultations
            logger.info(f"Starting parallel consensus for {len(self.models_to_consult)} models")

            initial_tasks = [
                self._consult_model(model_config, request, phase="initial") for model_config in self.models_to_consult
            ]

            # Execute all initial consultations in parallel
            # return_exceptions=True ensures failures don't stop other models
            initial_responses = await asyncio.gather(*initial_tasks, return_exceptions=True)

            # Process results and handle any errors
            successful_initial = []
            failed_models = []

            for i, response in enumerate(initial_responses):
                if isinstance(response, Exception):
                    logger.error(f"Model {self.models_to_consult[i].get('model', 'unknown')} failed: {response}")
                    failed_models.append(
                        {
                            "model": self.models_to_consult[i].get("model", "unknown"),
                            "error": str(response),
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
                            refinement_tasks.append(
                                self._consult_model_with_feedback(
                                    model_config, request, response, other_responses, phase="refinement"
                                )
                            )

                # Execute refinement tasks in parallel
                if refinement_tasks:
                    refinement_results = await asyncio.gather(*refinement_tasks, return_exceptions=True)

                    for result in refinement_results:
                        if isinstance(result, Exception):
                            logger.error(f"Refinement phase error: {result}")
                            # Continue without this refinement
                        else:
                            refined_responses.append(result)

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
                    thread_context = get_thread(request.continuation_id)
                    if thread_context and thread_context.turns:
                        turn_count = len(thread_context.turns)
                        if turn_count < MAX_CONVERSATION_TURNS - 1:
                            # Add consensus result as assistant turn
                            add_turn(
                                request.continuation_id,
                                "assistant",
                                self._format_consensus_for_storage(response_data),
                                tool_name="consensus",
                                model_provider="multi-model-consensus",
                                model_name=f"{len(final_responses)} models",
                                model_metadata={"consensus_data": response_data},
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

                    new_thread_id = create_thread(tool_name="consensus", initial_request=initial_request_dict)

                    # Add user's initial turn
                    add_turn(
                        new_thread_id,
                        "user",
                        request.prompt,
                        files=request.relevant_files,
                        images=request.images,
                        tool_name="consensus",
                    )

                    # Add consensus result as assistant turn
                    add_turn(
                        new_thread_id,
                        "assistant",
                        self._format_consensus_for_storage(response_data),
                        tool_name="consensus",
                        model_provider="multi-model-consensus",
                        model_name=f"{len(final_responses)} models",
                        model_metadata={"consensus_data": response_data},
                    )

                    continuation_offer = {
                        "continuation_id": new_thread_id,
                        "remaining_turns": MAX_CONVERSATION_TURNS - 1,
                        "note": f"Claude can continue this conversation for {MAX_CONVERSATION_TURNS - 1} more exchanges.",
                    }

            # Add continuation offer to response if available
            if continuation_offer:
                response_data["continuation_offer"] = continuation_offer

            return [TextContent(type="text", text=json.dumps(response_data, indent=2, ensure_ascii=False))]

        except Exception as e:
            logger.exception("Error in consensus workflow execution")
            error_response = {
                "status": "error",
                "error": str(e),
                "metadata": {"tool_name": self.get_name(), "workflow_type": "parallel_consensus"},
            }
            return [TextContent(type="text", text=json.dumps(error_response, indent=2, ensure_ascii=False))]

    async def _consult_model(self, model_config: dict, request, phase: str = "initial") -> dict:
        """Consult a single model and return its response."""
        try:
            # Get the provider for this model
            model_name = model_config["model"]
            provider = self.get_model_provider(model_name)

            # Create model context for this specific model
            from utils.model_context import ModelContext

            model_context = ModelContext(model_name)

            # Prepare the prompt with any relevant files
            prompt = self.initial_prompt

            # Add model-specific continuation history for initial phase only
            if request.continuation_id and phase == "initial":
                model_history = self._build_model_specific_history(model_name, request.continuation_id, request.models)

                if model_history:
                    prompt = f"{model_history}\n\nNEW QUESTION:\n{prompt}"

            if request.relevant_files:
                file_content, _ = self._prepare_file_content_for_prompt(
                    request.relevant_files,
                    request.continuation_id,
                    "Context files",
                    model_context=model_context,
                )
                if file_content:
                    prompt = f"{prompt}\n\n=== CONTEXT FILES ===\n{file_content}\n=== END CONTEXT ==="

            # Use the consensus system prompt
            system_prompt = self.get_system_prompt()

            # Call the model with timing and pass timeout to provider (use asyncio.to_thread for parallel execution)
            start_time = time.time()
            consensus_timeout = self._get_consensus_timeout()
            response = await asyncio.to_thread(
                provider.generate_content,
                prompt=prompt,
                model_name=model_name,
                system_prompt=system_prompt,
                temperature=request.temperature if request.temperature is not None else 0.2,
                thinking_mode="medium",
                images=request.images if request.images else None,
                timeout=consensus_timeout,  # Pass timeout to HTTP client for clean termination
            )

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
    ) -> dict:
        """Consult a model with feedback from other models' responses."""
        try:
            # Get the provider for this model
            model_name = model_config["model"]
            provider = self.get_model_provider(model_name)

            # Build the feedback prompt
            feedback_prompt = self._build_cross_feedback_prompt(
                initial_response, other_responses, request.cross_feedback_prompt
            )

            # Use the consensus system prompt
            system_prompt = self.get_system_prompt()

            # Call the model with the feedback and timing, pass timeout to provider (use asyncio.to_thread for parallel execution)
            start_time = time.time()
            consensus_timeout = self._get_consensus_timeout()
            response = await asyncio.to_thread(
                provider.generate_content,
                prompt=feedback_prompt,
                model_name=model_name,
                system_prompt=system_prompt,
                temperature=request.temperature if request.temperature is not None else 0.2,
                thinking_mode="medium",
                images=request.images if request.images else None,
                timeout=consensus_timeout,  # Pass timeout to HTTP client for clean termination
            )

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
        from utils.conversation_memory import get_thread

        thread = get_thread(continuation_id)
        if not thread:
            return {}

        consensus_responses = {}

        # Walk through turns to find consensus responses
        for turn in thread.turns:
            if turn.tool_name == "consensus" and turn.role == "assistant":
                # Check if we have consensus data in metadata
                if turn.model_metadata and "consensus_data" in turn.model_metadata:
                    consensus_data = turn.model_metadata["consensus_data"]
                    if isinstance(consensus_data, dict) and "responses" in consensus_data:
                        for response in consensus_data["responses"]:
                            model = response.get("model")
                            content = response.get("response")
                            if model and content and response.get("status") == "success":
                                consensus_responses[model] = content

        return consensus_responses

    def _build_model_specific_history(self, current_model: str, continuation_id: str, all_current_models: list) -> str:
        """Build conversation history specific to each model based on continuation context."""
        # Get previous consensus responses
        previous_consensus = self._extract_previous_consensus(continuation_id)
        if not previous_consensus:
            return ""

        # Case 1: If this model participated before, show only its own response
        if current_model in previous_consensus:
            return f"=== YOUR PREVIOUS RESPONSE ===\n\n{previous_consensus[current_model]}\n"

        # Case 2: New model - show all previous responses with attribution
        history = "=== PREVIOUS MODEL RESPONSES ===\n"
        for model, response in previous_consensus.items():
            history += f"\n--- {model}'s response ---\n{response}\n"

        return history

    def _format_consensus_for_storage(self, response_data: dict) -> str:
        """Format consensus results for conversation storage - store complete JSON."""
        # Store the entire response data as JSON to preserve full fidelity
        return json.dumps(response_data, indent=2, ensure_ascii=False)

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
