---
id: task-10
title: Implement Google Provider
status: To Do
assignee: []
created_date: '2025-07-25'
updated_date: '2025-07-25'
labels: []
dependencies:
  - task-9
priority: high
---

## Description

Create wrapper around @google/genai v1.11+ SDK (the new unified SDK, NOT the deprecated @google/generative-ai) for Gemini models, handling message format differences and normalizing to common interface
## Acceptance Criteria

- [ ] Google provider implements unified invoke(messages options) interface
- [ ] Uses official @google/genai v1.11+ SDK (NEW unified SDK)
- [ ] Message format conversion between common and Google formats
- [ ] Support for Gemini model selection (1.5 Pro 2.0 Flash etc)
- [ ] Response normalization matches other providers
- [ ] Error handling for Google AI API failures
- [ ] Safety settings and generation config support
- [ ] Confirms using NEW @google/genai not deprecated @google/generative-ai
