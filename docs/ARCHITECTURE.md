# Converse MCP Server - Architecture Overview

## 🏗️ System Architecture

The Converse MCP Server follows a **functional, modular architecture** designed for simplicity, maintainability, and performance. It implements the Model Context Protocol (MCP) to provide AI capabilities through multiple providers.

## 📁 Project Structure

```
src/
├── index.js              # Main entry point & MCP server setup
├── config.js             # Configuration and environment management
├── systemPrompts.js      # System prompts for tools
├── providers/            # AI provider implementations
│   ├── registry.js       # Provider registry and management
│   ├── openai.js         # OpenAI provider implementation
│   ├── google.js         # Google/Gemini provider implementation
│   └── xai.js            # X.AI/Grok provider implementation
├── tools/                # MCP tool implementations
│   ├── chat.js           # Single-provider chat tool
│   └── consensus.js      # Multi-provider consensus tool
├── utils/                # Utility functions
│   ├── logger.js         # Structured logging
│   ├── context.js        # File and image processing
│   ├── continuation.js   # Conversation persistence
│   └── validators.js     # Input validation
bin/
├── converse.js           # CLI entry point for npx execution
docs/                     # Documentation
tests/                    # Test suites
```

## 🔄 Core Design Principles

### 1. Functional Programming
- **No Classes**: Pure functions and modules only
- **Immutable Data**: Avoid state mutations where possible
- **Composable Functions**: Small, focused, reusable functions
- **Error Boundaries**: Explicit error handling at module boundaries

### 2. Provider Abstraction
- **Unified Interface**: All providers implement consistent API
- **Auto-Discovery**: Providers register themselves dynamically
- **Graceful Degradation**: System works with any subset of providers
- **Parallel Execution**: Multiple providers can run simultaneously

### 3. Tool Architecture
- **Minimal Interface**: Tools expose simple, focused functionality
- **Context Processing**: Standardized file and image handling
- **Continuation Support**: Persistent conversation management
- **Parameter Validation**: Comprehensive input validation

## 🔌 MCP Integration Layer

### Server Setup
```javascript
// index.js - Main MCP server setup
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';

const server = new Server(
  { name: 'converse-mcp-server', version: '1.0.0' },
  { capabilities: { tools: {} } }
);
```

### Tool Registration
```javascript
// Dynamic tool registration
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  
  switch (name) {
    case 'chat':
      return await chatTool(args);
    case 'consensus':
      return await consensusTool(args);
    default:
      throw new McpError(ErrorCode.MethodNotFound, `Tool not found: ${name}`);
  }
});
```

## 🤖 Provider System

### Provider Registry Pattern
```javascript
// providers/registry.js
const providers = new Map();

export function registerProvider(name, implementation) {
  if (implementation.isAvailable()) {
    providers.set(name, implementation);
  }
}

export function getProvider(name) {
  return providers.get(name);
}

export function getAvailableProviders() {
  return Array.from(providers.keys());
}
```

### Provider Implementation Contract
```javascript
// Each provider must implement:
export const providerImplementation = {
  // Check if provider is configured and available
  isAvailable: () => Boolean(process.env.API_KEY),
  
  // Get supported models
  getSupportedModels: () => ['model1', 'model2'],
  
  // Main chat completion method
  chatCompletion: async (messages, options) => {
    // Implementation details...
    return {
      content: 'Response text',
      usage: { input_tokens: 100, output_tokens: 50 }
    };
  },
  
  // Provider name for logging/tracking
  name: 'provider-name'
};
```

### Model Resolution
```javascript
// Automatic model resolution across providers
export function resolveModel(modelName) {
  // Handle aliases (flash -> gemini-2.5-flash)
  const resolvedName = MODEL_ALIASES[modelName] || modelName;
  
  // Find provider that supports this model
  const provider = findProviderForModel(resolvedName);
  
  return { provider, model: resolvedName };
}
```

## 🛠️ Tool Architecture

### Tool Implementation Pattern
```javascript
// tools/example.js
export const exampleTool = {
  definition: {
    name: 'example',
    description: 'Example tool description',
    inputSchema: {
      type: 'object',
      properties: {
        prompt: { type: 'string', description: 'User prompt' }
      },
      required: ['prompt']
    }
  },
  
  handler: async (args) => {
    // 1. Validate input
    const validation = validateInput(args);
    if (!validation.valid) {
      throw new McpError(ErrorCode.InvalidParams, validation.error);
    }
    
    // 2. Process context (files, images)
    const context = await processContext(args.files, args.images);
    
    // 3. Execute main logic
    const result = await executeLogic(args, context);
    
    // 4. Return standardized response
    return formatResponse(result);
  }
};
```

### Context Processing Pipeline
```javascript
// utils/context.js
export async function processContext(files = [], images = []) {
  return {
    fileContext: await processFiles(files),
    imageContext: await processImages(images)
  };
}

async function processFiles(filePaths) {
  return await Promise.all(
    filePaths.map(async (path) => {
      const content = await readFile(path);
      return {
        path,
        content: addLineNumbers(content),
        metadata: { size: content.length, type: getFileType(path) }
      };
    })
  );
}
```

## 🔄 Data Flow

### Single Tool Execution (Chat)
```
User Request
    ↓
Input Validation
    ↓
Context Processing (files/images)
    ↓
Provider Selection (auto/manual)
    ↓
Model Resolution
    ↓
API Call to Provider
    ↓
Response Processing
    ↓
Continuation Management
    ↓
Response to Client
```

### Multi-Provider Execution (Consensus)
```
User Request
    ↓
Input Validation
    ↓
Context Processing
    ↓
Provider Selection (multiple)
    ↓
Parallel Execution ────┬─── Provider A
                       ├─── Provider B  
                       └─── Provider C
    ↓
Initial Response Collection
    ↓
Cross-Feedback Phase (optional)
    ↓
Parallel Refinement ───┬─── Provider A (sees B,C)
                       ├─── Provider B (sees A,C)
                       └─── Provider C (sees A,B)
    ↓
Final Response Aggregation
    ↓
Response to Client
```

## 🔧 Configuration System

### Environment-Driven Configuration
```javascript
// config.js
export const config = {
  // Provider API keys
  providers: {
    openai: { apiKey: process.env.OPENAI_API_KEY },
    google: { apiKey: process.env.GOOGLE_API_KEY },
    xai: { apiKey: process.env.XAI_API_KEY }
  },
  
  // Server settings
  server: {
    port: parseInt(process.env.PORT) || 3000,
    logLevel: process.env.LOG_LEVEL || 'info',
    maxOutputTokens: parseInt(process.env.MAX_MCP_OUTPUT_TOKENS) || 25000
  },
  
  // Model mappings and aliases
  models: {
    aliases: {
      'flash': 'gemini-2.5-flash',
      'pro': 'gemini-2.5-pro',
      'grok': 'grok-4-0709'
    }
  }
};
```

### Dynamic Provider Registration
```javascript
// index.js - Provider initialization
async function initializeProviders() {
  const providerModules = [
    await import('./providers/openai.js'),
    await import('./providers/google.js'),
    await import('./providers/xai.js')
  ];
  
  for (const module of providerModules) {
    const provider = module.default;
    if (provider.isAvailable()) {
      registerProvider(provider.name, provider);
      logger.info(`Registered provider: ${provider.name}`);
    }
  }
}
```

## 📊 State Management

### Stateless Design
- **No Global State**: Each request is independent
- **Continuation Storage**: Conversations stored as isolated state
- **Provider Independence**: Providers don't share state
- **Immutable Responses**: Responses are constructed, not modified

### Continuation System
```javascript
// utils/continuation.js
const continuations = new Map();

export function storeContinuation(id, data) {
  continuations.set(id, {
    ...data,
    lastAccessed: Date.now(),
    messageCount: (data.messageCount || 0) + 1
  });
}

export function getContinuation(id) {
  const continuation = continuations.get(id);
  if (continuation) {
    continuation.lastAccessed = Date.now();
  }
  return continuation;
}
```

## 🚀 Performance Characteristics

### Parallel Execution
- **Consensus Tool**: Executes all providers simultaneously
- **Non-Blocking I/O**: All async operations use Promise.all()
- **Provider Isolation**: One provider failure doesn't affect others
- **Request Batching**: Multiple requests handled concurrently

### Memory Management
- **Streaming Responses**: Large responses handled efficiently
- **Context Cleanup**: Old continuations automatically expire
- **File Processing**: Files read on-demand, not cached
- **Provider Pooling**: Connection reuse where possible

### Error Resilience
```javascript
// Graceful error handling pattern
async function executeWithFallback(primaryFn, fallbackFn) {
  try {
    return await primaryFn();
  } catch (primaryError) {
    logger.warn('Primary execution failed, attempting fallback', { 
      error: primaryError.message 
    });
    
    try {
      return await fallbackFn();
    } catch (fallbackError) {
      logger.error('Both primary and fallback failed', {
        primaryError: primaryError.message,
        fallbackError: fallbackError.message
      });
      throw new McpError(ErrorCode.InternalError, 'All execution attempts failed');
    }
  }
}
```

## 🔒 Security Architecture

### Input Validation
```javascript
// utils/validators.js
export function validateChatInput(args) {
  const errors = [];
  
  if (!args.prompt || typeof args.prompt !== 'string') {
    errors.push('prompt must be a non-empty string');
  }
  
  if (args.files && !Array.isArray(args.files)) {
    errors.push('files must be an array');
  }
  
  return { valid: errors.length === 0, errors };
}
```

### Path Security
```javascript
// Prevent path traversal attacks
function validateFilePath(filePath) {
  const normalized = path.resolve(filePath);
  const allowed = path.resolve(process.cwd());
  
  if (!normalized.startsWith(allowed)) {
    throw new McpError(ErrorCode.InvalidParams, 'Access denied: Path outside allowed directory');
  }
  
  return normalized;
}
```

### API Key Protection
- **Environment Variables**: Keys never hardcoded
- **No Logging**: API keys excluded from all logs
- **Provider Isolation**: Keys scoped to specific providers
- **Error Sanitization**: Error messages don't expose keys

## 🔍 Observability

### Structured Logging
```javascript
// utils/logger.js
export const logger = {
  info: (message, meta = {}) => {
    console.log(JSON.stringify({
      level: 'info',
      timestamp: new Date().toISOString(),
      message,
      ...meta
    }));
  },
  
  error: (message, error = {}) => {
    console.error(JSON.stringify({
      level: 'error',
      timestamp: new Date().toISOString(),
      message,
      error: {
        name: error.name,
        message: error.message,
        stack: error.stack
      }
    }));
  }
};
```

### Request Tracing
```javascript
// Request correlation IDs
function generateRequestId() {
  return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// All operations tagged with request ID
logger.info('Processing chat request', { 
  requestId, 
  provider: 'openai', 
  model: 'gpt-4o' 
});
```

## 📈 Extensibility

### Adding New Providers
1. Create provider module in `src/providers/`
2. Implement the provider contract
3. Export as default
4. Provider auto-registers if API key is available

### Adding New Tools
1. Create tool module in `src/tools/`
2. Define tool schema and handler
3. Register in main server setup
4. Add to MCP tool list

### Configuration Extensions
```javascript
// Adding new configuration options
export const config = {
  // ... existing config
  
  // New feature config
  experimental: {
    enableFeatureX: process.env.ENABLE_FEATURE_X === 'true',
    featureXTimeout: parseInt(process.env.FEATURE_X_TIMEOUT) || 30000
  }
};
```

## 🧪 Testing Architecture

### Test Strategy
- **Unit Tests**: Individual functions and modules
- **Integration Tests**: Provider interactions (mocked APIs)
- **E2E Tests**: Full request/response cycles
- **Contract Tests**: Provider interface compliance

### Test Organization
```
tests/
├── unit/              # Unit tests for individual functions
├── integration/       # Integration tests with mocked dependencies
├── e2e/              # End-to-end tests
├── fixtures/         # Test data and mocks
└── helpers/          # Test utilities
```

## 🔧 Development Workflow

### Hot Reload Development
```bash
# Development with auto-restart
npm run dev

# Debug mode with inspection
npm run debug
```

### Code Quality Pipeline
```bash
# Full validation pipeline
npm run validate

# Individual checks
npm run lint
npm run typecheck
npm run test
npm run format:check
```

---

This architecture emphasizes **simplicity**, **reliability**, and **extensibility** while maintaining high performance through parallel execution and efficient resource management.