# Converse MCP Server - Project Context

## Project Overview

The **Converse MCP Server** is a Node.js rewrite of the existing Python Zen MCP Server, designed with a simplified, functional architecture while maintaining complete feature parity. This project aims to create a more maintainable, easier-to-understand implementation using modern Node.js practices and official SDKs.

## Key Goals

1. **Complete Feature Parity**: Preserve all functionality from the Python version
2. **Simplified Architecture**: Eliminate complex inheritance and base classes
3. **Modern Node.js**: Use latest LTS, ESM modules, and official SDKs
4. **Functional Design**: Module-based with explicit dependencies and clear separation
5. **Easy Maintenance**: Clear code structure that's easy to extend and debug

## Core Features to Implement

### Tools
- **Chat Tool**: Single-provider conversational AI with context and continuation support
- **Consensus Tool**: Multi-provider parallel execution with response aggregation

### Providers  
- **OpenAI**: Using `openai` v5 SDK for GPT models
- **XAI**: Using OpenAI-compatible API for Grok models
- **Google**: Using `@google/genai` v1.11 SDK for Gemini models (NOT the deprecated `@google/generative-ai`)

### Key Features
- **Continuation Support**: Persistent conversation history across requests
- **File Context**: Process and include file contents in conversations
- **Image Support**: Handle image inputs for vision models
- **Web Search**: Integrate web search results as context
- **Parallel Execution**: Consensus tool calls all providers simultaneously

## Architecture Principles

### Functional, Module-Driven Design
- **No Classes/Inheritance**: Pure functional modules with consistent interfaces
- **Registry Pattern**: Tools and providers exported as simple object maps
- **Dependency Injection**: Router explicitly passes dependencies to tools
- **Pluggable Components**: Easy to swap implementations (e.g., continuation store)

### Unified Provider Interface
All providers implement: `async invoke(messages, options) => { content, stop_reason, rawResponse }`

### Configuration
- **Environment Variables Only**: No config files, all configuration via ENV vars
- **Runtime Validation**: Validate required API keys on startup
- **MCP Client Integration**: Support standard MCP server configuration patterns

## Project Structure
```
node/
├── src/
│   ├── index.js              # Main server entry point
│   ├── router.js             # Central request dispatcher  
│   ├── continuationStore.js  # State management (pluggable)
│   ├── providers/
│   │   ├── index.js          # Provider registry
│   │   ├── openai.js         # OpenAI provider
│   │   ├── xai.js            # XAI provider  
│   │   └── google.js         # Google provider
│   ├── tools/
│   │   ├── index.js          # Tool registry
│   │   ├── chat.js           # Chat tool
│   │   └── consensus.js      # Consensus tool
│   └── utils/
│       └── contextProcessor.js # Context processing
├── tests/                    # Comprehensive testing
├── docs/                     # API and architecture docs
└── package.json              # Minimal dependencies
```

## Development Workflow

### Implementation Standards
1. **Read This Document First**: Every task should reference this context
2. **Follow Functional Patterns**: Use the established architecture
3. **Test Everything**: Full integration testing, not just unit tests
4. **Document Changes**: Update relevant docs and add implementation notes
5. **Validate Against Python**: Ensure feature parity is maintained

### Testing Requirements
- **Integration Testing**: Run full MCP server and test real workflows
- **Provider Testing**: Test with real API calls (mocked for CI)
- **Edge Case Testing**: Handle failures, missing keys, etc.
- **Performance Testing**: Ensure parallel execution works correctly

### Key Dependencies
- `@modelcontextprotocol/sdk` - Official MCP TypeScript SDK
- `openai` v5.x - OpenAI official SDK  
- `@google/genai` v1.11+ - Google's new unified GenAI SDK
- `dotenv` - Environment variable loading
- Minimal additional dependencies, prefer Node.js built-ins

## Environment Configuration

All configuration via environment variables:
```bash
# Required API Keys
OPENAI_API_KEY=sk-...
XAI_API_KEY=xai-...
GOOGLE_API_KEY=...

# Optional Configuration
PORT=3000
GOOGLE_LOCATION=us-central1
XAI_BASE_URL=https://api.x.ai/v1
```

## Migration Path

1. **Parallel Development**: Keep Python implementation as reference
2. **Feature Validation**: Compare outputs between implementations  
3. **Full Integration Testing**: Validate all MCP protocol interactions
4. **Documentation**: Complete setup and API documentation
5. **Repository Migration**: Create new repository for Converse MCP Server
6. **Python Removal**: Remove Python implementation after successful migration

## Implementation Notes Guidelines

Each task implementer should:
1. **Read This Document**: Understand the full context and goals
2. **Check Dependencies**: Review what previous tasks have implemented  
3. **Follow Patterns**: Use established architecture and interfaces
4. **Test Integration**: Don't just unit test, run the full server
5. **Update Documentation**: Keep docs current with implementation
6. **Add Implementation Notes**: Document approach, decisions, and changes made

This context should provide every task with the necessary background to implement their part of the system correctly and consistently.