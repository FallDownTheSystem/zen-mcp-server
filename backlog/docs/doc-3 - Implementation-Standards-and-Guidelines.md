---
id: doc-3
title: Implementation Standards and Guidelines
type: reference
created_date: '2025-07-25'
---

# Implementation Standards and Guidelines

## Before Starting Any Task

### 1. Read Project Context
**ALWAYS** read `backlog/docs/doc-2 - Converse-MCP-Server---Project-Context.md` first to understand:
- Overall project goals and architecture
- Naming conventions (Converse MCP Server, not Zen)
- Environment-based configuration approach
- Testing requirements
- Dependencies and SDK choices

### 2. Review Dependencies
Check what previous tasks have implemented:
- Read implementation notes from completed dependency tasks
- Understand interfaces and patterns established
- Ensure consistency with existing code

### 3. Check Current State
- Review existing code in the repository
- Understand the current file structure
- Identify what needs to be modified vs created

## During Implementation

### Architecture Patterns to Follow

#### Functional Modules
- Use pure functions, avoid classes and inheritance
- Export consistent interfaces from modules
- Keep functions focused on single responsibilities

#### Provider Interface Standard
All providers must implement:
```javascript
export async function invoke(messages, options = {}) {
  // Implementation
  return {
    content: "response text",
    stop_reason: "stop_reason",
    rawResponse: originalResponse
  }
}
```

#### Tool Interface Standard  
All tools must implement:
```javascript
export async function run(params) {
  // params includes: messages, continuation, fileContext, images, webSearch, provider
  // Implementation
  return {
    type: 'text',
    content: 'response',
    continuation: { id: continuationId, messages: history }
  }
}
```

### Configuration Standards
- **NO CONFIG FILES**: Use environment variables only
- Load with `dotenv` for development
- Validate required variables on startup
- Follow MCP client configuration patterns

### Testing Requirements
- **Integration Testing Required**: Don't just unit test
- Run full MCP server and test real workflows
- Test with actual MCP clients where possible
- Test error conditions and edge cases
- Validate against Python implementation outputs

### Google SDK Requirement
- **MUST use `@google/genai` v1.11+** (the new unified SDK)
- **DO NOT use `@google/generative-ai`** (deprecated)
- This is critical for future compatibility

## After Implementation

### Implementation Notes Template
Add this section to your task file:

```markdown
## Implementation Notes

### Approach Taken
- Brief summary of implementation approach
- Key architectural decisions made
- Any deviations from original plan

### Features Implemented
- List of specific features added
- Integration points with other modules
- API interfaces exposed

### Technical Decisions
- Technology choices and rationale
- Trade-offs considered
- Performance considerations

### Files Modified/Added
- `path/to/file.js` - Description of changes
- `path/to/test.js` - Test coverage added
- `docs/api.md` - Documentation updated

### Integration Testing Results
- Tests performed and results
- Performance measurements
- Comparison with Python implementation (if applicable)

### Known Issues/Limitations
- Any temporary limitations
- Future improvements needed
- Dependencies on other tasks
```

### Documentation Updates
Update these files as appropriate:
- `README.md` - If user-facing changes
- `docs/API.md` - For API changes
- `docs/ARCHITECTURE.md` - For structural changes
- Test documentation

### Quality Checklist
Before marking task as Done:
- [ ] All acceptance criteria checked off
- [ ] Implementation notes added with required sections
- [ ] Integration tests passing
- [ ] No regressions in existing functionality
- [ ] Documentation updated
- [ ] Code follows established patterns
- [ ] Environment variables properly handled
- [ ] Error handling implemented
- [ ] Logging added where appropriate

## Common Patterns

### Error Handling
```javascript
try {
  // Implementation
} catch (error) {
  console.error(`Error in ${module}:`, error);
  throw new Error(`${module} failed: ${error.message}`);
}
```

### Environment Variable Loading
```javascript
import 'dotenv/config';

const requiredEnvVars = ['OPENAI_API_KEY', 'GOOGLE_API_KEY'];
for (const envVar of requiredEnvVars) {
  if (!process.env[envVar]) {
    throw new Error(`Required environment variable ${envVar} not found`);
  }
}
```

### Module Registry Pattern
```javascript
// providers/index.js
import * as openai from './openai.js';
import * as google from './google.js';
import * as xai from './xai.js';

export const providers = {
  openai: openai,
  google: google,
  xai: xai
};
```

This ensures consistency across all task implementations and maintains the quality and architecture integrity of the Converse MCP Server.
