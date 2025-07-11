# Zen MCP Server - Simplified

A streamlined MCP (Model Context Protocol) server that provides two powerful AI tools for Claude Desktop and other MCP clients.

## Overview

This is a simplified fork of the original Zen MCP Server, reduced to just two essential tools:
- **Chat**: General conversational AI for brainstorming and discussions
- **Consensus**: Multi-model consensus gathering for complex decisions

## Features

- 🤖 **Multiple AI Provider Support**: OpenAI, Google Gemini, xAI, OpenRouter, Ollama, and custom endpoints
- 💬 **Chat Tool**: Interactive development chat and collaborative thinking
- 🤝 **Consensus Tool**: Get perspectives from multiple AI models on the same question
- 🔄 **Cross-Tool Conversation Memory**: Maintain context across different tool calls
- 📁 **Smart File Handling**: Automatic file reading and context management

## Quick Start

### Prerequisites

- Python 3.10+ (3.12 recommended)
- Git
- **Windows users**: WSL2 is required for Claude Code CLI

### Get API Keys (at least one required)

**Option A: OpenRouter (Access multiple models with one API)**
- **OpenRouter**: Visit [OpenRouter](https://openrouter.ai/) for access to multiple models through one API

**Option B: Native APIs**
- **Gemini**: Visit [Google AI Studio](https://makersuite.google.com/app/apikey) and generate an API key
- **OpenAI**: Visit [OpenAI Platform](https://platform.openai.com/api-keys) to get an API key for O3 model access
- **X.AI**: Visit [X.AI Console](https://console.x.ai/) to get an API key for GROK model access

**Option C: Custom API Endpoints (Local models like Ollama, vLLM)**
- **Ollama**: Run models like Llama 3.2 locally for free inference
- **vLLM**: Self-hosted inference server for high-throughput inference
- **Any OpenAI-compatible API**: Custom endpoints for your own infrastructure

### Installation

#### Option A: Quick Install with uvx

**Prerequisites**: Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first (required for uvx)

<details>
<summary>Claude Desktop Configuration</summary>

Add this to your Claude Desktop config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "zen": {
      "command": "sh",
      "args": [
        "-c",
        "exec $(which uvx || echo uvx) --from git+https://github.com/FallDownTheSystem/zen-mcp-server.git zen-mcp-server"
      ],
      "env": {
        "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:~/.local/bin",
        "OPENAI_API_KEY": "your_api_key_here",
        "GEMINI_API_KEY": "your_gemini_key_here",
        "XAI_API_KEY": "your_xai_key_here"
      }
    }
  }
}
```
</details>

<details>
<summary>Claude Code CLI Configuration</summary>

Create a `.mcp.json` file in your project root:
```json
{
  "mcpServers": {
    "zen": {
      "command": "sh",
      "args": [
        "-c",
        "exec $(which uvx || echo uvx) --from git+https://github.com/FallDownTheSystem/zen-mcp-server.git zen-mcp-server"
      ],
      "env": {
        "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:~/.local/bin",
        "OPENAI_API_KEY": "your_api_key_here",
        "GEMINI_API_KEY": "your_gemini_key_here",
        "XAI_API_KEY": "your_xai_key_here"
      }
    }
  }
}
```
</details>

**What this does:**
- **Zero setup required** - uvx handles everything automatically
- **Always up-to-date** - Pulls latest version on each run
- **No local dependencies** - Works without Python environment setup
- **Instant availability** - Ready to use immediately

#### Option B: Traditional Clone and Set Up

```bash
# Clone to your preferred location
git clone https://github.com/FallDownTheSystem/zen-mcp-server.git
cd zen-mcp-server

# One-command setup installs Zen in Claude
./run-server.sh

# To view MCP configuration for Claude
./run-server.sh -c

# See help for more
./run-server.sh --help
```

**What this does:**
- **Sets up everything automatically** - Python environment, dependencies, configuration
- **Configures Claude integrations** - Adds to Claude Code CLI and guides Desktop setup
- **Ready to use immediately** - No manual configuration needed

**After updates:** Always run `./run-server.sh` again after `git pull` to ensure everything stays current.

### Add Your API Keys

```bash
# Edit .env to add your API keys (if not already set in environment)
nano .env

# The file will contain, at least one should be set:
# GEMINI_API_KEY=your-gemini-api-key-here  # For Gemini models
# OPENAI_API_KEY=your-openai-api-key-here  # For O3 model
# XAI_API_KEY=your-xai-api-key-here        # For Grok models
# OPENROUTER_API_KEY=your-openrouter-key   # For OpenRouter

# For local models (Ollama, vLLM, etc.):
# CUSTOM_API_URL=http://localhost:11434/v1  # Ollama example
# CUSTOM_API_KEY=                          # Empty for Ollama
# CUSTOM_MODEL_NAME=llama3.2              # Default model

# Note: At least one API key OR custom URL is required
```

**No restart needed**: The server reads the .env file each time Claude calls a tool, so changes take effect immediately.

**Next**: Now run `claude` from your project folder using the terminal for it to connect to the newly added mcp server.

#### If Setting up for Claude Desktop

**Need the exact configuration?** Run `./run-server.sh -c` to display the platform-specific setup instructions with correct paths.

1. **Open Claude Desktop config**: Settings → Developer → Edit Config
2. **Copy the configuration** shown by `./run-server.sh -c` into your `claude_desktop_config.json`
3. **Restart Claude Desktop** for changes to take effect

### Start Using It!

Just ask Claude naturally:
- "Use zen chat to discuss implementation strategies" → Claude picks best model + `chat`
- "Get consensus from multiple models about whether we should migrate to microservices" → Multi-model analysis
- "Chat with gemini about this architecture design" → Uses Gemini specifically
- "Use o3 to analyze this complex algorithm" → Uses O3 specifically

## Configuration

Configure the Zen MCP Server through environment variables. For uvx installation, add these to your Claude configuration. For traditional installation, use the `.env` file.

### Environment Variables

**API Keys** (at least one required):
```bash
# Native APIs
OPENAI_API_KEY=your-openai-key      # For O3, O4-mini models
GEMINI_API_KEY=your-gemini-key      # For Gemini Pro/Flash models
XAI_API_KEY=your-xai-key            # For Grok-4, Grok-3 models
OPENROUTER_API_KEY=your-key         # For OpenRouter access

# Custom/Local Models (e.g., Ollama)
CUSTOM_API_URL=http://localhost:11434/v1
CUSTOM_API_KEY=                     # Empty for Ollama
CUSTOM_MODEL_NAME=llama3.2         # Default model
```

**Configuration Options**:
```bash
# Model Selection
DEFAULT_MODEL=auto                  # auto, flash, pro, o3, grok, etc.

# Logging
LOG_LEVEL=INFO                      # DEBUG, INFO, WARNING, ERROR

# Conversation Settings
CONVERSATION_TIMEOUT_HOURS=3        # How long conversations persist
MAX_CONVERSATION_TURNS=20           # Max turns in AI-to-AI conversations

# Model Restrictions (optional)
OPENAI_ALLOWED_MODELS=o3,o4-mini   # Comma-separated list
GOOGLE_ALLOWED_MODELS=flash,pro     # Comma-separated list
XAI_ALLOWED_MODELS=grok-4           # Comma-separated list
```

## Available Tools

### 1. Chat Tool

General-purpose conversational AI for brainstorming, discussions, and problem-solving.

**Usage in Claude:**
```
Use the chat tool to discuss implementation strategies for our new feature
```

**Features:**
- Interactive conversations
- File context support
- Image analysis capabilities
- Configurable temperature and model selection

### 2. Consensus Tool

Parallel multi-model consensus gathering with cross-model feedback. All models are consulted simultaneously, then given a chance to refine their responses based on other models' insights.

**Usage in Claude:**
```
Use the consensus tool to evaluate whether we should migrate to microservices
```

**Features:**
- **Parallel Execution**: All models consulted simultaneously (not sequentially)
- **Two-Phase Workflow**: 
  - Phase 1: Initial responses from all models in parallel
  - Phase 2: Each model sees others' responses and can refine their answer
- **Cross-Model Learning**: Models incorporate insights from other perspectives
- **Robust Error Handling**: If one model fails, others continue without interruption
- **Flexible Configuration**: 
  - Enable/disable cross-feedback phase
  - Custom refinement prompts
  - Same model can be used multiple times
- **Single Tool Call**: Everything happens in one atomic operation

**Example Workflow:**
1. You ask: "Should we implement real-time collaboration?"
2. Multiple models respond in parallel with their perspectives
3. Each model sees the others' responses
4. Models refine their positions based on collective insights
5. You receive both initial and refined responses for comparison

**Benefits:**
- **Faster Results**: Parallel execution vs sequential (3x faster for 3 models)
- **Better Decisions**: Models learn from each other's perspectives
- **Nuanced Analysis**: Different perspectives often converge toward consensus
- **Comprehensive View**: See how opinions evolve with new information

## Model Configuration

### Supported Providers

1. **OpenAI**: GPT-4, O3 models
2. **Google Gemini**: Gemini Pro, Gemini Flash
3. **xAI**: Grok-4 (latest), Grok-3, Grok-3-fast models
4. **OpenRouter**: Access to multiple models
5. **Ollama**: Local model support
6. **Custom**: Any OpenAI-compatible endpoint

### Model Selection

You can specify models in your tool calls:
```
Use the chat tool with model gemini-pro to explain this code
```

Or use model aliases:
```
Use consensus with models flash and o3-mini to evaluate this approach
```

## Development

### Running Tests

```bash
# Run unit tests
python -m pytest tests/ -v

# Run integration tests
./run_integration_tests.sh

# Run simulator tests (quick mode)
python communication_simulator_test.py --quick
```

### Code Quality

```bash
# Run all quality checks
./code_quality_checks.sh
```

## Troubleshooting

### Logs

For traditional installation, check server logs at:
```bash
tail -f logs/mcp_server.log
tail -f logs/mcp_activity.log
```

For uvx installation with Claude Desktop, check Claude's developer console for logs.

### Common Issues

1. **API Key Issues**: 
   - For uvx: Ensure your API keys are correctly set in Claude Desktop config
   - For traditional: Ensure your API keys are correctly set in `.env`

2. **Model Not Found**: Check that the model name is correct for your provider

3. **Connection Issues**: Verify your network and API endpoint settings

4. **uvx Installation Issues**:
   - Make sure `uv` is installed and in your PATH
   - Try running `uvx --version` to verify installation
   - Ensure Claude Desktop config JSON is valid (no trailing commas, proper quotes)
   - Restart Claude Desktop after config changes

## Contributing

Contributions are welcome! Please ensure all tests pass and code quality checks succeed before submitting PRs.

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Acknowledgments

This is a simplified fork of the original [Zen MCP Server](https://github.com/BeehiveInnovations/zen-mcp-server) by Beehive Innovations.