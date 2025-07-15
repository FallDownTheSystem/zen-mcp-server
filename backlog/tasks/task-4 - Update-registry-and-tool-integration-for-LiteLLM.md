---
id: task-4
title: Update registry and tool integration for LiteLLM
status: To Do
assignee: []
created_date: '2025-07-14'
labels: []
dependencies:
  - task-3
---

## Description

Modify the ModelProviderRegistry to use the single LiteLLMProvider for all models. Update how tools interact with the provider system to leverage LiteLLM's unified interface while maintaining backward compatibility.

## Acceptance Criteria

- [ ] ModelProviderRegistry updated to use LiteLLMProvider
- [ ] Provider type detection works with LiteLLM
- [ ] Model listing includes all LiteLLM-supported models
- [ ] Fallback model selection works correctly
- [ ] Tools (chat/consensus) work with new provider

## Implementation Plan

1. Analyze current consensus tool timeout passing mechanisms
2. Update ModelProviderRegistry to use single LiteLLMProvider
3. Ensure timeout parameters flow correctly from tools to provider
4. Test consensus tool timeout scenarios with new registry
5. Validate fallback behavior preserves timeout settings
6. Update provider detection logic for LiteLLM

## Implementation Notes

Registry should be simpler with one provider. 

**Timeout Integration Considerations:**
- Ensure consensus tool's timeout parameter (from CONSENSUS_MODEL_TIMEOUT) flows through registry to LiteLLMProvider
- Maintain backward compatibility for tools passing timeout in kwargs
- Registry should not modify or interfere with timeout values
- Test that timeout handling works correctly in fallback scenarios
- Verify that model selection doesn't affect timeout behavior
