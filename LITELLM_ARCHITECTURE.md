# Zen MCP Server - LiteLLM Architecture Design

## Executive Summary

This document outlines a completely new architecture for Zen MCP Server built entirely around LiteLLM. The design prioritizes simplicity, maintainability, and leveraging LiteLLM's unified interface to eliminate provider-specific code.

## Core Design Principles

1. **LiteLLM as the Single Source of Truth**: All model interactions go through LiteLLM
2. **Configuration over Code**: Model capabilities and behaviors defined in config files
3. **Plugin Architecture**: Tools are self-contained plugins with standard interfaces
4. **Async-First**: Built on modern async Python patterns
5. **Type Safety**: Comprehensive type hints and validation using Pydantic
6. **Observability**: Built-in logging, metrics, and tracing support

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         MCP Client (Claude)                       │
└────────────────────────────┬───────────────────────────────────┘
                             │ JSON-RPC over stdio
┌────────────────────────────▼───────────────────────────────────┐
│                      MCP Protocol Layer                          │
│  • Request/Response handling                                     │
│  • Tool discovery and routing                                    │
│  • Error handling and formatting                                 │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│                       Tool Registry                              │
│  • Dynamic tool loading from plugins/                           │
│  • Tool validation and schema generation                         │
│  • Dependency injection for tools                               │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│                    Tool Execution Engine                         │
│  • Async task management                                         │
│  • Request context and middleware                                │
│  • Rate limiting and concurrency control                         │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│                    LiteLLM Provider Layer                        │
│  • Single unified interface for all models                       │
│  • Automatic retry and fallback logic                          │
│  • Token counting and cost tracking                            │
│  • Response streaming support                                    │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│                  External AI Services                            │
│  (OpenAI, Anthropic, Google, Azure, AWS, etc.)                 │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
zen-mcp-server/
├── src/
│   ├── __init__.py
│   ├── server.py              # Main MCP server entry point
│   ├── config.py              # Configuration management
│   ├── core/
│   │   ├── __init__.py
│   │   ├── mcp_handler.py     # MCP protocol handling
│   │   ├── tool_registry.py   # Tool discovery and management
│   │   ├── middleware.py      # Request/response middleware
│   │   └── context.py         # Request context management
│   ├── providers/
│   │   ├── __init__.py
│   │   └── litellm_provider.py # Single LiteLLM provider
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py            # Base tool interface
│   │   ├── decorators.py      # Tool registration decorators
│   │   └── schema.py          # Schema generation utilities
│   ├── plugins/               # Tool implementations
│   │   ├── __init__.py
│   │   ├── chat/
│   │   │   ├── __init__.py
│   │   │   ├── tool.py
│   │   │   └── config.yaml
│   │   ├── consensus/
│   │   │   ├── __init__.py
│   │   │   ├── tool.py
│   │   │   └── config.yaml
│   │   └── ... (other tools)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── config.py          # Configuration models
│   │   ├── request.py         # Request/response models
│   │   └── capabilities.py    # Model capability definitions
│   └── utils/
│       ├── __init__.py
│       ├── logging.py         # Structured logging
│       ├── metrics.py         # Metrics collection
│       └── validation.py      # Input validation utilities
├── config/
│   ├── models.yaml            # Model capabilities configuration
│   ├── server.yaml            # Server configuration
│   └── limits.yaml            # Rate limits and quotas
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/
│   ├── setup.py
│   └── validate_config.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Key Components

### 1. Configuration System

```yaml
# config/models.yaml
models:
  # OpenAI Models
  gpt-4-turbo:
    provider: openai
    aliases: ["gpt4", "4-turbo"]
    context_window: 128000
    max_output: 4096
    capabilities:
      vision: true
      function_calling: true
      json_mode: true
    cost:
      input: 0.01
      output: 0.03
    
  # Anthropic Models  
  claude-3-opus:
    provider: anthropic
    aliases: ["opus", "claude-opus"]
    context_window: 200000
    max_output: 4096
    capabilities:
      vision: true
      function_calling: false
    
  # Custom endpoints
  local-llama:
    provider: custom
    base_url: "http://localhost:8080"
    context_window: 8192
    max_output: 2048
```

### 2. LiteLLM Provider (Single Implementation)

```python
# src/providers/litellm_provider.py
from typing import AsyncIterator, Optional, Dict, Any
import litellm
from litellm import acompletion, completion_cost, token_counter
from pydantic import BaseModel, Field
import backoff

class ModelRequest(BaseModel):
    """Unified request model for all LLM calls"""
    model: str
    messages: list[dict]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    tools: Optional[list[dict]] = None
    tool_choice: Optional[str] = None
    response_format: Optional[dict] = None
    user: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ModelResponse(BaseModel):
    """Unified response model"""
    content: str
    model: str
    usage: Dict[str, int]
    cost: Optional[float] = None
    provider: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class LiteLLMProvider:
    """Single provider class that handles all models through LiteLLM"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_configs = config.get("models", {})
        
        # Configure LiteLLM settings
        litellm.drop_params = True  # Automatically drop unsupported params
        litellm.set_verbose = config.get("debug", False)
        
        # Set up callbacks for logging/metrics
        litellm.success_callback = [self._log_success]
        litellm.failure_callback = [self._log_failure]
        
    @backoff.on_exception(
        backoff.expo,
        Exception,
        max_tries=3,
        giveup=lambda e: "rate_limit" not in str(e).lower()
    )
    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate completion using LiteLLM"""
        
        # Resolve model aliases
        model = self._resolve_model(request.model)
        
        # Get model config
        model_config = self.model_configs.get(model, {})
        
        # Build LiteLLM arguments
        kwargs = {
            "model": model,
            "messages": request.messages,
            "temperature": request.temperature,
            "stream": request.stream,
        }
        
        # Add optional parameters based on model capabilities
        if request.max_tokens:
            kwargs["max_tokens"] = min(
                request.max_tokens, 
                model_config.get("max_output", request.max_tokens)
            )
            
        if request.tools and model_config.get("capabilities", {}).get("function_calling"):
            kwargs["tools"] = request.tools
            kwargs["tool_choice"] = request.tool_choice
            
        if request.response_format and model_config.get("capabilities", {}).get("json_mode"):
            kwargs["response_format"] = request.response_format
            
        # Add custom endpoint if needed
        if model_config.get("provider") == "custom":
            kwargs["api_base"] = model_config.get("base_url")
            
        # Make the API call
        response = await acompletion(**kwargs)
        
        # Calculate costs
        cost = None
        try:
            cost = completion_cost(completion_response=response)
        except:
            pass  # Cost calculation not available for all models
            
        # Extract provider info
        provider = response.get("model_info", {}).get("provider", "unknown")
        
        return ModelResponse(
            content=response.choices[0].message.content,
            model=model,
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            cost=cost,
            provider=provider,
            metadata={
                "response_id": response.id,
                "finish_reason": response.choices[0].finish_reason,
            }
        )
    
    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        """Stream completion using LiteLLM"""
        request.stream = True
        kwargs = self._build_kwargs(request)
        
        async for chunk in await acompletion(**kwargs):
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def count_tokens(self, text: str, model: str) -> int:
        """Count tokens for the given text"""
        model = self._resolve_model(model)
        return token_counter(model=model, text=text)
    
    def _resolve_model(self, model: str) -> str:
        """Resolve model aliases to actual model names"""
        # Check if it's already a known model
        if model in self.model_configs:
            return model
            
        # Check aliases
        for model_name, config in self.model_configs.items():
            if model in config.get("aliases", []):
                return model_name
                
        # Return as-is if not found (let LiteLLM handle it)
        return model
    
    async def _log_success(self, kwargs, response, start_time, end_time):
        """Log successful API calls"""
        # Implement logging/metrics
        pass
        
    async def _log_failure(self, kwargs, exception, start_time, end_time):
        """Log failed API calls"""
        # Implement logging/metrics
        pass
```

### 3. Base Tool Interface

```python
# src/tools/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import yaml
from pathlib import Path

class ToolConfig(BaseModel):
    """Tool configuration model"""
    name: str
    description: str
    version: str = "1.0.0"
    author: Optional[str] = None
    models: Optional[Dict[str, Any]] = None  # Model-specific configs
    rate_limits: Optional[Dict[str, int]] = None
    enabled: bool = True

class ToolContext(BaseModel):
    """Context passed to tools during execution"""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class BaseTool(ABC):
    """Base class for all tools"""
    
    def __init__(self, provider: LiteLLMProvider, config_path: Optional[Path] = None):
        self.provider = provider
        self.config = self._load_config(config_path)
        
    def _load_config(self, config_path: Optional[Path]) -> ToolConfig:
        """Load tool configuration from YAML file"""
        if not config_path:
            config_path = Path(__file__).parent / "config.yaml"
            
        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f)
                return ToolConfig(**data)
        else:
            # Return default config
            return ToolConfig(
                name=self.__class__.__name__,
                description="No description provided"
            )
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Return JSON schema for tool parameters"""
        pass
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        """Execute the tool with given parameters"""
        pass
    
    @property
    def name(self) -> str:
        """Tool name for registration"""
        return self.config.name
    
    @property
    def description(self) -> str:
        """Tool description"""
        return self.config.description
```

### 4. Tool Registration System

```python
# src/tools/decorators.py
from typing import Type, Callable, Dict, Any
from functools import wraps

# Global tool registry
_TOOL_REGISTRY: Dict[str, Type[BaseTool]] = {}

def register_tool(name: Optional[str] = None):
    """Decorator to register a tool class"""
    def decorator(cls: Type[BaseTool]):
        tool_name = name or cls.__name__.lower().replace("tool", "")
        _TOOL_REGISTRY[tool_name] = cls
        return cls
    return decorator

def tool_method(schema: Dict[str, Any]):
    """Decorator for tool methods to add schema validation"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(self, params: Dict[str, Any], context: ToolContext):
            # Validate params against schema
            # ... validation logic ...
            return await func(self, params, context)
        
        wrapper._schema = schema
        return wrapper
    return decorator

# src/core/tool_registry.py
from pathlib import Path
import importlib.util
from typing import Dict, Type

class ToolRegistry:
    """Manages tool discovery and instantiation"""
    
    def __init__(self, provider: LiteLLMProvider):
        self.provider = provider
        self.tools: Dict[str, BaseTool] = {}
        
    def discover_tools(self, plugin_dir: Path):
        """Discover and load tools from plugin directory"""
        for tool_dir in plugin_dir.iterdir():
            if tool_dir.is_dir() and (tool_dir / "tool.py").exists():
                self._load_tool(tool_dir)
                
    def _load_tool(self, tool_dir: Path):
        """Load a single tool from directory"""
        module_path = tool_dir / "tool.py"
        spec = importlib.util.spec_from_file_location(
            f"plugins.{tool_dir.name}", 
            module_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find tool class in module
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                issubclass(attr, BaseTool) and 
                attr != BaseTool):
                # Instantiate tool
                config_path = tool_dir / "config.yaml"
                tool = attr(self.provider, config_path)
                if tool.config.enabled:
                    self.tools[tool.name] = tool
                    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get tool by name"""
        return self.tools.get(name)
        
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "schema": tool.get_schema()
            }
            for tool in self.tools.values()
        ]
```

### 5. Example Tool Implementation

```python
# src/plugins/chat/tool.py
from typing import Dict, Any, Optional, List
from src.tools.base import BaseTool, ToolContext
from src.tools.decorators import register_tool
from pathlib import Path

@register_tool("chat")
class ChatTool(BaseTool):
    """General purpose chat tool"""
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt or question to send to the model"
                },
                "model": {
                    "type": "string",
                    "description": "Model to use (e.g., 'gpt-4-turbo', 'claude-3-opus')"
                },
                "temperature": {
                    "type": "number",
                    "description": "Sampling temperature (0-2)",
                    "default": 0.7
                },
                "system_prompt": {
                    "type": "string",
                    "description": "Optional system prompt"
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional file paths to include"
                },
                "conversation_id": {
                    "type": "string",
                    "description": "Optional conversation ID for context"
                }
            },
            "required": ["prompt", "model"]
        }
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        """Execute chat request"""
        # Build messages
        messages = []
        
        # Add system prompt if provided
        if params.get("system_prompt"):
            messages.append({
                "role": "system",
                "content": params["system_prompt"]
            })
        
        # Add conversation history if ID provided
        if params.get("conversation_id"):
            history = await self._get_conversation_history(params["conversation_id"])
            messages.extend(history)
        
        # Add user message with any files
        user_content = params["prompt"]
        if params.get("files"):
            file_contents = await self._read_files(params["files"])
            user_content = f"{user_content}\n\nFiles:\n{file_contents}"
            
        messages.append({
            "role": "user",
            "content": user_content
        })
        
        # Make the request
        request = ModelRequest(
            model=params["model"],
            messages=messages,
            temperature=params.get("temperature", 0.7),
            metadata={
                "tool": "chat",
                "conversation_id": params.get("conversation_id"),
                "user_id": context.user_id
            }
        )
        
        response = await self.provider.generate(request)
        
        # Save to conversation history if needed
        if params.get("conversation_id"):
            await self._save_to_history(
                params["conversation_id"], 
                messages[-1], 
                response.content
            )
        
        return {
            "status": "success",
            "content": response.content,
            "model": response.model,
            "usage": response.usage,
            "cost": response.cost,
            "conversation_id": params.get("conversation_id")
        }
    
    async def _get_conversation_history(self, conversation_id: str) -> List[Dict]:
        """Retrieve conversation history"""
        # Implementation depends on storage backend
        return []
        
    async def _read_files(self, file_paths: List[str]) -> str:
        """Read and format file contents"""
        contents = []
        for path in file_paths:
            try:
                with open(path, 'r') as f:
                    contents.append(f"--- {Path(path).name} ---\n{f.read()}")
            except Exception as e:
                contents.append(f"--- Error reading {path}: {e} ---")
        return "\n\n".join(contents)
        
    async def _save_to_history(self, conversation_id: str, user_msg: Dict, assistant_msg: str):
        """Save messages to conversation history"""
        # Implementation depends on storage backend
        pass
```

### 6. MCP Server Implementation

```python
# src/server.py
import asyncio
from typing import Any, Dict
from mcp.server import Server
from mcp.server.stdio import stdio_server
from src.core.tool_registry import ToolRegistry
from src.providers.litellm_provider import LiteLLMProvider
from src.config import load_config
import logging

logger = logging.getLogger(__name__)

class ZenMCPServer:
    """Main MCP server implementation"""
    
    def __init__(self):
        self.config = load_config()
        self.provider = LiteLLMProvider(self.config)
        self.tool_registry = ToolRegistry(self.provider)
        self.server = Server("zen-mcp-server")
        
    async def initialize(self):
        """Initialize the server"""
        # Discover and load tools
        plugin_dir = Path(__file__).parent / "plugins"
        self.tool_registry.discover_tools(plugin_dir)
        
        # Register MCP handlers
        @self.server.list_tools()
        async def list_tools() -> list[Dict[str, Any]]:
            return self.tool_registry.list_tools()
            
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> Any:
            tool = self.tool_registry.get_tool(name)
            if not tool:
                raise ValueError(f"Unknown tool: {name}")
                
            # Create context
            context = ToolContext(
                request_id=str(uuid.uuid4()),
                metadata={"mcp_version": "1.0"}
            )
            
            # Execute tool
            try:
                result = await tool.execute(arguments, context)
                return result
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                return {
                    "status": "error",
                    "error": str(e)
                }
                
    async def run(self):
        """Run the server"""
        await self.initialize()
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="zen-mcp-server",
                    server_version=self.config.get("version", "1.0.0")
                )
            )

async def main():
    """Main entry point"""
    server = ZenMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())
```

## Key Advantages

### 1. Simplicity
- Single provider implementation handles all models
- No provider-specific code to maintain
- LiteLLM handles all the complexity

### 2. Flexibility
- Easy to add new models via configuration
- Tools are self-contained plugins
- Middleware system for cross-cutting concerns

### 3. Reliability
- Built-in retry logic via LiteLLM
- Automatic fallback to alternative models
- Comprehensive error handling

### 4. Observability
- Structured logging throughout
- Metrics collection built-in
- Cost tracking for all API calls

### 5. Developer Experience
- Type safety with Pydantic models
- Clear interfaces and contracts
- Comprehensive testing utilities

### 6. Performance
- Async throughout for better concurrency
- Connection pooling via LiteLLM
- Response streaming support

## Migration Path

1. **Phase 1**: Set up new project structure
2. **Phase 2**: Implement core components (provider, registry, base tool)
3. **Phase 3**: Migrate existing tools to new plugin format
4. **Phase 4**: Add middleware and advanced features
5. **Phase 5**: Comprehensive testing and documentation

## Configuration Examples

### Adding a New Model

```yaml
# config/models.yaml
models:
  my-custom-model:
    provider: custom
    base_url: "${MY_MODEL_URL}"
    api_key: "${MY_MODEL_API_KEY}"
    context_window: 16384
    max_output: 4096
    capabilities:
      streaming: true
```

### Creating a New Tool

```yaml
# src/plugins/my_tool/config.yaml
name: my_tool
description: "My custom tool"
version: "1.0.0"
author: "Your Name"
models:
  default: "gpt-4-turbo"
  allowed:
    - "gpt-4-turbo"
    - "claude-3-opus"
rate_limits:
  requests_per_minute: 60
  tokens_per_minute: 150000
```

## Conclusion

This architecture leverages LiteLLM's power to create a simple, maintainable, and extensible MCP server. By eliminating provider-specific code and embracing a plugin architecture, the system becomes much easier to understand, test, and extend.