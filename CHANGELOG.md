# Changelog

## [2.1.0] - 2024-01-12

### Added
- **Grok-4 Support**: Added support for xAI's latest Grok-4 model (grok-4-0709)
  - "grok" alias now defaults to grok-4 instead of grok-3
  - Added aliases: grok4, grok-4, grok-4-latest
  - Grok-4 supports extended thinking/reasoning capabilities
  - Updated tests and documentation

## [2.0.0] - 2024-01-12

### Changed
- **Breaking Change**: Removed stance-based analysis from consensus tool
  - Models no longer take for/against/neutral stances
  - Each model provides balanced, objective analysis
  - Simplified model configuration - just specify model name
  - System prompt updated to encourage balanced perspectives
  - All tests updated to work without stances

## [Simplified Fork] - 2024-01-11

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
    "step": "Should we implement real-time collaboration?",
    "step_number": 1,
    "total_steps": 1,
    "next_step_required": false,
    "findings": "30% of support tickets request this feature",
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