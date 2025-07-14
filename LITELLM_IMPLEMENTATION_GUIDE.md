# LiteLLM Implementation Guide

This guide provides step-by-step instructions for implementing the new LiteLLM-based architecture for Zen MCP Server.

## Overview

The new architecture completely replaces the existing provider system with a single, unified LiteLLM-based provider. This dramatically simplifies the codebase while adding support for many more models and providers.

## Key Benefits

1. **Unified Interface**: One provider class handles all models
2. **Automatic Provider Support**: LiteLLM supports 100+ LLM providers out of the box
3. **Built-in Features**: Retry logic, fallbacks, rate limiting, cost tracking
4. **Simplified Maintenance**: No provider-specific code to maintain
5. **Better Testing**: Mock one interface instead of many

## Implementation Steps

### Phase 1: Core Infrastructure (Week 1)

#### 1.1 Project Setup
```bash
# Create new project structure
mkdir -p src/{core,providers,tools,plugins,models,utils}
mkdir -p config tests/{unit,integration,e2e} scripts

# Install dependencies
pip install litellm pydantic pyyaml httpx tenacity structlog
```

#### 1.2 Configuration System
Create YAML-based configuration for models:

```yaml
# config/models.yaml
version: "1.0"

models:
  # OpenAI Models
  gpt-4-turbo-2024-04-09:
    provider: openai
    aliases: ["gpt4", "gpt-4-turbo", "4-turbo"]
    context_window: 128000
    max_output: 4096
    input_cost_per_token: 0.00001
    output_cost_per_token: 0.00003
    capabilities:
      vision: true
      function_calling: true
      json_mode: true
      streaming: true
    
  gpt-4o:
    provider: openai
    aliases: ["4o", "gpt4o"]
    context_window: 128000
    max_output: 4096
    
  # Anthropic Models
  claude-3-opus-20240229:
    provider: anthropic
    aliases: ["opus", "claude-opus", "claude-3-opus"]
    context_window: 200000
    max_output: 4096
    
  # Google Models
  gemini-pro:
    provider: vertex_ai
    aliases: ["gemini", "g-pro"]
    litellm_model: "vertex_ai/gemini-pro"
    context_window: 30720
    max_output: 2048
    
  # Local/Custom Models
  local-llama:
    provider: openai  # Uses OpenAI-compatible API
    aliases: ["llama", "local"]
    base_url: "${LOCAL_LLM_API_BASE}"
    api_key: "not-needed"
    context_window: 8192
    max_output: 2048
```

#### 1.3 LiteLLM Provider Implementation
Key implementation details:

```python
# src/providers/litellm_provider.py
import litellm
from litellm import Router  # For load balancing

class LiteLLMProvider:
    def __init__(self, config: Config):
        # Set up router for load balancing and fallbacks
        self.router = Router(
            model_list=[
                {
                    "model_name": "gpt-4-turbo",
                    "litellm_params": {
                        "model": "gpt-4-turbo-2024-04-09",
                        "api_key": os.getenv("OPENAI_API_KEY"),
                    },
                },
                {
                    "model_name": "gpt-4-turbo",  # Fallback
                    "litellm_params": {
                        "model": "azure/gpt-4-turbo",
                        "api_key": os.getenv("AZURE_API_KEY"),
                        "api_base": os.getenv("AZURE_API_BASE"),
                    },
                },
            ],
            fallbacks=[
                {"gpt-4-turbo": ["gpt-4", "gpt-3.5-turbo"]},
                {"claude-3-opus": ["claude-3-sonnet", "claude-2.1"]},
            ],
            retry_after=5,  # Retry failed requests after 5 seconds
            allowed_fails=2,  # Allow 2 fails before switching models
        )
```

### Phase 2: Tool System (Week 2)

#### 2.1 Base Tool Interface
```python
# src/tools/base.py
from abc import ABC, abstractmethod
from typing import Protocol

class ToolProtocol(Protocol):
    """Protocol defining tool interface"""
    name: str
    description: str
    
    def get_schema(self) -> Dict[str, Any]: ...
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]: ...

class BaseTool(ABC):
    """Base implementation with common functionality"""
    
    def __init__(self, provider: LiteLLMProvider, config: Optional[ToolConfig] = None):
        self.provider = provider
        self.config = config or self._load_default_config()
        self._setup_logging()
        
    def _setup_logging(self):
        self.logger = structlog.get_logger(tool=self.name)
```

#### 2.2 Tool Registry
```python
# src/core/tool_registry.py
class ToolRegistry:
    """Dynamic tool discovery and management"""
    
    def __init__(self, provider: LiteLLMProvider):
        self.provider = provider
        self.tools: Dict[str, ToolProtocol] = {}
        self._discovery_paths = [Path("src/plugins")]
        
    async def discover_and_load(self):
        """Discover tools from filesystem"""
        for path in self._discovery_paths:
            await self._scan_directory(path)
            
    def register_tool(self, tool: ToolProtocol):
        """Register a tool instance"""
        self.tools[tool.name] = tool
        self.logger.info(f"Registered tool: {tool.name}")
```

### Phase 3: Tool Migration (Week 3)

#### 3.1 Chat Tool Migration
```python
# src/plugins/chat/tool.py
@register_tool("chat")
class ChatTool(BaseTool):
    """Migrated chat tool using LiteLLM"""
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        # Extract parameters
        model = params["model"]
        prompt = params["prompt"]
        
        # Use conversation memory if available
        messages = await self._build_messages(prompt, params.get("conversation_id"))
        
        # Make request through LiteLLM provider
        request = ModelRequest(
            model=model,
            messages=messages,
            temperature=params.get("temperature", 0.7),
            metadata={
                "tool": "chat",
                "user": context.user_id,
                "session": context.session_id
            }
        )
        
        response = await self.provider.generate(request)
        
        # Save to conversation memory
        if params.get("conversation_id"):
            await self._save_conversation(params["conversation_id"], messages, response)
        
        return self._format_response(response)
```

#### 3.2 Consensus Tool Migration
Key improvements in the new version:

1. **True Parallel Execution**: Use asyncio.gather for all models
2. **Better Error Handling**: Partial failures don't break entire consensus
3. **Cost Aggregation**: Track total cost across all models
4. **Response Metadata**: Include timing, tokens, and provider info

### Phase 4: Advanced Features (Week 4)

#### 4.1 Middleware System
```python
# src/core/middleware.py
class MiddlewareProtocol(Protocol):
    async def process_request(self, request: ToolRequest, call_next: Callable) -> ToolResponse:
        ...

class RateLimitMiddleware:
    """Rate limiting per user/tool"""
    def __init__(self, limits: Dict[str, int]):
        self.limits = limits
        self.trackers = {}
        
    async def process_request(self, request: ToolRequest, call_next: Callable) -> ToolResponse:
        key = f"{request.user_id}:{request.tool_name}"
        if self._is_rate_limited(key):
            raise RateLimitExceeded(f"Rate limit exceeded for {request.tool_name}")
        
        response = await call_next(request)
        self._track_usage(key)
        return response
```

#### 4.2 Observability
```python
# src/utils/observability.py
class MetricsCollector:
    """Collect and export metrics"""
    
    def __init__(self):
        self.tool_latency = Histogram('tool_execution_seconds', 'Tool execution time')
        self.model_tokens = Counter('model_tokens_total', 'Total tokens used', ['model', 'type'])
        self.api_errors = Counter('api_errors_total', 'API errors', ['provider', 'error_type'])
        
    @contextmanager
    def track_execution(self, tool_name: str):
        start = time.time()
        try:
            yield
        finally:
            self.tool_latency.labels(tool=tool_name).observe(time.time() - start)
```

### Phase 5: Testing Strategy

#### 5.1 Unit Tests
```python
# tests/unit/test_litellm_provider.py
import pytest
from unittest.mock import AsyncMock, patch

class TestLiteLLMProvider:
    @pytest.fixture
    def mock_litellm(self):
        with patch('litellm.acompletion') as mock:
            mock.return_value = AsyncMock(
                choices=[AsyncMock(message=AsyncMock(content="Test response"))],
                usage=AsyncMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
            )
            yield mock
    
    async def test_generate_basic(self, mock_litellm):
        provider = LiteLLMProvider({})
        response = await provider.generate(ModelRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        ))
        
        assert response.content == "Test response"
        assert response.usage["total_tokens"] == 30
```

#### 5.2 Integration Tests
```python
# tests/integration/test_tools.py
@pytest.mark.integration
class TestToolIntegration:
    async def test_chat_tool_with_real_api(self):
        # Uses real API with test quotas
        provider = LiteLLMProvider(load_test_config())
        chat_tool = ChatTool(provider)
        
        result = await chat_tool.execute({
            "model": "gpt-3.5-turbo",
            "prompt": "Say 'test passed'"
        }, ToolContext(request_id="test-001"))
        
        assert "test passed" in result["content"].lower()
```

### Migration Checklist

- [ ] Set up new project structure
- [ ] Implement configuration system
- [ ] Create LiteLLM provider
- [ ] Implement base tool interface
- [ ] Create tool registry
- [ ] Migrate chat tool
- [ ] Migrate consensus tool
- [ ] Add middleware system
- [ ] Implement observability
- [ ] Write comprehensive tests
- [ ] Create migration scripts for existing data
- [ ] Update documentation
- [ ] Performance testing
- [ ] Gradual rollout plan

## Configuration Examples

### Multi-Provider Setup
```yaml
# config/providers.yaml
providers:
  primary:
    - model: gpt-4-turbo
      weight: 0.7  # 70% of traffic
    - model: claude-3-opus
      weight: 0.3  # 30% of traffic
      
  fallback_chain:
    - gpt-4-turbo
    - gpt-4
    - claude-3-opus
    - claude-3-sonnet
    - gpt-3.5-turbo  # Last resort
```

### Rate Limiting
```yaml
# config/limits.yaml
rate_limits:
  global:
    requests_per_minute: 1000
    tokens_per_minute: 1000000
    
  per_tool:
    chat:
      requests_per_minute: 100
      tokens_per_minute: 500000
    consensus:
      requests_per_minute: 20
      tokens_per_minute: 200000
      
  per_user:
    requests_per_hour: 500
    tokens_per_day: 1000000
```

## Performance Optimizations

1. **Connection Pooling**: LiteLLM handles this automatically
2. **Response Caching**: Use Redis for common queries
3. **Streaming**: Enable for long responses
4. **Batch Processing**: Group similar requests
5. **Model Router**: Load balance across providers

## Monitoring and Alerts

Set up alerts for:
- High error rates (> 1%)
- Slow response times (> 5s p95)
- Cost spikes (> 20% increase)
- Rate limit approaches (> 80% of limit)

## Rollback Plan

1. Keep existing provider code in `legacy/` directory
2. Feature flag for provider selection
3. Gradual rollout by percentage
4. Quick switch back if issues arise

## Future Enhancements

1. **Model Fine-tuning Integration**: Use LiteLLM's fine-tuning APIs
2. **A/B Testing**: Built-in experiment framework
3. **Custom Model Support**: Easy integration of self-hosted models
4. **Advanced Routing**: Smart model selection based on query type
5. **Cost Optimization**: Automatic model selection based on cost/quality trade-offs