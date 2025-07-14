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

## Implementation Notes

Registry should be simpler with one provider
