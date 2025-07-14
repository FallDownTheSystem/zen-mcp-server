#!/usr/bin/env python3
"""
Proof of Concept: LiteLLM-based Zen MCP Server

This demonstrates the core concepts of the new architecture:
1. Single LiteLLM provider for all models
2. Plugin-based tool system
3. Configuration-driven model management
4. Clean, simple interfaces

To run:
1. Install dependencies: pip install litellm pydantic pyyaml
2. Set API keys: export OPENAI_API_KEY=... ANTHROPIC_API_KEY=...
3. Run: python litellm_poc.py
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, AsyncIterator
from pathlib import Path
import logging
from dataclasses import dataclass
from datetime import datetime

import litellm
from litellm import acompletion, completion_cost, token_counter
from pydantic import BaseModel, Field
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# MODELS AND CONFIGURATION
# ============================================================================

class ModelRequest(BaseModel):
    """Unified request model for all LLM calls"""
    model: str
    messages: list[dict]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    tools: Optional[list[dict]] = None
    response_format: Optional[dict] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ModelResponse(BaseModel):
    """Unified response model"""
    content: str
    model: str
    usage: Dict[str, int]
    cost: Optional[float] = None
    provider: str
    response_time_ms: int
    metadata: Dict[str, Any] = Field(default_factory=dict)

@dataclass
class ModelConfig:
    """Model configuration"""
    name: str
    provider: str
    aliases: List[str]
    context_window: int
    max_output: int
    capabilities: Dict[str, bool]
    custom_endpoint: Optional[str] = None

# Example model configurations (would be loaded from YAML in real implementation)
MODEL_CONFIGS = {
    "gpt-4-turbo": ModelConfig(
        name="gpt-4-turbo",
        provider="openai",
        aliases=["gpt4", "4-turbo"],
        context_window=128000,
        max_output=4096,
        capabilities={
            "vision": True,
            "function_calling": True,
            "json_mode": True,
            "streaming": True
        }
    ),
    "claude-3-opus": ModelConfig(
        name="claude-3-opus-20240229",
        provider="anthropic",
        aliases=["opus", "claude-opus"],
        context_window=200000,
        max_output=4096,
        capabilities={
            "vision": True,
            "function_calling": False,
            "json_mode": False,
            "streaming": True
        }
    ),
    "gemini-pro": ModelConfig(
        name="gemini/gemini-pro",
        provider="google",
        aliases=["gemini", "g-pro"],
        context_window=30720,
        max_output=2048,
        capabilities={
            "vision": False,
            "function_calling": True,
            "json_mode": False,
            "streaming": True
        }
    ),
}

# ============================================================================
# LITELLM PROVIDER
# ============================================================================

class LiteLLMProvider:
    """Single provider class that handles all models through LiteLLM"""
    
    def __init__(self, model_configs: Dict[str, ModelConfig], debug: bool = False):
        self.model_configs = model_configs
        self.alias_map = self._build_alias_map()
        
        # Configure LiteLLM
        litellm.drop_params = True
        litellm.set_verbose = debug
        
        # Add callbacks
        litellm.success_callback = ["langfuse"]  # Example: could add logging callbacks
        
    def _build_alias_map(self) -> Dict[str, str]:
        """Build alias to model name mapping"""
        alias_map = {}
        for model_name, config in self.model_configs.items():
            for alias in config.aliases:
                alias_map[alias.lower()] = model_name
        return alias_map
    
    def resolve_model(self, model: str) -> str:
        """Resolve model aliases to actual model names"""
        model_lower = model.lower()
        
        # Check if it's already a known model
        if model in self.model_configs:
            return model
            
        # Check aliases
        if model_lower in self.alias_map:
            return self.alias_map[model_lower]
            
        # Return as-is if not found
        return model
    
    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate completion using LiteLLM"""
        start_time = datetime.now()
        
        # Resolve model name and get config
        model_name = self.resolve_model(request.model)
        model_config = self.model_configs.get(model_name)
        
        # Use LiteLLM model string if we have config
        litellm_model = model_config.name if model_config else request.model
        
        # Build kwargs
        kwargs = {
            "model": litellm_model,
            "messages": request.messages,
            "temperature": request.temperature,
            "stream": False,  # Never stream in this method
        }
        
        # Add optional parameters based on capabilities
        if request.max_tokens and model_config:
            kwargs["max_tokens"] = min(request.max_tokens, model_config.max_output)
        elif request.max_tokens:
            kwargs["max_tokens"] = request.max_tokens
            
        if request.tools and model_config and model_config.capabilities.get("function_calling"):
            kwargs["tools"] = request.tools
            
        if request.response_format and model_config and model_config.capabilities.get("json_mode"):
            kwargs["response_format"] = request.response_format
        
        # Make the API call
        try:
            response = await acompletion(**kwargs)
            
            # Calculate cost
            cost = None
            try:
                cost = completion_cost(completion_response=response)
            except:
                pass
            
            # Extract provider
            provider = litellm_model.split("/")[0] if "/" in litellm_model else "unknown"
            
            # Calculate response time
            response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return ModelResponse(
                content=response.choices[0].message.content or "",
                model=model_name if model_config else request.model,
                usage={
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                cost=cost,
                provider=provider,
                response_time_ms=response_time_ms,
                metadata={
                    "response_id": response.id,
                    "finish_reason": response.choices[0].finish_reason,
                    "litellm_model": litellm_model,
                }
            )
            
        except Exception as e:
            logger.error(f"LiteLLM generation failed: {e}")
            raise
    
    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        """Stream completion using LiteLLM"""
        # Resolve model
        model_name = self.resolve_model(request.model)
        model_config = self.model_configs.get(model_name)
        litellm_model = model_config.name if model_config else request.model
        
        # Check streaming support
        if model_config and not model_config.capabilities.get("streaming", True):
            # Fallback to non-streaming
            response = await self.generate(request)
            yield response.content
            return
        
        # Build kwargs
        kwargs = {
            "model": litellm_model,
            "messages": request.messages,
            "temperature": request.temperature,
            "stream": True,
        }
        
        if request.max_tokens:
            kwargs["max_tokens"] = request.max_tokens
        
        # Stream the response
        async for chunk in await acompletion(**kwargs):
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def count_tokens(self, text: str, model: str) -> int:
        """Count tokens for text"""
        model_name = self.resolve_model(model)
        model_config = self.model_configs.get(model_name)
        litellm_model = model_config.name if model_config else model
        
        try:
            return token_counter(model=litellm_model, text=text)
        except:
            # Fallback to approximate count
            return len(text) // 4

# ============================================================================
# TOOL SYSTEM
# ============================================================================

class ToolContext(BaseModel):
    """Context passed to tools during execution"""
    request_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class BaseTool(ABC):
    """Base class for all tools"""
    
    def __init__(self, provider: LiteLLMProvider):
        self.provider = provider
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description"""
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Get JSON schema for parameters"""
        pass
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        """Execute the tool"""
        pass

# ============================================================================
# EXAMPLE TOOLS
# ============================================================================

class ChatTool(BaseTool):
    """Simple chat tool implementation"""
    
    @property
    def name(self) -> str:
        return "chat"
    
    @property
    def description(self) -> str:
        return "General purpose chat with AI models"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt to send to the model"
                },
                "model": {
                    "type": "string",
                    "description": "Model to use (e.g., 'gpt4', 'opus', 'gemini')"
                },
                "temperature": {
                    "type": "number",
                    "description": "Temperature (0-2)",
                    "default": 0.7
                }
            },
            "required": ["prompt", "model"]
        }
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        """Execute chat request"""
        request = ModelRequest(
            model=params["model"],
            messages=[{"role": "user", "content": params["prompt"]}],
            temperature=params.get("temperature", 0.7),
            metadata={"tool": "chat", "request_id": context.request_id}
        )
        
        try:
            response = await self.provider.generate(request)
            
            return {
                "status": "success",
                "content": response.content,
                "model": response.model,
                "provider": response.provider,
                "usage": response.usage,
                "cost": response.cost,
                "response_time_ms": response.response_time_ms
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

class ConsensussTool(BaseTool):
    """Multi-model consensus tool"""
    
    @property
    def name(self) -> str:
        return "consensus"
    
    @property
    def description(self) -> str:
        return "Get consensus from multiple AI models"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The question to get consensus on"
                },
                "models": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of models to consult"
                }
            },
            "required": ["prompt", "models"]
        }
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        """Execute consensus request"""
        prompt = params["prompt"]
        models = params["models"]
        
        # Run all models in parallel
        tasks = []
        for model in models:
            request = ModelRequest(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                metadata={"tool": "consensus", "request_id": context.request_id}
            )
            tasks.append(self.provider.generate(request))
        
        # Gather results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process responses
        responses = []
        total_cost = 0
        
        for model, result in zip(models, results):
            if isinstance(result, Exception):
                responses.append({
                    "model": model,
                    "status": "error",
                    "error": str(result)
                })
            else:
                responses.append({
                    "model": result.model,
                    "provider": result.provider,
                    "status": "success",
                    "content": result.content,
                    "usage": result.usage,
                    "cost": result.cost
                })
                if result.cost:
                    total_cost += result.cost
        
        return {
            "status": "complete",
            "responses": responses,
            "total_cost": total_cost if total_cost > 0 else None,
            "models_consulted": len(models),
            "successful_responses": len([r for r in responses if r["status"] == "success"])
        }

# ============================================================================
# DEMO APPLICATION
# ============================================================================

async def demo():
    """Demonstrate the LiteLLM-based architecture"""
    
    # Initialize provider
    provider = LiteLLMProvider(MODEL_CONFIGS, debug=False)
    
    # Initialize tools
    chat_tool = ChatTool(provider)
    consensus_tool = ConsensussTool(provider)
    
    print("=== LiteLLM Zen MCP Server Demo ===\n")
    
    # Demo 1: Simple chat with alias resolution
    print("1. Testing chat with model aliases:")
    context = ToolContext(request_id="demo-001")
    
    for model_alias in ["gpt4", "opus", "gemini"]:
        print(f"\n   Using alias '{model_alias}':")
        result = await chat_tool.execute({
            "prompt": "Say hello in exactly 5 words",
            "model": model_alias,
            "temperature": 0.5
        }, context)
        
        if result["status"] == "success":
            print(f"   Model: {result['model']} (Provider: {result['provider']})")
            print(f"   Response: {result['content']}")
            print(f"   Tokens: {result['usage']['total_tokens']}")
            if result["cost"]:
                print(f"   Cost: ${result['cost']:.4f}")
            print(f"   Time: {result['response_time_ms']}ms")
        else:
            print(f"   Error: {result['error']}")
    
    # Demo 2: Consensus across models
    print("\n\n2. Testing consensus across multiple models:")
    context = ToolContext(request_id="demo-002")
    
    result = await consensus_tool.execute({
        "prompt": "What's the most important consideration when designing a distributed system? Answer in one sentence.",
        "models": ["gpt4", "opus", "gemini"]
    }, context)
    
    print(f"\n   Status: {result['status']}")
    print(f"   Models consulted: {result['models_consulted']}")
    print(f"   Successful responses: {result['successful_responses']}")
    if result["total_cost"]:
        print(f"   Total cost: ${result['total_cost']:.4f}")
    
    print("\n   Responses:")
    for response in result["responses"]:
        print(f"\n   {response['model']} ({response['provider']}):")
        if response["status"] == "success":
            print(f"   - {response['content']}")
        else:
            print(f"   - Error: {response['error']}")
    
    # Demo 3: Streaming (conceptual - would be async generator in real use)
    print("\n\n3. Testing streaming capability:")
    context = ToolContext(request_id="demo-003")
    
    request = ModelRequest(
        model="gpt4",
        messages=[{"role": "user", "content": "Count from 1 to 5 slowly"}],
        temperature=0.7
    )
    
    print("   Streaming response: ", end="", flush=True)
    async for chunk in provider.stream(request):
        print(chunk, end="", flush=True)
    print("\n")
    
    # Demo 4: Token counting
    print("\n4. Testing token counting:")
    test_text = "The quick brown fox jumps over the lazy dog. " * 10
    
    for model in ["gpt4", "opus"]:
        tokens = provider.count_tokens(test_text, model)
        print(f"   {model}: {tokens} tokens")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    # Run the demo
    asyncio.run(demo())