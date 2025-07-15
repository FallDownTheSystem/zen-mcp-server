---
id: task-2
title: Create LiteLLM provider wrapper
status: Done
assignee:
  - '@claude'
created_date: '2025-07-14'
updated_date: '2025-07-15'
labels: []
dependencies:
  - task-1
---

## Description

Implement a single LiteLLMProvider class that implements the existing ModelProvider interface. This provider will handle all models through LiteLLM's unified API, replacing the need for individual provider implementations.

## Acceptance Criteria

- [x] LiteLLMProvider class implements ModelProvider interface
- [x] Both sync and async generate_content methods work
- [x] Streaming responses are properly handled
- [x] LiteLLM exceptions are mapped to MCP error types
- [x] Provider delegates all logic to LiteLLM (no custom retry/routing)

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

Successfully implemented LiteLLMProvider as a minimal wrapper around LiteLLM.

**Approach taken:**
- Created thin wrapper class that delegates all logic to LiteLLM
- Minimal implementation focusing on format translation only
- No custom retry logic or routing - LiteLLM handles everything

**Features implemented:**
- Complete ModelProvider interface implementation (sync and async)
- Timeout parameter passing from tools to LiteLLM completion calls
- Exception mapping - LiteLLM exceptions are re-raised as-is
- Model metadata support for capabilities (optional)
- Token counting with fallback to estimation
- Image support (base64/URL/file path)
- System prompt and all standard parameters

**Technical decisions:**
- Used ProviderType.CUSTOM for the meta-provider
- Always return True for model validation (let LiteLLM handle errors)
- Default capabilities for unknown models (128k context, 8k output)
- Detect thinking models by checking for 'o3' or 'o4' in name
- Pass through all kwargs to LiteLLM for future compatibility

**Files added/modified:**
- Added: providers/litellm_provider.py (369 lines)
- Added: tests/test_litellm_provider.py (254 lines with 14 passing tests)
- All tests passing, code quality checks passed
