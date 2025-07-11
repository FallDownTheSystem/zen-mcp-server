# Changelog

## [6.2.3] - 2025-07-11

### Added
- **Response Timing**: Added timing information to all model responses
  - Displays "<Model name> took X.XX seconds to respond." at end of each response
  - Helps identify slow models when running consensus across multiple models
  - Implemented in SimpleTool base class, applies to both Chat and Consensus tools
  - Includes timing even for error responses to track failed model performance

### Changed
- **Fork Attribution**: Added `__forked_by__ = "FallDownTheSystem"` to config.py alongside original author
- **Temperature as Parameter**: Moved temperature from hardcoded config values to tool request parameters
  - Chat tool now has `temperature` parameter with default 0.5 (balanced responses)
  - Consensus tool now has `temperature` parameter with default 0.2 (analytical/focused responses)
  - Removed `TEMPERATURE_ANALYTICAL` and `TEMPERATURE_BALANCED` from config.py
  - Users can now customize temperature per request instead of using fixed values

### Removed
- **Unused Config Variables**: Cleaned up config.py by removing unused variables
  - Removed `DEFAULT_CONSENSUS_TIMEOUT` and `DEFAULT_CONSENSUS_MAX_INSTANCES_PER_COMBINATION` (obsolete)
  - Simplified MCP_PROMPT_SIZE_LIMIT calculation by removing unused function
  - Updated tests to reflect the changes

## [6.2.2] - 2025-07-11

### Fixed
- **Token/Character Limit Mismatch**: Fixed validation bug where character limits were compared against token counts
  - `_validate_token_limit` now correctly converts character limit to token limit (÷4)
  - Prevents false validation failures when using large file contexts
  - Fixes issue where ~15k token files would fail against 60k character limit
  - Added comprehensive tests to prevent regression
- **Consensus Tool Error**: Fixed model context not being provided for file preparation
  - Added ModelContext creation for each model in _consult_model method
  - Ensures proper token allocation for file content across models

### Changed
- **Consensus Prompts**: Transformed from judgment-based to collaborative solution-finding
  - Removed confidence scores and timeline estimates
  - Focus on balanced analysis, trade-offs, and practical recommendations
  - Encourages models to build on each other's insights during refinement phase

## [6.2.1] - 2025-07-11

### Changed
- **Consensus Tool Simplified**: Removed step-based workflow parameters for cleaner interface
  - Changed from WorkflowTool to SimpleTool base class
  - Replaced `step` parameter with `prompt` for clarity
  - Removed unnecessary fields: `step_number`, `total_steps`, `next_step_required`, `findings`, `confidence`
  - Tool now inherits from ToolRequest instead of WorkflowRequest
  - Simplified test suite to match new interface
  - No functional changes - still parallel execution with cross-model feedback

### Improved
- **Tool Descriptions**: Reduced verbosity by 70-80% to preserve context
  - Chat tool: 297 → 66 words (78% reduction)
  - Consensus tool: 424 → 80 words (81% reduction)
  - Removed redundant use cases and implementation details
  - Focused on essential information for tool selection

### Removed
- **Workflow Infrastructure**: Removed unused workflow base classes and utilities
  - Deleted `tools/workflow/` directory and all its contents
  - Removed `WorkflowRequest`, `BaseWorkflowRequest`, and `ConsolidatedFindings` from base_models.py
  - Cleaned up imports in `tools/shared/__init__.py`
  - Removed obsolete workflow-based test files
  - No impact on functionality - workflow classes were no longer used after consensus simplification

## [6.2.0] - 2025-07-11

### Changed
- **Improved README**: Updated installation instructions to match original repository format
  - Added comprehensive uvx installation guide for Claude Desktop and Claude Code
  - Added proper shell command wrapper for cross-platform compatibility
  - Improved configuration documentation with detailed environment variables
  - Added collapsible sections for better organization

## [6.1.0] - 2025-07-11

### Added
- **Grok-4 Support**: Added support for xAI's latest Grok-4 model (grok-4-0709)
  - "grok" alias now defaults to grok-4 instead of grok-3
  - Added aliases: grok4, grok-4, grok-4-latest
  - Grok-4 supports extended thinking/reasoning capabilities
  - Updated tests and documentation

## [6.0.1] - 2025-07-11

### Changed
- **Breaking Change**: Removed stance-based analysis from consensus tool
  - Models no longer take for/against/neutral stances
  - Each model provides balanced, objective analysis
  - Simplified model configuration - just specify model name
  - System prompt updated to encourage balanced perspectives
  - All tests updated to work without stances

## [6.0.0] - 2025-07-11 - Simplified Fork

### Changed
- Simplified codebase to include only two essential tools: Chat and Consensus
- Updated documentation to reflect the streamlined architecture
- Reduced test suite to focus on the remaining tools
- **Major Enhancement**: Consensus tool completely redesigned for parallel execution with cross-model feedback
  - **Parallel Processing**: All models consulted simultaneously using asyncio.gather() (3x faster for 3 models)
  - **Two-Phase Workflow**:
    - Phase 1: Initial responses gathered from all models in parallel
    - Phase 2: Each model sees others' responses and can refine their position
  - **Cross-Model Learning**: Models incorporate insights from other perspectives, often converging toward consensus
  - **Single Atomic Operation**: Everything happens in one tool call (no more multi-step workflow)
  - **Robust Error Handling**: Individual model failures don't stop others (return_exceptions=True)
  - **Flexible Configuration**:
    - Enable/disable cross-feedback with `enable_cross_feedback` parameter
    - Custom refinement prompts via `cross_feedback_prompt` parameter
    - Same model can be used multiple times for different perspectives
  - **Response Structure**: Returns both initial and refined responses for comparison
  - **Performance**: ~2-3 seconds total for 3 models vs ~6-9 seconds sequential

### Removed
- Removed analyze tool
- Removed challenge tool
- Removed codereview tool
- Removed debug tool
- Removed docgen tool
- Removed listmodels tool
- Removed planner tool
- Removed precommit tool
- Removed refactor tool
- Removed secaudit tool
- Removed testgen tool
- Removed thinkdeep tool
- Removed tracer tool
- Removed version tool
- Removed associated test files for deleted tools
- Removed unused system prompts

### Maintained
- Full support for multiple AI providers (OpenAI, Gemini, xAI, OpenRouter, Ollama)
- Cross-tool conversation memory functionality
- File and image handling capabilities
- All core infrastructure and utilities

## Example: New Consensus Workflow

```python
# Single call to get consensus with cross-model feedback
arguments = {
    "prompt": "Should we implement real-time collaboration? 30% of support tickets request this feature",
    "models": [
        {"model": "gemini-pro"},
        {"model": "o3-mini"},
        {"model": "flash"}
    ],
    "enable_cross_feedback": true  # Enable two-phase refinement
}

# Returns both phases:
# 1. Initial responses (all models respond in parallel)
# 2. Refined responses (models adjust based on others' insights)
```

## Notes

This is a simplified fork of the original Zen MCP Server focused on providing just the essential Chat and Consensus tools for a streamlined experience. The parallel consensus workflow represents a major architectural improvement, providing faster and more nuanced multi-model analysis.