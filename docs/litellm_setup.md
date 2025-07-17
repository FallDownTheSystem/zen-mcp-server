# LiteLLM Setup Documentation

## Overview

LiteLLM has been successfully integrated into the Zen MCP Server as the foundation for unified LLM API access. This setup provides a single interface to call multiple LLM providers using OpenAI's format.

## Installation

LiteLLM has been added to `requirements.txt`:
```
litellm>=1.74.3  # Unified LLM API interface
```

## Configuration

The LiteLLM configuration is defined in `litellm_config.yaml` with the following structure:

### Model Definitions
- **OpenAI Models**: o3, o3-mini, o4-mini, gpt-4.1-2025-04-14
- **Google Gemini Models**: gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash, gemini-2.0-flash-lite
- **X.AI GROK Models**: grok-4-0709, grok-3, grok-3-fast

Each model is configured with:
- Model name (alias for internal use)
- LiteLLM parameters (provider/model format, API key reference, temperature, max_tokens)

### Router Settings
- **Fallback Support**: Enabled with fallback models defined
- **Retry Policy**: Configured for different error types
- **Allowed Fails**: Set to 3 before switching to fallback

### LiteLLM Settings
- **Request Timeout**: 600 seconds (matching CONSENSUS_MODEL_TIMEOUT)
- **Connect Timeout**: 30 seconds
- **Drop Params**: Enabled to handle provider-specific parameter restrictions

## Environment Variables

API keys are loaded from environment variables:
- `OPENAI_API_KEY` - For OpenAI models
- `GOOGLE_API_KEY` - For Google Gemini models
- `XAI_API_KEY` - For X.AI GROK models
- `DIAL_API_KEY` - For DIAL unified access
- `OPENROUTER_API_KEY` - For OpenRouter access

## Key Features Configured

1. **Unified Interface**: All models accessible through LiteLLM's standard API
2. **Automatic Parameter Handling**: `drop_params=true` handles provider-specific restrictions
3. **Timeout Management**: Global timeout of 600s with 30s connection timeout
4. **Error Resilience**: Retry policies and fallback models configured
5. **Model Aliases**: User-friendly names mapped to provider-specific formats

## Usage Example

```python
import litellm

# Direct completion call
response = litellm.completion(
    model="o3-mini",  # Uses our configured alias
    messages=[{"role": "user", "content": "Hello!"}],
    temperature=1.0  # O3 models only support temperature=1.0
)

# With Router for advanced features
from litellm import Router
router = Router(model_list=config['model_list'])
response = router.completion(
    model="gemini-2.5-flash",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## Next Steps

With LiteLLM foundation in place, the next tasks involve:
1. Creating the LiteLLMProvider wrapper (Task 2)
2. Migrating model configurations (Task 3)
3. Updating the registry and tools (Task 4)
4. Adding comprehensive testing (Task 5)
5. Removing legacy providers (Task 6)