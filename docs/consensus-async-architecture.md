# Consensus Tool Async Architecture and Timeout Configuration

## Overview

The consensus tool implements a sophisticated async architecture that enables parallel execution of multiple AI model consultations while maintaining proper error handling, timeout management, and thread safety. This document describes the implementation details and configuration options.

## Architecture Components

### 1. Parallel Execution Model

The consensus tool uses `asyncio` to execute model consultations in parallel:

```python
# Phase 1: Parallel initial consultations
initial_tasks = [
    asyncio.create_task(self._consult_model(model_config, request, phase="initial"))
    for model_config in self.models_to_consult
]

# Execute with phase timeout
done, pending = await asyncio.wait(initial_tasks, timeout=phase_timeout)
```

Key benefits:
- **Speed**: 3-4x faster than sequential execution for typical 3-4 model scenarios
- **Resilience**: One model's failure doesn't block others
- **Graceful degradation**: Partial results are returned if some models timeout

### 2. Thread Safety

All storage operations (conversation memory updates) happen **outside** the parallel execution phases:

```python
# Storage happens AFTER all parallel operations complete
if continuation_id:
    add_turn(
        continuation_id,
        "assistant", 
        self._format_consensus_for_storage(response_data),
        # ... other parameters
    )
```

This ensures:
- No race conditions in conversation memory
- Atomic updates to thread context
- Consistent state management

### 3. Timeout Hierarchy

The system implements a three-level timeout hierarchy:

#### Level 1: Phase Timeout (Highest Priority)
- Controls overall time for each consensus phase
- Calculated as: `max(all_model_timeouts) + 60s buffer`
- Enforced using `asyncio.wait(timeout=phase_timeout)`
- Cancels any pending tasks when exceeded

#### Level 2: Model-Specific Timeout
- Defined in `ModelCapabilities.timeout` field
- Examples:
  - Standard models: 180s (3 minutes)
  - O3 models: 300s (5 minutes)
  - O3-Pro: 1800s (30 minutes)
  - O3-Deep-Research: 3600s (1 hour)

#### Level 3: HTTP Client Timeout
- Passed to provider's `generate_content()` method
- Controls individual HTTP request timeout
- Provider-specific implementation

### 4. Error Propagation

Errors are propagated immediately without waiting for timeouts:

```python
# In _consult_model
try:
    response = await asyncio.to_thread(
        provider.generate_content,
        # ... parameters
    )
except Exception as e:
    # Error returned immediately
    return {
        "model": model_name,
        "status": "error",
        "error": str(e)
    }
```

## Configuration Options

### 1. Environment Variables

```bash
# Global consensus timeout (default: 600s / 10 minutes)
export CONSENSUS_MODEL_TIMEOUT=900

# Provider-specific HTTP timeouts
export CUSTOM_CONNECT_TIMEOUT=30
export CUSTOM_READ_TIMEOUT=600
export CUSTOM_WRITE_TIMEOUT=600
export CUSTOM_POOL_TIMEOUT=600
```

### 2. Model Capabilities Configuration

In provider implementations:

```python
SUPPORTED_MODELS = {
    "o3-pro-2025-06-10": ModelCapabilities(
        # ... other fields
        timeout=1800.0,  # 30 minutes for deep research
    ),
    "gpt-4": ModelCapabilities(
        # ... other fields
        timeout=180.0,   # 3 minutes standard
    )
}
```

### 3. Reasoning Effort Impact

While not directly affecting timeouts, reasoning effort impacts processing time:
- `minimal`: 0.5% of max thinking tokens
- `low`: 8% of max thinking tokens
- `medium`: 33% of max thinking tokens (default)
- `high`: 67% of max thinking tokens
- `max`: 100% of max thinking tokens

## Implementation Details

### Phase Timeout Calculation

```python
def _get_phase_timeout(self, model_configs: list[dict]) -> float:
    """Calculate appropriate timeout for a consensus phase."""
    max_model_timeout = 0.0
    for config in model_configs:
        model_name = config.get("model", "")
        model_timeout = self._get_model_timeout(model_name)
        max_model_timeout = max(max_model_timeout, model_timeout)
    
    # Add 60 second buffer for coordination overhead
    phase_timeout = max_model_timeout + 60.0
    return phase_timeout
```

### Model Timeout Resolution

```python
def _get_model_timeout(self, model_name: str) -> float:
    """Get model-specific timeout from capabilities."""
    try:
        provider = self.get_model_provider(model_name)
        if provider:
            capabilities = provider.get_capabilities(model_name)
            if hasattr(capabilities, 'timeout'):
                return capabilities.timeout
    except Exception:
        pass
    
    # Fall back to consensus timeout
    return self._get_consensus_timeout()
```

### Async Execution Pattern

The consensus tool uses `asyncio.to_thread()` to wrap synchronous provider calls:

```python
response = await asyncio.to_thread(
    provider.generate_content,
    prompt=prompt,
    model_name=model_name,
    timeout=model_timeout,  # Model-specific timeout
    # ... other parameters
)
```

This allows:
- Parallel execution of blocking I/O operations
- Proper timeout propagation to HTTP clients
- Clean integration with async MCP server

## Best Practices

### 1. Timeout Configuration

- **Default models**: Use 3-minute timeout (180s)
- **Complex reasoning models**: Use 5-30 minute timeouts
- **Deep research models**: Use up to 1 hour timeout
- **Always add buffer**: Phase timeout adds 60s for coordination

### 2. Error Handling

- **Don't retry timeouts**: HTTP timeouts indicate unresponsive servers
- **Propagate immediately**: Return errors without waiting
- **Preserve partial results**: Return successful responses even if some fail
- **Log appropriately**: Warnings for timeouts, errors for other failures

### 3. Testing

- **Test timeout scenarios**: Ensure timeouts work as expected
- **Test mixed responses**: Verify partial results are handled
- **Test error propagation**: Confirm immediate error returns
- **Test order preservation**: Ensure model order is maintained

## Performance Characteristics

### Typical Execution Times

- **3 standard models**: ~5-10 seconds total (vs 15-30s sequential)
- **Mixed models (including O3)**: ~30-60 seconds total
- **With deep research model**: Can take several minutes

### Memory Usage

- **Per model task**: ~1-2MB overhead
- **Conversation history**: Grows with turn count
- **File content**: Additional memory for embedded files

### Scalability

- **Model count**: Tested with up to 10 models concurrently
- **Timeout handling**: No performance degradation with timeouts
- **Error scenarios**: Immediate return prevents resource waste

## Troubleshooting

### Common Issues

1. **"Phase timeout exceeded"**
   - Increase model-specific timeout in capabilities
   - Check if model is responding slowly
   - Verify network connectivity

2. **"Model timeout shorter than expected"**
   - Check CONSENSUS_MODEL_TIMEOUT environment variable
   - Verify model capabilities configuration
   - Look for timeout override in request

3. **"Partial results returned"**
   - Normal behavior when some models fail/timeout
   - Check failed_models array in response
   - Review individual error messages

### Debug Logging

Enable debug logging to see timeout calculations:

```python
logger.debug(f"Phase timeout calculated: {phase_timeout}s")
logger.info(f"Using extended timeout of {timeout}s for model {model_name}")
```

## Future Enhancements

1. **Dynamic timeout adjustment**: Based on prompt complexity
2. **Retry logic**: For specific retryable errors
3. **Streaming support**: For progressive response delivery
4. **Circuit breaker**: For consistently failing models
5. **Metrics collection**: Response times, success rates, timeout frequency