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

- Python 3.11+
- API keys for at least one provider (OpenAI, Google Gemini, etc.)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/FallDownTheSystem/zen-mcp-server.git
cd zen-mcp-server
```

2. Run the setup script:
```bash
./run-server.sh
```

This will:
- Set up a Python virtual environment
- Install dependencies
- Configure your API keys
- Set up MCP integration with Claude

### Configuration

The setup script will guide you through configuring your API keys. You can also manually edit `.env`:

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Google Gemini
GEMINI_API_KEY=...

# xAI (Grok)
XAI_API_KEY=...

# OpenRouter
OPENROUTER_API_KEY=...

# Custom/Local Models (e.g., Ollama)
CUSTOM_API_URL=http://localhost:11434
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
3. **xAI**: Grok models
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

Check server logs at:
```bash
tail -f logs/mcp_server.log
tail -f logs/mcp_activity.log
```

### Common Issues

1. **API Key Issues**: Ensure your API keys are correctly set in `.env`
2. **Model Not Found**: Check that the model name is correct for your provider
3. **Connection Issues**: Verify your network and API endpoint settings

## Contributing

Contributions are welcome! Please ensure all tests pass and code quality checks succeed before submitting PRs.

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Acknowledgments

This is a simplified fork of the original [Zen MCP Server](https://github.com/BeehiveInnovations/zen-mcp-server) by Beehive Innovations.