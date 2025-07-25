# Observability Documentation

This document describes the observability system for the Zen MCP Server's LiteLLM integration.

## Overview

The observability system provides comprehensive monitoring, cost tracking, and performance metrics for all LLM API calls using LiteLLM's callback system. It includes:

- **Cost tracking**: Monitors API costs and usage patterns
- **Latency metrics**: Tracks response times and performance
- **Secure logging**: Prevents PII exposure with automatic redaction
- **Integration**: Seamlessly integrates with existing MCP activity logs

## Environment Configuration

The observability system can be configured using environment variables:

### Core Settings

```bash
# Enable/disable observability (default: true)
OBSERVABILITY_ENABLED=true

# Enable verbose LiteLLM logging (default: false)
OBSERVABILITY_VERBOSE=false

# Enable request logging (default: false)
OBSERVABILITY_LOG_REQUESTS=false

# Enable response logging (default: false)
OBSERVABILITY_LOG_RESPONSES=false

# Enable/disable PII redaction (default: true)
OBSERVABILITY_REDACT_PII=true
```

### Usage Examples

#### Development Mode
```bash
# Enable detailed logging for development
OBSERVABILITY_ENABLED=true
OBSERVABILITY_VERBOSE=true
OBSERVABILITY_LOG_REQUESTS=true
OBSERVABILITY_LOG_RESPONSES=true
OBSERVABILITY_REDACT_PII=false
```

#### Production Mode
```bash
# Secure production configuration
OBSERVABILITY_ENABLED=true
OBSERVABILITY_VERBOSE=false
OBSERVABILITY_LOG_REQUESTS=false
OBSERVABILITY_LOG_RESPONSES=false
OBSERVABILITY_REDACT_PII=true
```

## Features

### Cost Tracking

Automatically tracks:
- Per-model API costs
- Total cumulative costs
- Average costs per call
- Token usage statistics

Example log output:
```
COST_TRACKING: model=gpt-4o cost=$0.002500 usage={'input_tokens': 100, 'output_tokens': 50, 'total_tokens': 150} total_cost=$0.012500 calls=5
```

### Latency Monitoring

Tracks:
- Response latency per model
- Average latency across calls
- Performance trends over time

Example log output:
```
LATENCY_TRACKING: model=gpt-4o latency=2.345s avg_latency=2.123s calls=5
```

### Secure Logging

Automatic PII redaction for:
- Email addresses → `[EMAIL]`
- Phone numbers → `[PHONE]`
- Social security numbers → `[SSN]`
- Credit card numbers → `[CARD]`
- API keys → `[API_KEY]`
- Passwords/secrets → `[REDACTED]`

### MCP Activity Integration

The observability system integrates with the existing MCP activity logger:
- `LLM_CALL_START`: When LLM request begins
- `LLM_CALL_END`: When LLM request completes
- `LLM_SUCCESS`: When LLM request succeeds
- `LLM_FAILURE`: When LLM request fails

## Implementation Details

### Callback Handler

The `ZenObservabilityHandler` class extends LiteLLM's `CustomLogger` to provide:
- Pre/post API call logging
- Success/failure event handling
- Async callback support
- Statistics collection

### Integration Points

1. **LiteLLM Provider**: Automatically configures callbacks during initialization
2. **Activity Logger**: Integrates with existing `mcp_activity` logger
3. **Cost Tracking**: Uses LiteLLM's built-in cost calculation
4. **Error Handling**: Graceful degradation if observability fails

### Security Features

- **PII Redaction**: Automatic removal of sensitive data
- **Content Truncation**: Limits log content length
- **Error Isolation**: Observability failures don't affect LLM calls
- **Configurable Verbosity**: Control logging detail level

## Testing

Run the observability test suite:

```bash
source .zen_venv/Scripts/activate
python test_observability.py
```

The test verifies:
- Callback configuration
- Provider initialization
- PII redaction
- Async callback support

## Monitoring

### Log Files

Observability logs are written to:
- `logs/mcp_server.log` - Main server logs including observability
- `logs/mcp_activity.log` - Activity logs including LLM events

### Statistics

Get runtime statistics via the LiteLLM provider:

```python
provider = LiteLLMProvider()
stats = provider.get_observability_stats()
```

Returns:
```python
{
    "cost_stats": {
        "total_cost": 0.123,
        "call_count": 50,
        "average_cost": 0.00246
    },
    "latency_stats": {
        "total_latency": 125.6,
        "call_count": 50,
        "average_latency": 2.512
    }
}
```

## Troubleshooting

### Common Issues

1. **Callbacks not working**: Check `OBSERVABILITY_ENABLED=true`
2. **No cost data**: Ensure LiteLLM has proper API keys
3. **PII showing**: Verify `OBSERVABILITY_REDACT_PII=true`
4. **Performance impact**: Disable detailed logging in production

### Debug Mode

Enable debug logging:
```bash
OBSERVABILITY_VERBOSE=true
LOG_LEVEL=DEBUG
```

This will show detailed callback execution and LiteLLM operations.

## Best Practices

1. **Production**: Use minimal logging with PII redaction enabled
2. **Development**: Enable detailed logging for debugging
3. **Monitoring**: Regularly check cost and latency trends
4. **Security**: Never disable PII redaction in production environments
5. **Performance**: Monitor observability overhead in high-throughput scenarios