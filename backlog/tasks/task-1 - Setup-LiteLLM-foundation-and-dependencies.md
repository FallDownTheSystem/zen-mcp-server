---
id: task-1
title: Setup LiteLLM foundation and dependencies
status: To Do
assignee: []
created_date: '2025-07-14'
labels: []
dependencies: []
---

## Description

Install LiteLLM and create basic configuration structure. This is the foundation for migrating from custom provider implementations to LiteLLM's unified interface.

## Acceptance Criteria

- [ ] LiteLLM is added to requirements.txt with pinned version
- [ ] LiteLLM config.yaml created with model aliases and settings
- [ ] Environment variable handling for API keys works
- [ ] LiteLLM can make successful sync and async test calls
- [ ] Streaming response test passes

## Implementation Notes

Initial setup focusing on minimal configuration. Use LiteLLM's native config.yaml format instead of custom configuration. Pin exact version (e.g., litellm==1.38.5) to prevent breaking changes.
