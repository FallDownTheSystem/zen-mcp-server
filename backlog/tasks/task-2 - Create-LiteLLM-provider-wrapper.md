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

## Implementation Plan

1. Analyze current ModelProvider interface and timeout handling patterns
2. Create LiteLLMProvider class with minimal wrapper approach
3. Implement timeout parameter passing from tools to LiteLLM
4. Map LiteLLM exceptions to existing MCP error types
5. Test with consensus tool timeout scenarios
6. Validate streaming response handling

## Implementation Notes

Keep it minimal - let LiteLLM handle complexity. The wrapper should be a thin translation layer that only:
1. Calls litellm.completion() or litellm.acompletion()
2. Maps LiteLLM exceptions to MCP error types
3. Returns responses in the expected format
4. **Preserves timeout parameter passing** - tools like consensus pass request-specific timeouts

**Timeout Handling Strategy:**
- Current consensus tool passes `timeout` parameter to providers
- LiteLLM natively supports timeout parameters in completion calls
- Preserve existing tool-level timeout logic (CONSENSUS_MODEL_TIMEOUT env var)
- Remove complex provider-level HTTP timeout configurations
- Let LiteLLM handle HTTP client timeout management

No custom retry logic or routing - that's configured in LiteLLM's config.yaml.
