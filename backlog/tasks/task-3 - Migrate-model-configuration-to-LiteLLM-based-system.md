---
id: task-3
title: Migrate model configuration to LiteLLM-based system
status: To Do
assignee: []
created_date: '2025-07-14'
labels: []
dependencies:
  - task-2
---

## Description

Migrate all model configuration to LiteLLM's native config.yaml format. Define model aliases, fallbacks, and retries using LiteLLM's built-in configuration system rather than creating our own.

## Acceptance Criteria

- [ ] LiteLLM config.yaml created with model_list definitions
- [ ] Model aliases defined in LiteLLM native format
- [ ] Fallback chains configured for resilience
- [ ] Retry settings configured per model
- [ ] Special model metadata stored separately for app-specific needs

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
