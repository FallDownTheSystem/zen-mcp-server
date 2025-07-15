# LiteLLM Configuration Migration Guide

## Overview

This document describes the migration from provider-specific model configurations to LiteLLM's unified configuration system.

## Configuration Files

### 1. `litellm_config.yaml` - Main LiteLLM Configuration

This file contains:
- **Model definitions**: All available models with their LiteLLM-compatible names
- **Model aliases**: Shorthand names that map to full model names
- **Timeout settings**: Global and per-model timeout configurations
- **Retry policies**: Error-specific retry configurations
- **Fallback chains**: Model fallback sequences for resilience

Key features:
- Temperature constraints for O3/O4 models (fixed at 1.0)
- Model-specific timeouts (e.g., 1200s for o3-deep-research)
- Context window fallbacks for large prompts
- Load balancing and routing strategies

### 2. `model_metadata.yaml` - Zen-Specific Model Metadata

This file contains metadata that LiteLLM doesn't natively support:
- **Thinking mode support**: Which models support extended thinking
- **Temperature constraints**: Fixed, range, or discrete temperature values
- **Image support**: Which models accept images and size limits
- **Context windows**: Accurate token limits per model
- **Model priorities**: For automatic model selection

## Timeout Configuration Hierarchy

The system respects the following timeout precedence:
1. **Tool-level timeout**: Passed directly in the request (highest priority)
2. **Model-specific timeout**: Defined in litellm_config.yaml
3. **Global timeout**: litellm_settings.request_timeout (600s default)
4. **LiteLLM defaults**: Built-in defaults (lowest priority)

## Model Aliases

All existing aliases are preserved:

### OpenAI Models
- `o3mini` → `o3-mini`
- `o3pro`, `o3-pro` → `o3-pro-2025-06-10`
- `o3-research`, `deep-research` → `o3-deep-research-2025-06-26`
- `o4mini` → `o4-mini`
- `gpt4.1`, `gpt-4.1` → `gpt-4.1-2025-04-14`

### Gemini Models
- `flash` → `gemini-2.5-flash`
- `pro`, `gemini pro` → `gemini-2.5-pro`
- `flash2`, `flash-2.0` → `gemini-2.0-flash`
- `flashlite`, `flash-lite` → `gemini-2.0-flash-lite`

### X.AI Models
- `grok`, `grok4`, `grok-4-latest` → `grok-4-0709`
- `grok3` → `grok-3`
- `grok3fast`, `grok3-fast` → `grok-3-fast`

## Environment Variables

The following environment variables are still used:
- `CONSENSUS_MODEL_TIMEOUT`: Default timeout for consensus tool (600s)
- `OPENAI_API_KEY`: OpenAI API key
- `GOOGLE_API_KEY`: Google Gemini API key
- `XAI_API_KEY`: X.AI API key

Removed (handled by LiteLLM):
- `CUSTOM_CONNECT_TIMEOUT`
- `CUSTOM_READ_TIMEOUT`
- `CUSTOM_WRITE_TIMEOUT`
- `CUSTOM_POOL_TIMEOUT`

## Usage with LiteLLMProvider

```python
import yaml
from providers.litellm_provider import LiteLLMProvider

# Load metadata
with open("model_metadata.yaml", "r") as f:
    metadata = yaml.safe_load(f)

# Create provider with metadata
provider = LiteLLMProvider(model_metadata=metadata['models'])

# Use any model by name or alias
response = provider.generate_content(
    prompt="Hello",
    model_name="flash",  # Uses gemini-2.5-flash
    timeout=300  # Override default timeout
)
```

## Migration Benefits

1. **Unified Configuration**: Single source of truth for all models
2. **Native Retry/Fallback**: LiteLLM handles retries and fallbacks
3. **Simplified Provider**: One provider handles all models
4. **Better Timeout Management**: Clear hierarchy and model-specific settings
5. **Easier Maintenance**: Add new models by updating YAML files

## Testing

Run the configuration test to verify:
```bash
python test_litellm_config.py
```

This validates:
- Configuration loading
- Metadata structure
- Alias resolution
- Timeout settings
- Provider integration