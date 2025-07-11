"""
Consensus tool - Parallel multi-model consensus with cross-model feedback

This tool provides a structured workflow for gathering consensus from multiple models.
It sends the initial prompt to all models in parallel, then allows each model to see
the others' responses and refine their answer based on the collective insights.

Key features:
- Parallel model consultation for faster execution
- Two-phase approach: initial responses + refinement based on cross-model feedback
- Context-aware file embedding
- Support for stance-based analysis (for/against/neutral)
- Comprehensive responses showing both initial and refined perspectives
- Robust error handling - if one model fails, others continue
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from pydantic import Field, model_validator

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from mcp.types import TextContent

from config import TEMPERATURE_ANALYTICAL
from systemprompts import CONSENSUS_PROMPT
from tools.shared.base_models import WorkflowRequest

from .workflow.base import WorkflowTool

logger = logging.getLogger(__name__)

# Tool-specific field descriptions for consensus workflow
CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS = {
    "step": (
        "Describe the proposal, question, or idea you want to gather consensus on. "
        "Provide sufficient context and be clear about what decision or feedback you're seeking. "
        "This will be sent to all models for their initial analysis."
    ),
    "step_number": (
        "For the new parallel workflow, this should always be 1 as the entire consensus "
        "gathering happens in a single call."
    ),
    "total_steps": (
        "For the new parallel workflow, this should always be 1 as the entire consensus "
        "gathering happens in a single call."
    ),
    "next_step_required": ("For the new parallel workflow, this should always be False."),
    "findings": (
        "Provide your initial analysis or context about the proposal. This helps frame "
        "the discussion for the models that will be consulted."
    ),
    "relevant_files": (
        "Files that are relevant to the consensus analysis. Include files that help understand the proposal, "
        "provide context, or contain implementation details."
    ),
    "models": (
        "List of model configurations to consult. Each can have a model name, stance (for/against/neutral), "
        "and optional custom stance prompt. The same model can be used multiple times with different stances, "
        "but each model + stance combination must be unique. "
        "Example: [{'model': 'o3', 'stance': 'for'}, {'model': 'o3', 'stance': 'against'}, "
        "{'model': 'flash', 'stance': 'neutral'}]"
    ),
    "current_model_index": (
        "Internal tracking of which model is being consulted (0-based index). Used to determine which model "
        "to call next."
    ),
    "model_responses": ("Accumulated responses from models consulted so far. Internal field for tracking progress."),
    "images": (
        "Optional list of image paths or base64 data URLs for visual context. Useful for UI/UX discussions, "
        "architecture diagrams, mockups, or any visual references that help inform the consensus analysis."
    ),
    "enable_cross_feedback": (
        "Whether to enable the second phase where models see each other's responses and can refine their answers. "
        "Defaults to True. Set to False for faster single-phase consensus."
    ),
    "cross_feedback_prompt": (
        "Optional custom prompt for the cross-model feedback phase. If not provided, a default prompt will be used "
        "that asks models to consider other perspectives and refine their response."
    ),
}


class ConsensusRequest(WorkflowRequest):
    """Request model for consensus workflow steps"""

    # Required fields for each step
    step: str = Field(..., description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["step"])
    step_number: int = Field(..., description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["step_number"])
    total_steps: int = Field(..., description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["total_steps"])
    next_step_required: bool = Field(..., description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"])

    # Investigation tracking fields
    findings: str = Field(..., description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["findings"])
    confidence: str = Field(default="exploring", exclude=True, description="Not used")

    # Consensus-specific fields (only needed in step 1)
    models: list[dict] | None = Field(None, description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["models"])
    relevant_files: list[str] | None = Field(
        default_factory=list,
        description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"],
    )

    # Internal tracking fields
    current_model_index: int | None = Field(
        0,
        description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["current_model_index"],
    )
    model_responses: list[dict] | None = Field(
        default_factory=list,
        description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["model_responses"],
    )

    # Optional images for visual debugging
    images: list[str] | None = Field(default=None, description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["images"])

    # New fields for parallel consensus with cross-feedback
    enable_cross_feedback: bool = Field(
        default=True,
        description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["enable_cross_feedback"],
    )
    cross_feedback_prompt: str | None = Field(
        default=None,
        description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["cross_feedback_prompt"],
    )

    # Override inherited fields to exclude them from schema
    temperature: float | None = Field(default=None, exclude=True)
    thinking_mode: str | None = Field(default=None, exclude=True)
    use_websearch: bool | None = Field(default=None, exclude=True)

    # Not used in consensus workflow
    files_checked: list[str] | None = Field(default_factory=list, exclude=True)
    relevant_context: list[str] | None = Field(default_factory=list, exclude=True)
    issues_found: list[dict] | None = Field(default_factory=list, exclude=True)
    hypothesis: str | None = Field(None, exclude=True)
    backtrack_from_step: int | None = Field(None, exclude=True)

    @model_validator(mode="after")
    def validate_consensus_requirements(self):
        """Ensure consensus request has required models field and unique model+stance combinations."""
        # For the new parallel workflow, we always need models
        if not self.models:
            raise ValueError("Consensus requires 'models' field to specify which models to consult")

        # Check for unique model + stance combinations
        seen_combinations = set()
        for model_config in self.models:
            model_name = model_config.get("model", "")
            stance = model_config.get("stance", "neutral")
            combination = f"{model_name}:{stance}"

            if combination in seen_combinations:
                raise ValueError(
                    f"Duplicate model + stance combination found: {model_name} with stance '{stance}'. "
                    f"Each model + stance combination must be unique."
                )
            seen_combinations.add(combination)

        return self


class ConsensusTool(WorkflowTool):
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
        self.accumulated_responses: list[dict] = []
        self._current_arguments: dict[str, Any] = {}

    def get_name(self) -> str:
        return "consensus"

    def get_description(self) -> str:
        return (
            "PARALLEL CONSENSUS WITH CROSS-MODEL FEEDBACK - Multi-model consensus gathering in a single call. "
            "This tool consults multiple AI models simultaneously and includes a feedback phase where models "
            "can refine their responses based on others' perspectives.\n\n"
            "How it works:\n"
            "1. Send your proposal/question to all specified models in parallel\n"
            "2. Collect all initial responses\n"
            "3. Share each model's response with the others for refinement\n"
            "4. Collect refined responses that incorporate cross-model insights\n"
            "5. Return both initial and refined responses for comprehensive analysis\n\n"
            "Key features:\n"
            "- Parallel execution for faster results (single tool call)\n"
            "- Cross-model feedback allows models to learn from each other\n"
            "- Models can have stances (for/against/neutral) for structured debate\n"
            "- Same model can be used multiple times with different stances\n"
            "- Robust error handling - if one model fails, others continue\n"
            "- Optional: disable cross-feedback for faster single-phase consensus\n\n"
            "Perfect for: complex decisions, architectural choices, feature proposals, "
            "technology evaluations, strategic planning where multiple perspectives and refinement are valuable."
        )

    def get_system_prompt(self) -> str:
        # For the CLI agent's initial analysis, use a neutral version of the consensus prompt
        return CONSENSUS_PROMPT.replace(
            "{stance_prompt}",
            """BALANCED PERSPECTIVE

Provide objective analysis considering both positive and negative aspects. However, if there is overwhelming evidence
that the proposal clearly leans toward being exceptionally good or particularly problematic, you MUST accurately
reflect this reality. Being "balanced" means being truthful about the weight of evidence, not artificially creating
50/50 splits when the reality is 90/10.

Your analysis should:
- Present all significant pros and cons discovered
- Weight them according to actual impact and likelihood
- If evidence strongly favors one conclusion, clearly state this
- Provide proportional coverage based on the strength of arguments
- Help the questioner see the true balance of considerations

Remember: Artificial balance that misrepresents reality is not helpful. True balance means accurate representation
of the evidence, even when it strongly points in one direction.""",
        )

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    def get_model_category(self) -> ToolModelCategory:
        """Consensus workflow requires extended reasoning"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def get_workflow_request_model(self):
        """Return the consensus workflow-specific request model."""
        return ConsensusRequest

    def get_input_schema(self) -> dict[str, Any]:
        """Generate input schema for consensus workflow."""
        from .workflow.schema_builders import WorkflowSchemaBuilder

        # Consensus tool-specific field definitions
        consensus_field_overrides = {
            # Override standard workflow fields that need consensus-specific descriptions
            "step": {
                "type": "string",
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["step"],
            },
            "step_number": {
                "type": "integer",
                "minimum": 1,
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["step_number"],
            },
            "total_steps": {
                "type": "integer",
                "minimum": 1,
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["total_steps"],
            },
            "next_step_required": {
                "type": "boolean",
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"],
            },
            "findings": {
                "type": "string",
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["findings"],
            },
            "relevant_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"],
            },
            # consensus-specific fields (not in base workflow)
            "models": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "stance": {"type": "string", "enum": ["for", "against", "neutral"], "default": "neutral"},
                        "stance_prompt": {"type": "string"},
                    },
                    "required": ["model"],
                },
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["models"],
            },
            "current_model_index": {
                "type": "integer",
                "minimum": 0,
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["current_model_index"],
            },
            "model_responses": {
                "type": "array",
                "items": {"type": "object"},
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["model_responses"],
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["images"],
            },
            "enable_cross_feedback": {
                "type": "boolean",
                "default": True,
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["enable_cross_feedback"],
            },
            "cross_feedback_prompt": {
                "type": "string",
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["cross_feedback_prompt"],
            },
        }

        # Define excluded fields for consensus workflow
        excluded_workflow_fields = [
            "files_checked",  # Not used in consensus workflow
            "relevant_context",  # Not used in consensus workflow
            "issues_found",  # Not used in consensus workflow
            "hypothesis",  # Not used in consensus workflow
            "backtrack_from_step",  # Not used in consensus workflow
            "confidence",  # Not used in consensus workflow
        ]

        excluded_common_fields = [
            "model",  # Consensus uses 'models' field instead
            "temperature",  # Not used in consensus workflow
            "thinking_mode",  # Not used in consensus workflow
            "use_websearch",  # Not used in consensus workflow
        ]

        # Build schema with proper field exclusion
        # Include model field for compatibility but don't require it
        schema = WorkflowSchemaBuilder.build_schema(
            tool_specific_fields=consensus_field_overrides,
            model_field_schema=self.get_model_field_schema(),
            auto_mode=False,  # Consensus doesn't require model at MCP boundary
            tool_name=self.get_name(),
            excluded_workflow_fields=excluded_workflow_fields,
            excluded_common_fields=excluded_common_fields,
        )
        return schema

    def get_required_actions(
        self, step_number: int, confidence: str, findings: str, total_steps: int
    ) -> list[str]:  # noqa: ARG002
        """Define required actions for consensus workflow.

        For the new parallel workflow, this is simplified since everything happens in one call.
        """
        return [
            "Consensus gathering will consult all specified models in parallel",
            "Models will receive the same prompt and provide initial responses",
            "If cross-feedback is enabled, models will see each other's responses and refine their answers",
            "You will receive all responses (initial and refined) in a single result",
        ]

    def should_call_expert_analysis(self, consolidated_findings, request=None) -> bool:
        """Consensus workflow doesn't use traditional expert analysis - it consults models step by step."""
        return False

    def prepare_expert_analysis_context(self, consolidated_findings) -> str:
        """Not used in consensus workflow."""
        return ""

    def requires_expert_analysis(self) -> bool:
        """Consensus workflow handles its own model consultations."""
        return False

    def requires_model(self) -> bool:
        """
        Consensus tool doesn't require model resolution at the MCP boundary.

        Uses it's own set of models

        Returns:
            bool: False
        """
        return False

    # Hook method overrides for consensus-specific behavior

    def prepare_step_data(self, request) -> dict:
        """Prepare consensus-specific step data."""
        step_data = {
            "step": request.step,
            "step_number": request.step_number,
            "findings": request.findings,
            "files_checked": [],  # Not used
            "relevant_files": request.relevant_files or [],
            "relevant_context": [],  # Not used
            "issues_found": [],  # Not used
            "confidence": "exploring",  # Not used, kept for compatibility
            "hypothesis": None,  # Not used
            "images": request.images or [],  # Now used for visual context
        }
        return step_data

    async def handle_work_completion(self, response_data: dict, request, arguments: dict) -> dict:  # noqa: ARG002
        """Handle consensus workflow completion.

        For the new parallel workflow, this is not used since everything happens in execute_workflow.
        """
        # This method is not used in the new parallel workflow
        return response_data

    def handle_work_continuation(self, response_data: dict, request) -> dict:
        """Handle continuation between consensus steps.

        For the new parallel workflow, this is not used since everything happens in one call.
        """
        # This method is not used in the new parallel workflow
        return response_data

    async def execute_workflow(self, arguments: dict[str, Any]) -> list:
        """Execute parallel consensus workflow with optional cross-model feedback."""

        # Validate request
        request = self.get_workflow_request_model()(**arguments)

        # Store initial state
        self.initial_prompt = request.step
        self.models_to_consult = request.models or []

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
                            "stance": self.models_to_consult[i].get("stance", "neutral"),
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
                            if mc.get("model") == response.get("model") and mc.get("stance", "neutral") == response.get(
                                "stance", "neutral"
                            ):
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

            # Prepare comprehensive response
            response_data = {
                "status": "consensus_complete",
                "consensus_complete": True,
                "initial_prompt": self.initial_prompt,
                "models_consulted": len(self.models_to_consult),
                "successful_initial_responses": len(successful_initial),
                "refined_responses": len(refined_responses),
                "failed_models": failed_models,
                "cross_feedback_enabled": request.enable_cross_feedback,
                "phases": {"initial": successful_initial, "refined": refined_responses if refined_responses else None},
                "next_steps": (
                    "PARALLEL CONSENSUS GATHERING IS COMPLETE. Please synthesize the responses:\n"
                    "1. Review initial responses from all models\n"
                    + (
                        "2. Consider refined responses that incorporate cross-model insights\n"
                        if refined_responses
                        else ""
                    )
                    + "3. Identify key points of AGREEMENT across models\n"
                    "4. Note key points of DISAGREEMENT and underlying reasons\n"
                    "5. Provide your final recommendation based on the collective insights\n"
                    "6. Suggest specific, actionable next steps"
                ),
                "metadata": {
                    "tool_name": self.get_name(),
                    "workflow_type": "parallel_consensus_with_feedback" if refined_responses else "parallel_consensus",
                    "total_models": len(self.models_to_consult),
                    "successful_models": len(successful_initial),
                    "models_with_refinements": len(refined_responses),
                },
            }

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

            # Prepare the prompt with any relevant files
            prompt = self.initial_prompt
            if request.relevant_files:
                file_content, _ = self._prepare_file_content_for_prompt(
                    request.relevant_files,
                    request.continuation_id,
                    "Context files",
                )
                if file_content:
                    prompt = f"{prompt}\n\n=== CONTEXT FILES ===\n{file_content}\n=== END CONTEXT ==="

            # Get stance-specific system prompt
            stance = model_config.get("stance", "neutral")
            stance_prompt = model_config.get("stance_prompt")
            system_prompt = self._get_stance_enhanced_prompt(stance, stance_prompt)

            # Call the model
            response = provider.generate_content(
                prompt=prompt,
                model_name=model_name,
                system_prompt=system_prompt,
                temperature=0.2,  # Low temperature for consistency
                thinking_mode="medium",
                images=request.images if request.images else None,
            )

            return {
                "model": model_name,
                "stance": stance,
                "status": "success",
                "phase": phase,
                "response": response.content,
                "metadata": {
                    "provider": provider.get_provider_type().value,
                    "model_name": model_name,
                    "input_tokens": response.usage.get("input_tokens", 0) if response.usage else 0,
                    "output_tokens": response.usage.get("output_tokens", 0) if response.usage else 0,
                },
            }

        except Exception as e:
            logger.exception("Error consulting model %s in %s phase", model_config, phase)
            return {
                "model": model_config.get("model", "unknown"),
                "stance": model_config.get("stance", "neutral"),
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

            # Get stance-specific system prompt
            stance = model_config.get("stance", "neutral")
            stance_prompt = model_config.get("stance_prompt")
            system_prompt = self._get_stance_enhanced_prompt(stance, stance_prompt)

            # Call the model with the feedback
            response = provider.generate_content(
                prompt=feedback_prompt,
                model_name=model_name,
                system_prompt=system_prompt,
                temperature=0.2,  # Low temperature for consistency
                thinking_mode="medium",
                images=request.images if request.images else None,
            )

            return {
                "model": model_name,
                "stance": stance,
                "status": "success",
                "phase": phase,
                "initial_response": initial_response.get("response"),
                "refined_response": response.content,
                "metadata": {
                    "provider": provider.get_provider_type().value,
                    "model_name": model_name,
                    "input_tokens": response.usage.get("input_tokens", 0) if response.usage else 0,
                    "output_tokens": response.usage.get("output_tokens", 0) if response.usage else 0,
                },
            }

        except Exception as e:
            logger.exception("Error in refinement phase for model %s", model_config)
            return {
                "model": model_config.get("model", "unknown"),
                "stance": model_config.get("stance", "neutral"),
                "status": "error",
                "phase": phase,
                "error": str(e),
            }

    def _build_cross_feedback_prompt(
        self, initial_response: dict, other_responses: list[dict], custom_prompt: str | None = None
    ) -> str:
        """Build the prompt for cross-model feedback phase."""
        if custom_prompt:
            # Use custom prompt template
            prompt = custom_prompt
        else:
            # Default cross-feedback prompt
            prompt = f"""You previously analyzed the following question/proposal:

{self.initial_prompt}

Your initial response was:
{initial_response.get('response', 'No response available')}

Other AI models have also provided their perspectives on this same question. Here are their responses:

"""

        # Add other models' responses
        for i, other in enumerate(other_responses, 1):
            model_info = f"{other.get('model', 'Unknown')} ({other.get('stance', 'neutral')} perspective)"
            prompt += f"\n=== Response {i} from {model_info} ===\n"
            prompt += other.get("response", "No response available")
            prompt += "\n"

        # Add refinement instructions
        if not custom_prompt:
            prompt += """
=== REFINEMENT REQUEST ===

After reviewing these other perspectives, please provide a refined response that:

1. Acknowledges valuable insights from other models that enhance your analysis
2. Clarifies or defends your position where you disagree with others
3. Identifies any consensus points across all models
4. Highlights critical disagreements and their implications
5. Updates your recommendation if the collective insights warrant it

Be specific about which insights from other models influenced your thinking and why.
Your refined response should be comprehensive but concise, focusing on how the
cross-model insights improve the overall analysis.
"""

        return prompt

    def _get_stance_enhanced_prompt(self, stance: str, custom_stance_prompt: str | None = None) -> str:
        """Get the system prompt with stance injection."""
        base_prompt = CONSENSUS_PROMPT

        if custom_stance_prompt:
            return base_prompt.replace("{stance_prompt}", custom_stance_prompt)

        stance_prompts = {
            "for": """SUPPORTIVE PERSPECTIVE WITH INTEGRITY

You are tasked with advocating FOR this proposal, but with CRITICAL GUARDRAILS:

MANDATORY ETHICAL CONSTRAINTS:
- This is NOT a debate for entertainment. You MUST act in good faith and in the best interest of the questioner
- You MUST think deeply about whether supporting this idea is safe, sound, and passes essential requirements
- You MUST be direct and unequivocal in saying "this is a bad idea" when it truly is
- There must be at least ONE COMPELLING reason to be optimistic, otherwise DO NOT support it

WHEN TO REFUSE SUPPORT (MUST OVERRIDE STANCE):
- If the idea is fundamentally harmful to users, project, or stakeholders
- If implementation would violate security, privacy, or ethical standards
- If the proposal is technically infeasible within realistic constraints
- If costs/risks dramatically outweigh any potential benefits

YOUR SUPPORTIVE ANALYSIS SHOULD:
- Identify genuine strengths and opportunities
- Propose solutions to overcome legitimate challenges
- Highlight synergies with existing systems
- Suggest optimizations that enhance value
- Present realistic implementation pathways

Remember: Being "for" means finding the BEST possible version of the idea IF it has merit, not blindly supporting bad ideas.""",
            "against": """CRITICAL PERSPECTIVE WITH RESPONSIBILITY

You are tasked with critiquing this proposal, but with ESSENTIAL BOUNDARIES:

MANDATORY FAIRNESS CONSTRAINTS:
- You MUST NOT oppose genuinely excellent, common-sense ideas just to be contrarian
- You MUST acknowledge when a proposal is fundamentally sound and well-conceived
- You CANNOT give harmful advice or recommend against beneficial changes
- If the idea is outstanding, say so clearly while offering constructive refinements

WHEN TO MODERATE CRITICISM (MUST OVERRIDE STANCE):
- If the proposal addresses critical user needs effectively
- If it follows established best practices with good reason
- If benefits clearly and substantially outweigh risks
- If it's the obvious right solution to the problem

YOUR CRITICAL ANALYSIS SHOULD:
- Identify legitimate risks and failure modes
- Point out overlooked complexities
- Suggest more efficient alternatives
- Highlight potential negative consequences
- Question assumptions that may be flawed

Remember: Being "against" means rigorous scrutiny to ensure quality, not undermining good ideas that deserve support.""",
            "neutral": """BALANCED PERSPECTIVE

Provide objective analysis considering both positive and negative aspects. However, if there is overwhelming evidence
that the proposal clearly leans toward being exceptionally good or particularly problematic, you MUST accurately
reflect this reality. Being "balanced" means being truthful about the weight of evidence, not artificially creating
50/50 splits when the reality is 90/10.

Your analysis should:
- Present all significant pros and cons discovered
- Weight them according to actual impact and likelihood
- If evidence strongly favors one conclusion, clearly state this
- Provide proportional coverage based on the strength of arguments
- Help the questioner see the true balance of considerations

Remember: Artificial balance that misrepresents reality is not helpful. True balance means accurate representation
of the evidence, even when it strongly points in one direction.""",
        }

        stance_prompt = stance_prompts.get(stance, stance_prompts["neutral"])
        return base_prompt.replace("{stance_prompt}", stance_prompt)

    def customize_workflow_response(self, response_data: dict, request) -> dict:
        """Customize response for consensus workflow."""
        # Store model responses in the response for tracking
        if self.accumulated_responses:
            response_data["accumulated_responses"] = self.accumulated_responses

        # Add consensus-specific fields
        if request.step_number == 1:
            response_data["consensus_workflow_status"] = "initial_analysis_complete"
        elif request.step_number < request.total_steps - 1:
            response_data["consensus_workflow_status"] = "consulting_models"
        else:
            response_data["consensus_workflow_status"] = "ready_for_synthesis"

        # Customize metadata for consensus workflow
        self._customize_consensus_metadata(response_data, request)

        return response_data

    def _customize_consensus_metadata(self, response_data: dict, request) -> None:
        """
        Customize metadata for consensus workflow to accurately reflect multi-model nature.

        The default workflow metadata shows the model running Agent's analysis steps,
        but consensus is a multi-model tool that consults different models. We need
        to provide accurate metadata that reflects this.
        """
        if "metadata" not in response_data:
            response_data["metadata"] = {}

        metadata = response_data["metadata"]

        # Always preserve tool_name
        metadata["tool_name"] = self.get_name()

        if request.step_number == request.total_steps:
            # Final step - show comprehensive consensus metadata
            models_consulted = []
            if self.models_to_consult:
                models_consulted = [f"{m['model']}:{m.get('stance', 'neutral')}" for m in self.models_to_consult]

            metadata.update(
                {
                    "workflow_type": "multi_model_consensus",
                    "models_consulted": models_consulted,
                    "consensus_complete": True,
                    "total_models": len(self.models_to_consult) if self.models_to_consult else 0,
                }
            )

            # Remove the misleading single model metadata
            metadata.pop("model_used", None)
            metadata.pop("provider_used", None)

        else:
            # Intermediate steps - show consensus workflow in progress
            models_to_consult = []
            if self.models_to_consult:
                models_to_consult = [f"{m['model']}:{m.get('stance', 'neutral')}" for m in self.models_to_consult]

            metadata.update(
                {
                    "workflow_type": "multi_model_consensus",
                    "models_to_consult": models_to_consult,
                    "consultation_step": request.step_number,
                    "total_consultation_steps": request.total_steps,
                }
            )

            # Remove the misleading single model metadata that shows Agent's execution model
            # instead of the models being consulted
            metadata.pop("model_used", None)
            metadata.pop("provider_used", None)

    def _add_workflow_metadata(self, response_data: dict, arguments: dict[str, Any]) -> None:
        """
        Override workflow metadata addition for consensus tool.

        The consensus tool doesn't use single model metadata because it's a multi-model
        workflow. Instead, we provide consensus-specific metadata that accurately
        reflects the models being consulted.
        """
        # Initialize metadata if not present
        if "metadata" not in response_data:
            response_data["metadata"] = {}

        # Add basic tool metadata
        response_data["metadata"]["tool_name"] = self.get_name()

        # The consensus-specific metadata is already added by _customize_consensus_metadata
        # which is called from customize_workflow_response. We don't add the standard
        # single-model metadata (model_used, provider_used) because it's misleading
        # for a multi-model consensus workflow.

        logger.debug(
            f"[CONSENSUS_METADATA] {self.get_name()}: Using consensus-specific metadata instead of single-model metadata"
        )

    def store_initial_issue(self, step_description: str):
        """Store initial prompt for model consultations."""
        self.initial_prompt = step_description

    # Required abstract methods from BaseTool
    def get_request_model(self):
        """Return the consensus workflow-specific request model."""
        return ConsensusRequest

    async def prepare_prompt(self, request) -> str:  # noqa: ARG002
        """Not used - workflow tools use execute_workflow()."""
        return ""  # Workflow tools use execute_workflow() directly
