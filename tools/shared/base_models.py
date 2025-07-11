"""
Base models for Zen MCP tools.

This module contains the shared Pydantic models used across all tools,
extracted to avoid circular imports and promote code reuse.

Key Models:
- ToolRequest: Base request model for all tools
"""

from typing import Optional

from pydantic import BaseModel, Field

# Shared field descriptions to avoid duplication
COMMON_FIELD_DESCRIPTIONS = {
    "model": (
        "Model to use. See tool's input schema for available models and their capabilities. "
        "Use 'auto' to let Claude select the best model for the task."
    ),
    "temperature": (
        "Temperature for response (0.0 to 1.0). Lower values are more focused and deterministic, "
        "higher values are more creative. Tool-specific defaults apply if not specified."
    ),
    "thinking_mode": (
        "Thinking depth: minimal (0.5% of model max), low (8%), medium (33%), high (67%), "
        "max (100% of model max). Higher modes enable deeper reasoning at the cost of speed."
    ),
    "use_websearch": (
        "Enable web search for documentation, best practices, and current information. "
        "When enabled, the model can request Claude to perform web searches and share results back "
        "during conversations. Particularly useful for: brainstorming sessions, architectural design "
        "discussions, exploring industry best practices, working with specific frameworks/technologies, "
        "researching solutions to complex problems, or when current documentation and community insights "
        "would enhance the analysis."
    ),
    "continuation_id": (
        "Thread continuation ID for multi-turn conversations. When provided, the complete conversation "
        "history is automatically embedded as context. Your response should build upon this history "
        "without repeating previous analysis or instructions. Focus on providing only new insights, "
        "additional findings, or answers to follow-up questions. Can be used across different tools."
    ),
    "images": (
        "Optional image(s) for visual context. Accepts absolute file paths or "
        "base64 data URLs. Only provide when user explicitly mentions images. "
        "When including images, please describe what you believe each image contains "
        "to aid with contextual understanding. Useful for UI discussions, diagrams, "
        "visual problems, error screens, architecture mockups, and visual analysis tasks."
    ),
    "files": ("Optional files for context (must be FULL absolute paths to real files / folders - DO NOT SHORTEN)"),
}


class ToolRequest(BaseModel):
    """
    Base request model for all Zen MCP tools.

    This model defines common fields that all tools accept, including
    model selection, temperature control, and conversation threading.
    Tool-specific request models should inherit from this class.
    """

    # Model configuration
    model: Optional[str] = Field(None, description=COMMON_FIELD_DESCRIPTIONS["model"])
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0, description=COMMON_FIELD_DESCRIPTIONS["temperature"])
    thinking_mode: Optional[str] = Field(None, description=COMMON_FIELD_DESCRIPTIONS["thinking_mode"])

    # Features
    use_websearch: Optional[bool] = Field(True, description=COMMON_FIELD_DESCRIPTIONS["use_websearch"])

    # Conversation support
    continuation_id: Optional[str] = Field(None, description=COMMON_FIELD_DESCRIPTIONS["continuation_id"])

    # Visual context
    images: Optional[list[str]] = Field(None, description=COMMON_FIELD_DESCRIPTIONS["images"])


# Tool-specific field descriptions are now declared in each tool file
# This keeps concerns separated and makes each tool self-contained
