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

## Implementation Notes

Use LiteLLM's native config.yaml format. For app-specific metadata (like thinking mode support), create a minimal separate config file. Example structure:
- model_list: Define aliases and litellm_params
- litellm_settings: Global settings like retries
- Separate metadata.yaml for Zen-specific features
