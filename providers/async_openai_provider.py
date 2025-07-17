"""
Async-native OpenAI provider that avoids deadlocks by using proper async patterns.

This provider:
1. Uses AsyncOpenAI client exclusively (no sync fallback)
2. Properly manages async client lifecycle
3. Uses aiohttp backend for better concurrency
4. Avoids mixing sync/async contexts
"""

import asyncio
import logging
import os
from typing import Optional

from openai import AsyncOpenAI

from .base import (
    ModelCapabilities,
    ModelProvider,
    ModelResponse,
    ProviderType,
    create_temperature_constraint,
)

logger = logging.getLogger(__name__)


class AsyncOpenAIProvider(ModelProvider):
    """Async-native OpenAI provider with proper concurrency handling."""
    
    # Model configurations - complete set matching AioHttpOpenAI provider
    SUPPORTED_MODELS = {
        "o3": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3",
            friendly_name="OpenAI (O3)",
            context_window=200_000,
            max_output_tokens=100_000,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
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
            supports_streaming=True,
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
            supports_streaming=True,
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
            supports_streaming=True,
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
            supports_streaming=True,
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
            supports_streaming=True,
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
        """Initialize async-native OpenAI provider."""
        super().__init__(api_key, **kwargs)
        self.base_url = base_url
        self._client = None
        self._client_lock = asyncio.Lock()
        self._session = None
        
        # Configure for aiohttp backend if available
        self._use_aiohttp = kwargs.get("use_aiohttp", True)
        
    async def _get_client(self) -> AsyncOpenAI:
        """Get or create async OpenAI client with proper lifecycle management."""
        if self._client is not None:
            return self._client
            
        async with self._client_lock:
            if self._client is not None:
                return self._client
                
            # Configure client with aiohttp backend if available
            client_kwargs = {
                "api_key": self.api_key,
                "base_url": self.base_url,
            }
            
            if self._use_aiohttp:
                try:
                    # Try to use aiohttp backend for better concurrency
                    from openai import DefaultAioHttpClient
                    client_kwargs["http_client"] = DefaultAioHttpClient()
                    logger.debug("Using aiohttp backend for AsyncOpenAI client")
                except ImportError:
                    logger.debug("aiohttp not available, using default httpx backend")
                    
            self._client = AsyncOpenAI(**client_kwargs)
            logger.debug("Created new AsyncOpenAI client")
            return self._client
    
    async def aclose(self):
        """Properly close async resources."""
        if self._client:
            await self._client.close()
            self._client = None
        if self._session:
            await self._session.close()
            self._session = None
    
    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get capabilities for a specific model."""
        resolved_name = self._resolve_model_name(model_name)
        if resolved_name not in self.SUPPORTED_MODELS:
            raise ValueError(f"Model {model_name} not supported by AsyncOpenAI provider")
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
        # Simple approximation: ~4 characters per token
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
        """
        Synchronous generate_content - NOT RECOMMENDED for this provider.
        
        This provider is designed for async usage. This method is provided
        for compatibility but will use asyncio.run() which can cause issues
        in async contexts.
        """
        logger.warning(
            "Using synchronous generate_content with AsyncOpenAI provider is not recommended. "
            "Use agenerate_content instead for better performance and to avoid deadlocks."
        )
        
        # Run in a new event loop to avoid conflicts
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, this will likely fail
                raise RuntimeError(
                    "Cannot use synchronous generate_content from within async context. "
                    "Use agenerate_content instead."
                )
        except RuntimeError:
            pass
            
        # Create a new event loop for this sync call
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
        """Async content generation using AsyncOpenAI client."""
        resolved_model = self._resolve_model_name(model_name)
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Build request parameters
        request_params = {
            "model": resolved_model,
            "messages": messages,
        }
        
        # Handle temperature based on model capabilities
        capabilities = self.get_capabilities(model_name)
        if capabilities.supports_temperature:
            effective_temperature = self.get_effective_temperature(model_name, temperature)
            if effective_temperature is not None:
                request_params["temperature"] = effective_temperature
        
        # Add max tokens if specified
        if max_output_tokens:
            request_params["max_tokens"] = max_output_tokens
        
        # Handle reasoning effort for thinking models
        reasoning_effort = kwargs.get("reasoning_effort", "medium")
        if self.supports_thinking_mode(model_name):
            request_params["reasoning_effort"] = reasoning_effort
        
        # Make the API call
        client = await self._get_client()
        
        try:
            response = await client.chat.completions.create(**request_params)
            
            # Extract content and usage
            content = response.choices[0].message.content
            usage = {
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }
            
            return ModelResponse(
                content=content,
                usage=usage,
                model_name=resolved_model,
                friendly_name=f"OpenAI {resolved_model}",
                provider=ProviderType.OPENAI,
                metadata={
                    "finish_reason": response.choices[0].finish_reason,
                    "model": response.model,
                    "id": response.id,
                    "created": response.created,
                }
            )
            
        except Exception as e:
            logger.error(f"AsyncOpenAI API error: {e}")
            raise RuntimeError(f"OpenAI API error: {e}")
    
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