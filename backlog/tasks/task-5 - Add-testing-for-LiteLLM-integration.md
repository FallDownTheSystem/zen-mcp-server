---
id: task-5
title: Add testing for LiteLLM integration
status: To Do
assignee: []
created_date: '2025-07-14'
labels: []
dependencies:
  - task-4
---

## Description

Create tests that verify the LiteLLM provider works correctly. Focus on mocking LiteLLM responses rather than making real API calls. Ensure critical features like temperature constraints and model resolution are tested.

## Acceptance Criteria

- [ ] Unit tests for LiteLLMProvider class created
- [ ] Mock LiteLLM responses for testing
- [ ] Integration smoke test with real API call (inexpensive model)
- [ ] Rate limit error handling verified
- [ ] Streaming response tests pass

## Implementation Plan

1. Research current timeout-related test cases in consensus tool tests
2. Create unit tests for LiteLLMProvider timeout handling
3. Mock LiteLLM responses with timeout scenarios
4. Add integration tests for consensus tool timeout behavior
5. Test fallback scenarios with timeout errors
6. Add performance tests for timeout configuration

## Implementation Notes

Use LiteLLM's mock capabilities when available. Include one real API call test to catch breaking changes or auth issues. Use pytest monkeypatch for mocking. Test rate limit handling by simulating 429 errors.

**Timeout-Specific Testing Requirements:**
- Test consensus tool timeout parameter passing through LiteLLMProvider
- Mock timeout exceptions from LiteLLM and verify proper error handling
- Test that CONSENSUS_MODEL_TIMEOUT environment variable is respected
- Verify timeout behavior in consensus tool parallel model execution
- Test that timeouts don't trigger retry loops (as fixed in commit e6fdb74)
- Add test cases for timeout hierarchy: tool > config > defaults
