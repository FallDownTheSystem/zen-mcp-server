---
id: task-3
title: Migrate model configuration to LiteLLM-based system
status: Done
assignee:
  - '@claude'
created_date: '2025-07-14'
updated_date: '2025-07-15'
labels: []
dependencies:
  - task-2
---

## Description

Migrate all model configuration to LiteLLM's native config.yaml format. Define model aliases, fallbacks, and retries using LiteLLM's built-in configuration system rather than creating our own.

## Acceptance Criteria

- [x] LiteLLM config.yaml created with model_list definitions
- [x] Model aliases defined in LiteLLM native format
- [x] Fallback chains configured for resilience
- [x] Retry settings configured per model
- [x] Special model metadata stored separately for app-specific needs

## Implementation Plan

1. Research current timeout configurations and environment variables
2. Design LiteLLM config.yaml structure with timeout settings
3. Map existing model aliases to LiteLLM format
4. Configure retry and timeout settings per model type
5. Create separate metadata file for Zen-specific features
6. Test timeout behavior with consensus tool scenarios
## Implementation Notes

Use LiteLLM's native config.yaml format. For app-specific metadata (like thinking mode support), create a minimal separate config file. Example structure:
- model_list: Define aliases and litellm_params
- litellm_settings: Global settings like retries and timeouts
- Separate metadata.yaml for Zen-specific features

**Timeout Configuration Migration:**
- Map current CONSENSUS_MODEL_TIMEOUT (600s default) to LiteLLM settings
- Configure request_timeout: 600s as global default
- Set connect_timeout: 30s for connection handling
- Remove custom HTTP timeout environment variables (CUSTOM_*_TIMEOUT)
- Preserve consensus tool's ability to override timeouts per request
- Document timeout hierarchy: tool-level > config-level > LiteLLM defaults

Successfully migrated all model configurations to LiteLLM's native format.

**Approach taken:**
- Created comprehensive litellm_config.yaml with all models and aliases
- Separated Zen-specific metadata into model_metadata.yaml
- Preserved all existing model aliases and timeout configurations
- Maintained timeout hierarchy: tool > model > global > defaults

**Features implemented:**
- Complete model_list with all supported models
- Model aliases using LiteLLM's model_alias field
- Fallback chains for resilience (gemini-2.5-flash → gpt-4.1 → grok-3-fast)
- Context window fallbacks for large prompts
- Retry policies per error type
- Model-specific timeouts (e.g., 1200s for deep research)
- Temperature constraints (O3/O4 fixed at 1.0)

**Technical decisions:**
- Used LiteLLM's native YAML format for all configuration
- Kept Zen-specific metadata separate (thinking mode, image support)
- Set global timeout to 600s matching CONSENSUS_MODEL_TIMEOUT
- Enabled drop_params to handle provider differences
- Disabled caching by default for consistency

**Files added/modified:**
- Modified: litellm_config.yaml (195 lines, complete rewrite)
- Added: model_metadata.yaml (181 lines)
- Added: docs/litellm_migration.md (migration guide)
- All configuration tests passed
