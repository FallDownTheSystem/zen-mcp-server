# Advanced Usage Guide

This guide covers advanced features, configuration options, and workflows for power users of the Simplified Zen MCP server.

## Table of Contents

- [Model Configuration](#model-configuration)
- [Model Usage Restrictions](#model-usage-restrictions)
- [Thinking Modes](#thinking-modes)
- [Tool Parameters](#tool-parameters)
- [Context Revival: AI Memory Beyond Context Limits](#context-revival-ai-memory-beyond-context-limits)
- [Collaborative Workflows](#collaborative-workflows)
- [Working with Large Prompts](#working-with-large-prompts)
- [Vision Support](#vision-support)
- [Web Search Integration](#web-search-integration)
- [System Prompts](#system-prompts)

## Model Configuration

**For basic configuration**, see the [Configuration Guide](configuration.md) which covers API keys, model selection, and environment variables.

This section focuses on **advanced model usage patterns** for power users:

**Per-Request Model Override:**
Regardless of your default configuration, you can specify models per request:
- "Use **pro** for deep security analysis of auth.py"
- "Use **flash** to quickly format this code"
- "Use **o3** for logic analysis"
- "Use **o4-mini** for balanced analysis"
- "Use **gpt4.1** for comprehensive codebase analysis"

**Claude's Auto Mode Decision Matrix:**

| Model | Provider | Context | Strengths | Auto Mode Usage |
|-------|----------|---------|-----------|------------------|
| **`pro`** (Gemini 2.5 Pro) | Google | 1M tokens | Extended thinking (up to 32K tokens), deep analysis | Complex architecture, security reviews |
| **`flash`** (Gemini 2.0 Flash) | Google | 1M tokens | Ultra-fast responses | Quick checks, formatting, simple analysis |
| **`o3`** | OpenAI | 200K tokens | Strong logical reasoning | Logic analysis, systematic evaluation |
| **`o3-mini`** | OpenAI | 200K tokens | Balanced speed/quality | Moderate complexity tasks |
| **`o4-mini`** | OpenAI | 200K tokens | Latest reasoning model | Optimized for shorter contexts |
| **`gpt4.1`** | OpenAI | 1M tokens | Latest GPT-4 with extended context | Large codebase analysis, comprehensive reviews |
| **`llama`** (Llama 3.2) | Custom/Local | 128K tokens | Local inference, privacy | On-device analysis, cost-free processing |
| **Any model** | OpenRouter | Varies | Access to GPT-4, Claude, Llama, etc. | User-specified or based on task requirements |

**Mix & Match Providers:** Use multiple providers simultaneously! Set both `OPENROUTER_API_KEY` and `CUSTOM_API_URL` to access 
cloud models (expensive/powerful) AND local models (free/private) in the same conversation.

**Model Capabilities:**
- **Gemini Models**: Support thinking modes (minimal to max), web search, 1M context
- **O3 Models**: Excellent reasoning, systematic analysis, 200K context
- **GPT-4.1**: Extended context window (1M tokens), general capabilities

## Model Usage Restrictions

**For complete restriction configuration**, see the [Configuration Guide](configuration.md#model-usage-restrictions).

**Advanced Restriction Strategies:**

**Cost Control Examples:**
```env
# Development: Allow experimentation
GOOGLE_ALLOWED_MODELS=flash,pro
OPENAI_ALLOWED_MODELS=o4-mini,o3-mini

# Production: Cost-optimized  
GOOGLE_ALLOWED_MODELS=flash
OPENAI_ALLOWED_MODELS=o4-mini

# High-performance: Quality over cost
GOOGLE_ALLOWED_MODELS=pro
OPENAI_ALLOWED_MODELS=o3,o4-mini
```

**Important Notes:**
- Restrictions apply to all usage including auto mode
- `OPENROUTER_ALLOWED_MODELS` only affects OpenRouter models accessed via custom provider (where `is_custom: false` in custom_models.json)
- Custom local models (`is_custom: true`) are not affected by any restrictions

## Thinking Modes

**Claude automatically manages thinking modes based on task complexity**, but you can also manually control Gemini's reasoning depth to balance between response quality and token consumption. Each thinking mode uses a different amount of tokens, directly affecting API costs and response time.

### Thinking Modes & Token Budgets

These only apply to models that support customizing token usage for extended thinking, such as Gemini 2.5 Pro.

| Mode | Token Budget | Use Case | Cost Impact |
|------|-------------|----------|-------------|
| `minimal` | 128 tokens | Simple, straightforward tasks | Lowest cost |
| `low` | 2,048 tokens | Basic reasoning tasks | 16x more than minimal |
| `medium` | 8,192 tokens | **Default** - Most development tasks | 64x more than minimal |
| `high` | 16,384 tokens | Complex problems requiring thorough analysis | 128x more than minimal |
| `max` | 32,768 tokens | Exhaustive reasoning | 256x more than minimal |

### How to Use Thinking Modes

**Claude automatically selects appropriate thinking modes**, but you can override this by explicitly requesting a specific mode in your prompts. Remember: higher thinking modes = more tokens = higher cost but better quality:

#### Optimizing Token Usage & Costs

- For simple formatting, syntax fixes, or quick questions, use `minimal` thinking mode
- For standard development tasks, the default `medium` mode provides good balance
- Reserve `high` or `max` thinking for truly complex problems like architecture design or algorithm optimization
- Monitor your token usage to understand cost patterns

**Example cost optimization:**
```bash
# Low cost: Use flash with minimal thinking
"Use flash with minimal thinking to format this JSON"

# Standard cost: Default medium thinking
"Help me refactor this function" 

# High cost: Pro with max thinking for complex analysis
"Use pro with max thinking to design a distributed system architecture"
```

## Tool Parameters

The Simplified Zen MCP server provides two powerful tools, each with specific parameters:

### Available Tools

**`chat`** - General conversational AI with file and image support
- `prompt`: Your question or request (required)
- `model`: Specific model to use (required in non-auto mode)
- `files`: List of files to analyze (optional)
- `images`: Images for visual context (optional)
- `temperature`: Response temperature 0.0-1.0, default 0.5 (optional)
- `thinking_mode`: Control thinking depth for supported models (optional)
- `use_websearch`: Enable web search for current information (optional, default true)
- `continuation_id`: Continue a previous conversation (optional)

**`consensus`** - Multi-model consensus gathering
- `prompt`: The question or proposal (required)
- `models`: List of models to consult (required)
- `relevant_files`: Files for context (optional)
- `images`: Visual context (optional)
- `enable_cross_feedback`: Allow models to see each other's responses (optional, default true)
- `cross_feedback_prompt`: Custom refinement prompt (optional)
- `temperature`: Response temperature 0.0-1.0, default 0.2 (optional)
- `continuation_id`: Thread continuation ID (optional)

### Tool Examples

**Chat with file context:**
```
"Use flash to explain the authentication flow in auth.py"
```

**Consensus across multiple models:**
```
"Get consensus from o3, flash, and pro on the best approach for implementing rate limiting"
```

**Using continuation for follow-up:**
```
"Follow up on the previous discussion about rate limiting implementation"
```

## Context Revival: AI Memory Beyond Context Limits

**Context Revival** automatically preserves and reconstructs conversation context when token limits are reached. See the [Context Revival Guide](context-revival.md) for detailed information.

Key features:
- Automatic conversation summarization
- File context preservation across sessions
- Seamless conversation continuation
- Works with both chat and consensus tools

## Collaborative Workflows

The consensus tool enables powerful multi-model collaboration patterns:

### Getting Multiple Perspectives

Use consensus to gather insights from different models:
```
"Get consensus from flash, pro, and o3 on the security implications of this authentication approach"
```

### Cross-Model Refinement

With `enable_cross_feedback` (default true), models can see and refine based on each other's responses:
1. Each model provides initial analysis independently
2. Models review all responses and refine their insights
3. Final responses incorporate the best insights from all models

This is particularly powerful when one model spots a key insight that others can then build upon.

### Practical Workflow Examples

**Architecture Review:**
```
"Use consensus with o3, pro, and gpt4.1 to review this microservices architecture design"
```

**Security Analysis:**
```
"Get consensus from multiple models on potential security vulnerabilities in this API implementation"
```

## Working with Large Prompts

The Zen server intelligently handles large prompts and file contexts:

### Automatic Token Management
- Files are tokenized and managed within model limits
- Non-essential content is trimmed while preserving critical context
- Works seamlessly with 1M+ context models (Gemini, GPT-4.1)

### Best Practices
1. **Use appropriate models for large contexts**: Gemini Pro/Flash and GPT-4.1 support 1M tokens
2. **Let the server handle file loading**: Just specify file paths, the server optimizes inclusion
3. **Use directories for multiple files**: `"Analyze the src/ directory"`

## Vision Support

Both tools support image analysis with capable models:

### Supported Models
- **Gemini Models**: Excellent for complex diagrams, architecture visuals
- **OpenAI O3/O4 series**: Strong for visual analysis, error screenshots (up to 20MB total)
- **GPT-4.1**: General vision capabilities

### Vision Examples

**With Chat:**
```
"Explain the architecture shown in this diagram" [attach diagram.png]
```

**With Consensus:**
```
"Get consensus on the UX flow shown in these mockups" [attach mockup images]
```

### Best Practices
- Use appropriate models: Gemini for complex diagrams, O3 for analytical visuals
- Keep images under 20MB total when using multiple images
- Provide clear, high-quality images for best results

## Web Search Integration

Web search is enabled by default for the chat tool. The model intelligently determines when additional information from the web would enhance its response and provides specific search recommendations.

### How It Works
1. Model analyzes the request and identifies areas where current documentation, API references, or community solutions would be valuable
2. Searches are performed automatically within the tool execution
3. Results are integrated into the response with proper attribution

### Controlling Web Search
- Disable for a specific request: Set `use_websearch: false` in tool parameters
- Web search is particularly useful for:
  - Current API documentation
  - Recent best practices
  - Framework-specific solutions
  - Error resolution from community sources

## System Prompts

Each tool uses carefully crafted system prompts that define their behavior:

- **`chat`**: Flexible assistant ready to help with any development task
- **`consensus`**: Focused on finding breakthrough insights through multi-model collaboration

System prompts are maintained in the `systemprompts/` directory and can be customized if needed.

---

For more specific use cases and troubleshooting, see the [Troubleshooting Guide](troubleshooting.md).