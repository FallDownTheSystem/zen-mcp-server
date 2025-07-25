---
id: task-7
title: Implement Central Router
status: Done
assignee:
  - '@myself'
created_date: '2025-07-25'
labels: []
dependencies:
  - task-6
priority: medium
---

## Description

Create the single orchestration point with dependency injection that dispatches requests to tools with all necessary dependencies

## Acceptance Criteria

- [x] Router function handles MCP request dispatching
- [x] Tool lookup based on request tool name
- [x] Dependency injection for providers and utilities
- [x] Error handling for unknown tools
- [x] Consistent error response format
- [x] Integration with MCP SDK request/response cycle

## Implementation Notes

Successfully implemented comprehensive central router as single orchestration point with dependency injection and enhanced error handling. All acceptance criteria met:

**Approach Taken:**
- Enhanced existing router with comprehensive error handling and validation
- Implemented single unified request handler for all tool calls with proper dispatching
- Added robust dependency injection system with validation and error recovery
- Created standardized error response format for consistent error handling
- Integrated health check and monitoring endpoints for operational visibility

**Features Implemented:**
- **MCP Request Dispatching**: Unified `CallToolRequestSchema` handler with tool lookup and execution
- **Tool Validation**: Comprehensive tool existence, callability, and argument validation
- **Dependency Injection**: Enhanced system injecting config, providers, continuation store, and utilities
- **Error Handling**: Custom `RouterError` class with detailed error codes and context
- **Consistent Responses**: Standardized `createErrorResponse()` function for all error scenarios
- **Health Monitoring**: Built-in health check endpoint and router statistics
- **Enhanced Logging**: Detailed execution timing and error logging with request context

**Technical Decisions:**
- Used single request handler pattern instead of per-tool handlers for better centralization
- Implemented comprehensive validation pipeline (tool existence → arguments → execution)
- Added execution timing and request tracking for monitoring and debugging
- Used functional error handling with consistent error response format
- Included development vs production error detail levels (stack traces in dev only)
- Added router health checks and statistics endpoints for operational monitoring

**Dependency Injection System:**
The router creates and validates a comprehensive dependencies object:
```javascript
{
  config,                    // Configuration with provider settings
  continuationStore,         // Conversation state management
  providers,                 // AI provider registry
  contextProcessor,          // File/image/web search processing
  router: {                  // Router utilities
    createErrorResponse,
    validateToolArguments
  }
}
```

**Error Response Format:**
Standardized error format across all failure scenarios:
```javascript
{
  content: [{ type: 'text', text: 'Error message' }],
  isError: true,
  error: {
    type: 'ErrorType',
    code: 'ERROR_CODE',
    message: 'Detailed message',
    toolName: 'failing-tool',
    timestamp: '2025-01-25T...',
    // Additional context...
  }
}
```

**Enhanced Tool Validation:**
- **Tool Existence**: Validates tool exists in registry and is callable
- **Argument Validation**: JSON schema validation with detailed error messages
- **Type Checking**: Validates argument types, string lengths, required fields
- **Error Context**: Provides detailed validation failure information

**MCP SDK Integration:**
- Full integration with `@modelcontextprotocol/sdk` request/response cycle
- Proper `CallToolRequestSchema` handling with request parameter extraction
- Enhanced `tools/list` endpoint with metadata and tool information
- Added custom `router/health` endpoint for monitoring

**Files Modified:**
- `src/router.js` - Complete enhancement with centralized orchestration
- Added `RouterError` custom error class with error codes
- Added `createErrorResponse()` for consistent error formatting
- Added `createDependencies()` with comprehensive validation
- Enhanced `validateToolArguments()` with JSON schema validation
- Added health check and statistics endpoints
- Integrated execution timing and detailed logging

**Integration Testing Results:**
- All error response creation working correctly with proper format
- Tool argument validation handling all edge cases (missing, wrong type, length)
- RouterError class providing detailed error information with codes
- Router creation properly validating dependencies and failing gracefully
- Validation working for various schema patterns and edge cases
- Request dispatching ready for tool implementation

**Key Benefits:**
- **Centralization**: Single orchestration point for all MCP requests
- **Reliability**: Comprehensive error handling prevents crashes and provides debugging info
- **Monitoring**: Built-in health checks and statistics for operational visibility
- **Consistency**: Standardized error format and response patterns across all tools
- **Extensibility**: Easy to add new tools and providers through registry pattern
- **Performance**: Execution timing and monitoring for performance optimization
- **Security**: Input validation and error isolation prevent malicious requests
