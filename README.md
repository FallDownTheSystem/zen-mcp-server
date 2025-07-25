# Converse MCP Server

A simplified, functional Node.js implementation of an MCP (Model Context Protocol) server with chat and consensus tools. Built with modern Node.js practices and official SDKs for seamless AI provider integration.

## 🚀 Quick Start

### Option 1: Direct from GitHub (Recommended)

```bash
# Using npx (recommended)
npx FallDownTheSystem/converse

# Using pnpm dlx (alternative)
pnpm dlx FallDownTheSystem/converse

# Using yarn dlx (alternative)  
yarn dlx FallDownTheSystem/converse
```

### Option 2: Clone and Install

```bash
# Clone the repository
git clone https://github.com/FallDownTheSystem/converse.git
cd converse

# Install dependencies
npm install

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Start the server
npm start
```

## 📋 Requirements

- **Node.js**: >= 20.0.0 (LTS recommended)
- **Package Manager**: npm, pnpm, or yarn
- **API Keys**: At least one of OpenAI, Google, or X.AI

## 🔑 Configuration

### 1. Environment Variables

Create a `.env` file in your project root:

```bash
# Required: At least one API key
OPENAI_API_KEY=sk-proj-your_openai_key_here
GOOGLE_API_KEY=your_google_api_key_here  
XAI_API_KEY=xai-your_xai_key_here

# Optional: Server configuration
PORT=3000
LOG_LEVEL=info
MAX_MCP_OUTPUT_TOKENS=200000

# Optional: Provider-specific settings
GOOGLE_LOCATION=us-central1
XAI_BASE_URL=https://api.x.ai/v1
```

### 2. Get API Keys

| Provider | Where to Get | Example Format |
|----------|-------------|----------------|
| **OpenAI** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | `sk-proj-...` |
| **Google** | [makersuite.google.com/app/apikey](https://makersuite.google.com/app/apikey) | `AIzaSy...` |
| **X.AI** | [console.x.ai](https://console.x.ai/) | `xai-...` |

### 3. MCP Client Configuration

Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "converse": {
      "command": "npx",
      "args": ["FallDownTheSystem/converse"],
      "env": {
        "OPENAI_API_KEY": "your_key_here",
        "GOOGLE_API_KEY": "your_key_here",
        "XAI_API_KEY": "your_key_here"
      }
    }
  }
}
```

## 🛠️ Available Tools

### 1. Chat Tool

General conversational AI with context and continuation support.

```javascript
// Example usage
{
  "prompt": "How should I structure the authentication module for this Express.js API?",
  "model": "gemini-2.5-flash",
  "files": ["/path/to/src/auth.js", "/path/to/config.json"],
  "images": ["/path/to/architecture.png"],
  "temperature": 0.5,
  "reasoning_effort": "medium",
  "use_websearch": false
}
```

### 2. Consensus Tool

Multi-provider parallel execution with cross-model feedback.

```javascript
// Example usage
{
  "prompt": "Should we use microservices or monolith architecture for our e-commerce platform?",
  "models": [
    {"model": "o3"},
    {"model": "gemini-2.5-flash"},
    {"model": "grok-4-0709"}
  ],
  "relevant_files": ["/path/to/requirements.md"],
  "enable_cross_feedback": true,
  "temperature": 0.2
}
```

## 📊 Supported Models

### OpenAI Models
- **o3**: Strong reasoning (200K context)
- **o3-mini**: Fast O3 variant (200K context)  
- **o4-mini**: Latest reasoning model (200K context)
- **gpt-4o**: Multimodal flagship (128K context)
- **gpt-4o-mini**: Fast multimodal (128K context)

### Google/Gemini Models
- **gemini-2.5-flash** (alias: `flash`): Ultra-fast (1M context)
- **gemini-2.5-pro** (alias: `pro`): Deep reasoning (1M context)
- **gemini-2.0-flash**: Latest with experimental thinking

### X.AI/Grok Models  
- **grok-4-0709** (alias: `grok`): Latest advanced model (256K context)
- **grok-3**: Previous generation (131K context)
- **grok-3-fast**: Higher performance variant

## 🚀 Development

### Install from Source

```bash
# Clone and setup
git clone https://github.com/FallDownTheSystem/converse.git
cd converse
npm install

# Development with hot reload
npm run dev

# Run tests
npm test

# Run with specific log level
LOG_LEVEL=debug npm run dev
```

### Scripts Available

```bash
# Server management
npm start              # Start production server
npm run dev            # Development with hot reload
npm run dev:quiet      # Development with minimal logging

# Testing
npm test               # Run all tests
npm run test:unit      # Unit tests only
npm run test:integration # Integration tests
npm run test:real-api  # Real API tests (requires keys)
npm run test:coverage  # Coverage report

# Code quality
npm run lint           # Check code style
npm run lint:fix       # Fix code style issues
npm run format         # Format code with Prettier
npm run validate       # Full validation (lint + test)

# Utilities
npm run build          # Build for production
npm run debug          # Start with debugger
npm run check-deps     # Check for outdated dependencies
```

### Testing with Real APIs

```bash
# Set up your API keys in .env first
OPENAI_API_KEY=sk-proj-...
GOOGLE_API_KEY=AIzaSy...
XAI_API_KEY=xai-...

# Run real API tests
npm run test:real-api
```

## 📁 Project Structure

```
converse/
├── src/
│   ├── index.js              # Main server entry point
│   ├── config.js             # Configuration management
│   ├── router.js             # Central request dispatcher
│   ├── continuationStore.js  # State management
│   ├── systemPrompts.js      # Tool system prompts
│   ├── providers/            # AI provider implementations
│   │   ├── index.js          # Provider registry
│   │   ├── openai.js         # OpenAI provider
│   │   ├── xai.js            # XAI provider
│   │   └── google.js         # Google provider
│   ├── tools/                # MCP tool implementations
│   │   ├── index.js          # Tool registry
│   │   ├── chat.js           # Chat tool
│   │   └── consensus.js      # Consensus tool
│   └── utils/                # Utility modules
│       ├── contextProcessor.js # File/image processing
│       ├── errorHandler.js   # Error handling
│       └── logger.js         # Logging utilities
├── tests/                    # Comprehensive test suite
├── docs/                     # API and architecture docs
└── package.json              # Dependencies and scripts
```

## 🔧 Configuration Options

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `PORT` | Server port | `3000` | `3000` |
| `LOG_LEVEL` | Logging level | `info` | `debug`, `info`, `error` |
| `MAX_MCP_OUTPUT_TOKENS` | Token response limit | `25000` | `200000` |
| `GOOGLE_LOCATION` | Google API region | `us-central1` | `us-central1` |
| `XAI_BASE_URL` | XAI API endpoint | `https://api.x.ai/v1` | Custom endpoint |

### Model Selection

Use `"auto"` for automatic model selection, or specify exact models:

```javascript
// Auto-selection (recommended)
{ "model": "auto" }

// Specific models
{ "model": "gemini-2.5-flash" }
{ "model": "o3" }
{ "model": "grok-4-0709" }

// Using aliases
{ "model": "flash" }    // -> gemini-2.5-flash
{ "model": "pro" }      // -> gemini-2.5-pro
{ "model": "grok" }     // -> grok-4-0709
```

## 🐛 Troubleshooting

### Common Issues

**Server won't start:**
```bash
# Check Node.js version
node --version  # Should be >= 20.0.0

# Check for port conflicts
PORT=3001 npm start
```

**API key errors:**
```bash
# Verify your .env file format
cat .env

# Test API keys
npm run test:real-api
```

**Module import errors:**
```bash
# Clear cache and reinstall
npm run clean
```

### Debug Mode

```bash
# Enable debug logging
LOG_LEVEL=debug npm run dev

# Start with debugger
npm run debug

# Trace all operations
LOG_LEVEL=trace npm run dev
```

## 📚 Documentation

- **API Reference**: [docs/API.md](docs/API.md)
- **Architecture Guide**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Integration Examples**: [docs/EXAMPLES.md](docs/EXAMPLES.md)
- **Testing Guide**: [docs/TESTING.md](docs/TESTING.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `npm run validate`
5. Commit changes: `git commit -m 'Add amazing feature'`
6. Push to branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Development Setup

```bash
# Fork and clone your fork
git clone https://github.com/yourusername/converse.git
cd converse

# Install dependencies
npm install

# Create feature branch
git checkout -b feature/your-feature

# Make changes and test
npm run validate

# Commit and push
git add .
git commit -m "Description of changes"
git push origin feature/your-feature
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🔗 Links

- **GitHub**: https://github.com/FallDownTheSystem/converse
- **Issues**: https://github.com/FallDownTheSystem/converse/issues
- **NPM Package**: https://www.npmjs.com/package/converse-mcp-server

---

**Built with ❤️ using Node.js and modern AI APIs**