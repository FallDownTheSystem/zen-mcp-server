"""
Pure aiohttp-based OpenAI provider for maximum concurrency and deadlock prevention.

This provider:
1. Uses only aiohttp for HTTP requests (no external SDK dependencies)
2. Implements minimal OpenAI API interface
3. Designed for high concurrency without deadlocks
4. Lightweight and focused on chat completions
"""

import asyncio
import json
import logging
import time
from typing import Optional

import aiohttp

from .base import (
    ModelCapabilities,
    ModelProvider,
    ModelResponse,
    ProviderType,
    create_temperature_constraint,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(ModelProvider):
    """Pure aiohttp-based OpenAI provider for maximum concurrency."""
    
    # Model configurations - matching the original OpenAI provider
    SUPPORTED_MODELS = {
        "o3": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3",
            friendly_name="OpenAI (O3)",
            context_window=200_000,
            max_output_tokens=100_000,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=False,  # aiohttp version doesn't support streaming yet
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,
            max_image_size_mb=20.0,
            supports_temperature=False,
            temperature_constraint=create_temperature_constraint("fixed"),
            description="Strong reasoning (200K context) - Logical problems, code generation, systematic analysis",
            aliases=[],
            timeout=300.0,
        ),
        "o3-mini": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3-mini",
            friendly_name="OpenAI (O3-mini)",
            context_window=200_000,
            max_output_tokens=100_000,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=False,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,
            max_image_size_mb=20.0,
            supports_temperature=False,
            temperature_constraint=create_temperature_constraint("fixed"),
            description="Fast O3 variant (200K context) - Balanced performance/speed, moderate complexity",
            aliases=["o3mini", "o3-mini"],
        ),
        "o3-pro-2025-06-10": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3-pro-2025-06-10",
            friendly_name="OpenAI (O3-Pro)",
            context_window=200_000,
            max_output_tokens=100_000,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=False,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,
            max_image_size_mb=20.0,
            supports_temperature=False,
            temperature_constraint=create_temperature_constraint("fixed"),
            description="Professional-grade reasoning (200K context) - EXTREMELY EXPENSIVE: Only for the most complex problems requiring universe-scale complexity analysis OR when the user explicitly asks for this model. Use sparingly for critical architectural decisions or exceptionally complex debugging that other models cannot handle.",
            aliases=["o3-pro"],
            timeout=1800.0,
        ),
        "o3-deep-research-2025-06-26": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3-deep-research-2025-06-26",
            friendly_name="OpenAI (O3-Deep-Research)",
            context_window=200_000,
            max_output_tokens=100_000,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=False,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,
            max_image_size_mb=20.0,
            supports_temperature=False,
            temperature_constraint=create_temperature_constraint("fixed"),
            description="Deep research model (200K context) - Specialized for comprehensive analysis, literature review, and complex research tasks",
            aliases=["o3-deep-research", "deep-research", "research", "o3-research"],
            timeout=3600.0,
        ),
        "o4-mini": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o4-mini",
            friendly_name="OpenAI (O4-mini)",
            context_window=200_000,
            max_output_tokens=100_000,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=False,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,
            max_image_size_mb=20.0,
            supports_temperature=True,
            temperature_constraint=create_temperature_constraint("range"),
            description="Latest reasoning model (200K context) - Optimized for shorter contexts, rapid reasoning",
            aliases=["o4mini"],
            timeout=180.0,
        ),
        "gpt-4.1-2025-04-14": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="gpt-4.1-2025-04-14",
            friendly_name="OpenAI (GPT-4.1)",
            context_window=1_000_000,
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=False,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,
            max_image_size_mb=20.0,
            supports_temperature=True,
            temperature_constraint=create_temperature_constraint("range"),
            description="GPT-4.1 (1M context) - Advanced reasoning model with large context window",
            aliases=["gpt4.1"],
            timeout=300.0,
        ),
    }

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", **kwargs):
        """Initialize aiohttp-based OpenAI provider."""
        super().__init__(api_key, **kwargs)
        self.base_url = base_url.rstrip('/')
        self._session = None
        self._session_lock = asyncio.Lock()
        
        # Configure connection limits for high concurrency
        self.max_connections = kwargs.get("max_connections", 100)
        self.max_connections_per_host = kwargs.get("max_connections_per_host", 30)
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with proper configuration."""
        if self._session is not None and not self._session.closed:
            return self._session
            
        async with self._session_lock:
            if self._session is not None and not self._session.closed:
                return self._session
                
            # Configure connector for high concurrency
            connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                limit_per_host=self.max_connections_per_host,
                ttl_dns_cache=300,
                use_dns_cache=True,
            )
            
            # Configure timeout
            timeout = aiohttp.ClientTimeout(total=300)
            
            # Create session with proper headers
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "zen-mcp-server/1.0 (aiohttp)",
                }
            )
            
            logger.debug("Created new aiohttp session for OpenAI API")
            return self._session
    
    async def aclose(self):
        """Close aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get capabilities for a specific model."""
        resolved_name = self._resolve_model_name(model_name)
        if resolved_name not in self.SUPPORTED_MODELS:
            raise ValueError(f"Model {model_name} not supported by AioHttpOpenAI provider")
        return self.SUPPORTED_MODELS[resolved_name]
    
    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.OPENAI
    
    def validate_model_name(self, model_name: str) -> bool:
        """Validate if the model name is supported."""
        resolved_name = self._resolve_model_name(model_name)
        return resolved_name in self.SUPPORTED_MODELS
    
    def supports_thinking_mode(self, model_name: str) -> bool:
        """Check if the model supports extended reasoning effort mode."""
        try:
            capabilities = self.get_capabilities(model_name)
            return capabilities.supports_extended_thinking
        except ValueError:
            return False
    
    def count_tokens(self, text: str, model_name: str) -> int:
        """Count tokens for the given text. Simple approximation."""
        return len(text) // 4
    
    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Synchronous wrapper that properly handles event loop contexts."""
        logger.warning(
            "Using synchronous generate_content with AioHttpOpenAI provider is not recommended. "
            "Use agenerate_content instead for better performance."
        )
        
        try:
            # Check if we're already in an async context
            loop = asyncio.get_running_loop()
            logger.error(
                "Cannot use synchronous generate_content from within async context. "
                "The calling code should use agenerate_content instead."
            )
            raise RuntimeError(
                "AioHttpOpenAI provider cannot be used synchronously from async context. "
                "Use agenerate_content instead, or switch to a different provider for sync usage."
            )
        except RuntimeError:
            # No running event loop, we can create one
            async def _async_generate():
                return await self.agenerate_content(
                    prompt=prompt,
                    model_name=model_name,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    **kwargs
                )
            
            return asyncio.run(_async_generate())
    
    async def agenerate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Async content generation using pure aiohttp."""
        resolved_model = self._resolve_model_name(model_name)
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Build request payload
        payload = {
            "model": resolved_model,
            "messages": messages,
        }
        
        # Handle temperature based on model capabilities
        capabilities = self.get_capabilities(model_name)
        if capabilities.supports_temperature:
            effective_temperature = self.get_effective_temperature(model_name, temperature)
            if effective_temperature is not None:
                payload["temperature"] = effective_temperature
        
        # Add max tokens if specified
        if max_output_tokens:
            payload["max_tokens"] = max_output_tokens
        
        # Handle reasoning effort for thinking models
        reasoning_effort = kwargs.get("reasoning_effort", "medium")
        if self.supports_thinking_mode(model_name):
            payload["reasoning_effort"] = reasoning_effort
        
        # Make the API call
        session = await self._get_session()
        url = f"{self.base_url}/chat/completions"
        
        start_time = time.time()
        
        try:
            async with session.post(url, json=payload) as response:
                response_time = time.time() - start_time
                
                # Check for HTTP errors
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"OpenAI API error {response.status}: {error_text}")
                    raise RuntimeError(f"OpenAI API error {response.status}: {error_text}")
                
                # Parse JSON response
                response_data = await response.json()
                
                # Extract content and usage
                content = response_data["choices"][0]["message"]["content"]
                usage = {}
                if "usage" in response_data:
                    usage_data = response_data["usage"]
                    usage = {
                        "input_tokens": usage_data.get("prompt_tokens", 0),
                        "output_tokens": usage_data.get("completion_tokens", 0),
                        "total_tokens": usage_data.get("total_tokens", 0),
                    }
                
                return ModelResponse(
                    content=content,
                    usage=usage,
                    model_name=resolved_model,
                    friendly_name=f"OpenAI {resolved_model} (aiohttp)",
                    provider=ProviderType.OPENAI,
                    metadata={
                        "finish_reason": response_data["choices"][0].get("finish_reason"),
                        "model": response_data.get("model"),
                        "id": response_data.get("id"),
                        "response_time": response_time,
                        "http_backend": "aiohttp",
                    }
                )
                
        except aiohttp.ClientError as e:
            logger.error(f"aiohttp client error: {e}")
            raise RuntimeError(f"HTTP client error: {e}")
        except asyncio.TimeoutError:
            logger.error(f"Request timeout for model {model_name}")
            raise RuntimeError(f"Request timeout for model {model_name}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise RuntimeError(f"Invalid JSON response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise RuntimeError(f"Unexpected error: {e}")
    
    def _resolve_model_name(self, model_name: str) -> str:
        """Resolve model name to canonical form, including aliases."""
        model_name_lower = model_name.lower()
        
        # Check exact matches first
        for supported_model in self.SUPPORTED_MODELS:
            if supported_model.lower() == model_name_lower:
                return supported_model
        
        # Check aliases
        for supported_model, capabilities in self.SUPPORTED_MODELS.items():
            if hasattr(capabilities, 'aliases') and capabilities.aliases:
                for alias in capabilities.aliases:
                    if alias.lower() == model_name_lower:
                        return supported_model
                        
        # Return as-is if not found
        return model_name