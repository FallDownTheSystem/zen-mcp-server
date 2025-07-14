# Radical LiteLLM-Based Rewrite Design

## Overview

This document outlines a complete reimagining of Zen MCP Server built entirely around LiteLLM. No backward compatibility, no legacy code - just a clean, modern architecture.

## Core Philosophy

1. **LiteLLM handles ALL provider complexity** - No custom provider code
2. **Configuration over code** - Model behaviors defined in YAML/JSON
3. **Plugin-based tools** - Each tool is a self-contained module
4. **Streaming-first** - All operations support streaming by default
5. **Type-safe** - Pydantic models and protocols throughout

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Interface                         │
├─────────────────────────────────────────────────────────┤
│                    Tool Router                           │
│  ┌─────────┐  ┌───────────┐  ┌──────────────┐         │
│  │  Chat   │  │ Consensus │  │ Future Tools │         │
│  └────┬────┘  └─────┬─────┘  └──────┬───────┘         │
│       └─────────────┴────────────────┘                  │
├─────────────────────────────────────────────────────────┤
│                 LiteLLM Service Layer                    │
│  ┌────────────┐  ┌──────────────┐  ┌────────────┐     │
│  │   Router   │  │ Rate Limiter │  │   Cache    │     │
│  └─────┬──────┘  └──────┬───────┘  └─────┬──────┘     │
│        └────────────────┴─────────────────┘             │
├─────────────────────────────────────────────────────────┤
│              LiteLLM Core (100+ providers)               │
└─────────────────────────────────────────────────────────┘
```

## File Structure

```
zen-mcp-server/
├── config/
│   ├── models.yaml         # Model configurations
│   ├── limits.yaml         # Rate limits, quotas
│   └── prompts.yaml        # System prompts
├── src/
│   ├── core/
│   │   ├── llm.py         # Single LiteLLM wrapper
│   │   ├── config.py      # Config management
│   │   └── types.py       # Pydantic models
│   ├── tools/
│   │   ├── base.py        # Tool protocol
│   │   ├── chat.py        # Chat tool
│   │   └── consensus.py   # Consensus tool
│   ├── middleware/
│   │   ├── auth.py        # API key validation
│   │   ├── logging.py     # Request/response logging
│   │   └── metrics.py     # Prometheus metrics
│   └── server.py          # MCP server entry
├── tests/
└── pyproject.toml         # Modern Python packaging
```

## Core Components

### 1. Single LiteLLM Service (`src/core/llm.py`)

```python
from typing import AsyncIterator, Optional
import litellm
from pydantic import BaseModel, Field

class ModelConfig(BaseModel):
    """Runtime model configuration"""
    aliases: list[str] = []
    temperature_override: Optional[float] = None
    max_tokens_override: Optional[int] = None
    supports_vision: bool = False
    supports_tools: bool = False
    cost_multiplier: float = 1.0
    
class LLMService:
    def __init__(self, config_path: str = "config/models.yaml"):
        self.models = self._load_model_configs(config_path)
        
        # Configure LiteLLM globally
        litellm.drop_params = True  # Ignore unsupported params
        litellm.set_verbose = True
        litellm.cache = litellm.Cache(type="redis")  # Built-in caching
        
    async def complete(
        self,
        model: str,
        messages: list[dict],
        **kwargs
    ) -> litellm.ModelResponse:
        """Unified completion interface for all models"""
        # Resolve aliases
        actual_model = self._resolve_model(model)
        
        # Apply model-specific overrides
        config = self.models.get(actual_model, ModelConfig())
        if config.temperature_override is not None:
            kwargs['temperature'] = config.temperature_override
            
        # Use LiteLLM's router for automatic failover
        response = await litellm.acompletion(
            model=actual_model,
            messages=messages,
            **kwargs
        )
        
        return response
        
    async def stream(
        self,
        model: str,
        messages: list[dict],
        **kwargs
    ) -> AsyncIterator[litellm.ModelResponse]:
        """Streaming interface"""
        actual_model = self._resolve_model(model)
        
        async for chunk in litellm.acompletion(
            model=actual_model,
            messages=messages,
            stream=True,
            **kwargs
        ):
            yield chunk
```

### 2. Plugin-Based Tools (`src/tools/base.py`)

```python
from typing import Protocol, Any, Dict
from pydantic import BaseModel

class ToolRequest(BaseModel):
    """Base request all tools inherit from"""
    request_id: str
    metadata: Dict[str, Any] = {}

class ToolResponse(BaseModel):
    """Base response all tools return"""
    request_id: str
    status: str
    data: Any
    metadata: Dict[str, Any] = {}

class Tool(Protocol):
    """Protocol all tools must implement"""
    name: str
    description: str
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        """Execute the tool"""
        ...
```

### 3. Modern Chat Tool (`src/tools/chat.py`)

```python
from typing import Optional, List
from pydantic import BaseModel, Field
from .base import Tool, ToolRequest, ToolResponse
from ..core.llm import LLMService

class ChatRequest(ToolRequest):
    model: str
    prompt: str
    images: List[str] = []
    files: List[str] = []
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: Optional[int] = None
    stream: bool = False
    
class ChatTool(Tool):
    name = "chat"
    description = "General purpose LLM chat"
    
    def __init__(self, llm: LLMService):
        self.llm = llm
        
    async def execute(self, request: ChatRequest) -> ToolResponse:
        # Build messages
        messages = [{"role": "user", "content": request.prompt}]
        
        # Add images if provided
        if request.images:
            messages[0]["content"] = [
                {"type": "text", "text": request.prompt},
                *[{"type": "image_url", "image_url": img} for img in request.images]
            ]
            
        # Single call to LiteLLM handles everything
        response = await self.llm.complete(
            model=request.model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        return ToolResponse(
            request_id=request.request_id,
            status="success",
            data=response.choices[0].message.content,
            metadata={
                "model": response.model,
                "tokens": response.usage.total_tokens,
                "cost": litellm.completion_cost(response)
            }
        )
```

### 4. Parallel Consensus Tool (`src/tools/consensus.py`)

```python
import asyncio
from typing import List, Dict
from .base import Tool, ToolRequest, ToolResponse

class ConsensusRequest(ToolRequest):
    prompt: str
    models: List[str]
    enable_cross_feedback: bool = True
    temperature: float = 0.3
    
class ConsensusTool(Tool):
    name = "consensus"
    description = "Gather consensus from multiple models"
    
    async def execute(self, request: ConsensusRequest) -> ToolResponse:
        # Phase 1: Parallel initial responses
        initial_tasks = [
            self._get_response(model, request.prompt, request.temperature)
            for model in request.models
        ]
        initial_responses = await asyncio.gather(*initial_tasks, return_exceptions=True)
        
        # Phase 2: Cross-feedback (if enabled)
        if request.enable_cross_feedback:
            feedback_prompt = self._build_feedback_prompt(request.prompt, initial_responses)
            feedback_tasks = [
                self._get_response(model, feedback_prompt, request.temperature)
                for model in request.models
            ]
            refined_responses = await asyncio.gather(*feedback_tasks, return_exceptions=True)
        else:
            refined_responses = None
            
        return ToolResponse(
            request_id=request.request_id,
            status="success",
            data={
                "initial": initial_responses,
                "refined": refined_responses
            }
        )
```

## Configuration Examples

### `config/models.yaml`
```yaml
# Model aliases and overrides
models:
  gpt-4:
    aliases: ["gpt4", "chatgpt-4"]
    cost_multiplier: 1.0
    
  o3-mini:
    temperature_override: 1.0  # O3 requires temperature=1
    
  gemini/gemini-2.0-flash-thinking-exp:
    aliases: ["flash-thinking", "gemini-thinking"]
    supports_vision: true
    
  claude-3-5-sonnet-20241022:
    aliases: ["claude", "sonnet"]
    supports_vision: true
    supports_tools: true
```

### `config/limits.yaml`
```yaml
# Rate limiting configuration
rate_limits:
  global:
    requests_per_minute: 100
    tokens_per_minute: 1000000
    
  per_model:
    o3-mini:
      requests_per_minute: 10  # Expensive model
    gpt-4-turbo:
      requests_per_minute: 50
```

## Key Benefits

1. **90% Less Code**: One provider instead of 6+
2. **Instant Provider Support**: Any model LiteLLM supports works immediately
3. **Built-in Features**:
   - Automatic retries with exponential backoff
   - Fallback chains (e.g., try GPT-4, fall back to GPT-3.5)
   - Load balancing across API keys
   - Cost tracking and budgets
   - Request caching
   - Rate limiting
   
4. **Better Observability**:
   - Unified logging format
   - Built-in metrics (latency, tokens, costs)
   - Trace IDs for request tracking
   
5. **Easier Testing**:
   - Mock one interface (LiteLLM)
   - Use LiteLLM's built-in mock responses
   - Test tools in isolation

## Migration Strategy

1. **Build New System in Parallel**: Create new codebase alongside old
2. **Feature Parity Testing**: Ensure all current features work
3. **Performance Testing**: Verify latency is acceptable
4. **Gradual Rollout**: Use feature flags to switch traffic
5. **Deprecate Old System**: Remove after validation period

## Example Usage

```python
# Initialize once
llm = LLMService()
chat_tool = ChatTool(llm)
consensus_tool = ConsensusTool(llm)

# Simple chat
response = await chat_tool.execute(ChatRequest(
    model="gpt4",  # Alias resolved to gpt-4-turbo
    prompt="Explain quantum computing",
    temperature=0.5
))

# Parallel consensus
consensus = await consensus_tool.execute(ConsensusRequest(
    prompt="Should we use microservices?",
    models=["gpt-4", "claude", "gemini-pro"],
    enable_cross_feedback=True
))

# Streaming with any model
async for chunk in llm.stream("mistral-large", messages):
    print(chunk.choices[0].delta.content)
```

## Radical Simplifications

1. **No Provider Classes**: Just configuration
2. **No Manual Retry Logic**: LiteLLM handles it
3. **No Cost Calculation**: `litellm.completion_cost()`
4. **No Token Counting**: Built into responses
5. **No Manual Routing**: LiteLLM Router class
6. **No Custom Error Types**: Use LiteLLM's unified errors

This design represents a complete paradigm shift - from maintaining provider complexity ourselves to leveraging LiteLLM's battle-tested implementations, allowing us to focus on building great tools rather than maintaining API integrations.