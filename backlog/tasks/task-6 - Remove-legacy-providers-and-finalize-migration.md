---
id: task-6
title: Remove legacy providers and finalize migration
status: To Do
assignee: []
created_date: '2025-07-14'
labels: []
dependencies:
  - task-5
---

## Description

Remove all the old provider implementations and clean up the codebase. Ensure the system is fully migrated to LiteLLM with proper documentation updates. This completes the migration from custom providers to LiteLLM.

## Acceptance Criteria

- [ ] Feature parity checklist completed (streaming, errors, costs, metrics)
- [ ] All legacy provider files removed
- [ ] Provider registry simplified to use only LiteLLM
- [ ] Documentation updated to reflect new architecture
- [ ] All tests pass with new implementation
- [ ] Security scan for new dependencies passes

## Implementation Notes

Keep backups until fully validated. Run feature parity checklist before deleting any code. Add pip-audit or safety to CI pipeline for dependency scanning. Update CLAUDE.md with new simplified workflow.
