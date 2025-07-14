---
id: task-2
title: Create LiteLLM provider wrapper
status: To Do
assignee: []
created_date: '2025-07-14'
labels: []
dependencies:
  - task-1
---

## Description

Implement a single LiteLLMProvider class that implements the existing ModelProvider interface. This provider will handle all models through LiteLLM's unified API, replacing the need for individual provider implementations.

## Acceptance Criteria

- [ ] LiteLLMProvider class implements ModelProvider interface
- [ ] Both sync and async generate_content methods work
- [ ] Streaming responses are properly handled
- [ ] LiteLLM exceptions are mapped to MCP error types
- [ ] Provider delegates all logic to LiteLLM (no custom retry/routing)

## Implementation Notes

Keep it minimal - let LiteLLM handle complexity. The wrapper should be a thin translation layer that only:
1. Calls litellm.completion() or litellm.acompletion()
2. Maps LiteLLM exceptions to MCP error types
3. Returns responses in the expected format
No custom retry logic or routing - that's configured in LiteLLM's config.yaml.
