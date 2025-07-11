# Zen MCP Server - Simplified

> **Note:** This is a fork based on [https://github.com/BeehiveInnovations/zen-mcp-server](https://github.com/BeehiveInnovations/zen-mcp-server)

A streamlined MCP (Model Context Protocol) server that provides two powerful AI tools for Claude Desktop and other MCP clients.

## Overview

This is a simplified fork of the original Zen MCP Server, focused on providing just two essential tools:

- **Chat**: Single-model conversational AI for brainstorming, discussions, and problem-solving
- **Consensus**: Multi-model parallel consensus gathering with cross-model refinement

The server supports multiple AI providers including OpenAI, Google Gemini, xAI, OpenRouter, and local models through Ollama or other OpenAI-compatible endpoints.

## Quick Start

### Prerequisites
- Python 3.10+ (3.12 recommended)
- At least one API key (OpenAI, Google Gemini, xAI, or OpenRouter)
- **Windows users**: WSL2 is required (see WSL Setup section below)

### Installation

#### Option 1: uvx (Recommended for Claude Desktop & Claude Code)

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
2. Add to your config file:
   - **Claude Desktop**:
     - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
     - Windows: `C:\Users\<username>\AppData\Roaming\Claude\claude_desktop_config.json`
   - **Claude Code CLI**: Create `.mcp.json` in your project root

```json
{
  "mcpServers": {
    "zen": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/FallDownTheSystem/zen-mcp-server.git", "zen-mcp-server"],
      "env": {
        "GEMINI_API_KEY": "your-key-here",
        "OPENAI_API_KEY": "your-key-here"
      }
    }
  }
}
```

3. Restart Claude Desktop or reload Claude Code CLI

#### Option 2: Traditional Setup

```bash
git clone https://github.com/FallDownTheSystem/zen-mcp-server.git
cd zen-mcp-server
./run-server.sh
```

For Claude Code CLI with traditional setup, you can configure it using:

**CLI Command (Recommended):**
```bash
# Project-specific (stored in .mcp.json)
claude mcp add -s project zen -e GEMINI_API_KEY=your-key -e OPENAI_API_KEY=your-key -- python /path/to/zen-mcp-server/server.py

# Or global/user-wide
claude mcp add -s user zen -e GEMINI_API_KEY=your-key -e OPENAI_API_KEY=your-key -- python /path/to/zen-mcp-server/server.py
```

**Manual Configuration:**
Add to your configuration file:
- **Project-specific**: `.mcp.json` in your project root
- **User-specific**: `.claude.json` (can contain global or project-specific MCP servers)

```json
{
  "mcpServers": {
    "zen": {
      "command": "python",
      "args": ["/path/to/zen-mcp-server/server.py"],
      "env": {
        "GEMINI_API_KEY": "your-key",
        "OPENAI_API_KEY": "your-key"
      }
    }
  }
}
```

### Configuration

Create a `.env` file with at least one API key:

```bash
# Native APIs (recommended)
GEMINI_API_KEY=your-key      # Google AI Studio
OPENAI_API_KEY=your-key      # OpenAI Platform
XAI_API_KEY=your-key         # X.AI Console

# OR use OpenRouter for multiple models
OPENROUTER_API_KEY=your-key

# OR use local models (Ollama example)
CUSTOM_API_URL=http://localhost:11434/v1
CUSTOM_MODEL_NAME=llama3.2
```

## Usage

Simply ask Claude naturally in your conversation:

- "Use chat to discuss this architecture"
- "Get consensus from o3, flash, and pro on whether to use microservices"
- "Chat with gemini about implementation strategies"
- "Use zen chat to brainstorm solutions" (Claude will pick the best model)

The server integrates seamlessly with Claude's interface - just mention the tool in your request.

## Key Features

### Conversation Memory & Context Revival
The server maintains conversation context across tool calls with a powerful context revival system:
- **Persistent Memory**: Conversations are stored with UUID-based threads that persist across Claude's context resets
- **Context Revival**: When Claude's context resets, other models can access the full conversation history and "remind" Claude of everything discussed
- **Cross-Tool Continuation**: Switch between chat and consensus tools while preserving complete context
- **Smart Prioritization**: Newest context is prioritized when token limits are reached
- **3-Hour Persistence**: Conversations remain in memory for 3 hours (configurable)

This means you can have multi-hour workflows where Claude orchestrates different models, and even after context resets, the conversation continues seamlessly.

### File and Image Support
Both tools support:
- **File Context**: Include code files, configs, or documentation for analysis
- **Image Analysis**: Analyze diagrams, screenshots, UI mockups, or architecture visuals
- **Directory Support**: Specify entire directories to analyze multiple files

### Auto Mode
When you don't specify a model, Claude intelligently selects the best one based on:
- Task complexity
- Required capabilities (vision, reasoning, speed)
- Context length requirements
- Cost optimization

### Localization Support
Configure response language with the `LOCALE` environment variable:
```bash
LOCALE=fr-FR  # French
LOCALE=zh-CN  # Chinese (Simplified)
LOCALE=ja-JP  # Japanese
# Any standard language code
```

## Tools

### Chat Tool

The chat tool provides single-model conversations with support for files, images, and web search. It's perfect for brainstorming, getting second opinions, exploring ideas, and general development discussions.

**Parameters:**
- `prompt` (required): Your question or topic
- `model`: Specific model to use (defaults to auto mode where Claude picks the best model)
- `files`: List of files to include for context
- `images`: Images for visual analysis (diagrams, screenshots, mockups)
- `temperature`: Response creativity from 0.0-1.0, default 0.5
- `thinking_mode`: Control reasoning depth - minimal/low/medium/high/max (Gemini only)
- `use_websearch`: Enable web search for current information (default: true)
- `continuation_id`: Continue a previous conversation

### Consensus Tool

The consensus tool orchestrates multiple AI models to provide diverse perspectives on your questions. It uses a powerful two-phase parallel workflow:

1. **Phase 1**: All models analyze your question independently and simultaneously
2. **Phase 2**: Each model sees the other responses and can refine their answer based on new insights

This approach is inspired by Grok 4's multi-agent system, where the real value comes from models spotting each other's breakthrough insights.

**Parameters:**
- `prompt` (required): The question or proposal to analyze
- `models` (required): List of models to consult (e.g., [{"model": "o3"}, {"model": "flash"}])
- `relevant_files`: Files for context
- `images`: Visual references (architecture diagrams, UI mockups, etc.)
- `enable_cross_feedback`: Allow models to see and refine based on others' responses (default: true)
- `temperature`: Response consistency from 0.0-1.0, default 0.2 for analytical responses
- `continuation_id`: Continue a previous consensus discussion

**Key Benefits:**
- **Faster** than sequential execution - all models work in parallel
- **Breakthrough discovery** - when one model finds the key insight, others can recognize and build on it
- **Robust error handling** - if one model fails, others continue without interruption
- **Evolution of thought** - see how perspectives change when models learn from each other

## Supported Models

The server supports a wide range of models from different providers:

### Native APIs
- **Google Gemini**
  - `pro` (Gemini 2.5 Pro): 1M context, extended thinking modes, deep analysis
  - `flash` (Gemini 2.0 Flash): 1M context, ultra-fast responses, perfect for quick tasks
- **OpenAI**
  - `o3`: Strong logical reasoning, 200K context
  - `o3-mini`: Balanced speed and quality, 200K context
  - `o4-mini`: Latest reasoning model, optimized for shorter contexts
  - `gpt4.1`: GPT-4 with 1M context window
- **xAI**
  - `grok-4`: Latest GROK model with advanced reasoning
  - `grok-3`: Previous generation, still highly capable
  - `grok-3-fast`: Faster variant with higher performance

### OpenRouter
Use OpenRouter to access multiple models through a single API key:
- GPT-4, Claude (Opus, Sonnet, Haiku)
- Llama models (70B, 405B)
- Mistral, Mixtral
- Many other commercial and open models

### Local Models
Run models locally for privacy and cost savings:
- **Ollama**: Easy local inference with models like Llama 3.2, Mistral
- **vLLM**: High-performance inference server
- **LM Studio**: User-friendly local model interface
- Any OpenAI-compatible API endpoint

## Advanced Configuration

### Environment Variables

```bash
# Model selection
DEFAULT_MODEL=auto              # Let Claude choose

# Logging
LOG_LEVEL=INFO                  # DEBUG for troubleshooting

# Conversation memory
CONVERSATION_TIMEOUT_HOURS=3
MAX_CONVERSATION_TURNS=20

# Model restrictions (optional)
GOOGLE_ALLOWED_MODELS=flash,pro
OPENAI_ALLOWED_MODELS=o3,o3-mini
```

### Thinking Modes (Gemini only)

Control the reasoning depth and token usage for Gemini models. Higher modes use more tokens but provide deeper analysis:

| Mode | Token Budget | Use Case |
|------|-------------|----------|
| `minimal` | 128 tokens | Quick tasks, simple questions |
| `low` | 2,048 tokens | Basic reasoning, straightforward problems |
| `medium` | 8,192 tokens | Default - balanced for most tasks |
| `high` | 16,384 tokens | Complex analysis, architecture decisions |
| `max` | 32,768 tokens | Maximum reasoning depth for critical problems |

### Custom Models

Configure model aliases and custom endpoints in `conf/custom_models.json`. This allows you to use simple names for complex model identifiers:

```json
{
  "model_aliases": {
    "llama": "llama3.2",
    "mistral": "mistral-nemo",
    "gpt4": "openai/gpt-4-turbo-preview"
  },
  "is_custom": true
}
```

Now you can use `"llama"` instead of `"llama3.2"` in your requests.

## Troubleshooting

### Viewing Logs

The server provides detailed logging to help diagnose issues:

- **Traditional install**: 
  ```bash
  tail -f logs/mcp_server.log        # Main server log
  tail -f logs/mcp_activity.log      # Tool execution log
  ```
- **uvx install**: Check Claude's developer console (View → Developer → Logs)

### Common Issues

1. **API Key Issues**
   - Ensure your API keys are correctly set in `.env` (traditional) or Claude config (uvx)
   - Check that keys don't have extra spaces or quotes
   - Verify keys are active on the provider's platform

2. **Model Not Found**
   - Check that the model name matches the provider's exact naming
   - Some models require specific API access (e.g., o3 requires OpenAI access)
   - Use `DEFAULT_MODEL=auto` to let Claude choose available models

3. **Connection Issues**
   - Verify your network connection
   - Check if API endpoints are accessible
   - For local models, ensure the server is running (e.g., `ollama serve`)
   - Firewall may block connections to local model servers

4. **uvx Installation Issues**
   - Ensure `uv` is installed and in your PATH
   - Verify Claude Desktop config JSON is valid (no trailing commas)
   - Restart Claude Desktop after configuration changes

## Development

For contributors and developers working on the Zen MCP Server:

```bash
# Run unit tests
python -m pytest tests/ -v

# Run integration tests (requires API keys)
./run_integration_tests.sh

# Run all code quality checks
./code_quality_checks.sh

# Run quick simulator tests
python communication_simulator_test.py --quick
```

Before submitting PRs, ensure all tests pass and code quality checks succeed.

## Platform-Specific Setup

### WSL Setup (Windows)

Windows users must use WSL2 for the Claude Code CLI. Here's the setup process:

```bash
# Update WSL and Ubuntu
sudo apt update && sudo apt upgrade -y

# Install required dependencies
sudo apt install -y python3-venv python3-pip curl git

# Install Node.js and npm (for Claude Code CLI)
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs

# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Clone and setup (in WSL, not Windows filesystem)
cd ~
git clone https://github.com/FallDownTheSystem/zen-mcp-server.git
cd zen-mcp-server
./run-server.sh
```

### Docker Deployment

For production environments, you can deploy using Docker:

```bash
# Clone the repository
git clone https://github.com/FallDownTheSystem/zen-mcp-server.git
cd zen-mcp-server

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Deploy with Docker Compose
./docker/scripts/deploy.sh      # Linux/macOS
.\docker\scripts\deploy.ps1     # Windows PowerShell
```

The Docker deployment includes:
- Health checks and auto-restart
- Volume persistence for logs
- Security hardening (non-root user, read-only filesystem)
- Resource limits and monitoring

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Acknowledgments

This is a simplified fork of the original [Zen MCP Server](https://github.com/BeehiveInnovations/zen-mcp-server) by Beehive Innovations.