"""Custom OpenAI provider that handles HTTP requests manually."""

import json
import logging
from typing import Optional
import urllib.request
import urllib.parse
from urllib.error import HTTPError, URLError

from providers.base import ModelProvider, ModelResponse, ModelCapabilities, ProviderType, RangeTemperatureConstraint

logger = logging.getLogger(__name__)


class CustomOpenAI(ModelProvider):
    """Custom OpenAI provider that handles HTTP requests manually without external dependencies."""
    
    SUPPORTED_MODELS = {
        "o3-mini": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3-mini",
            friendly_name="OpenAI o3-mini",
            context_window=200000,
            max_output_tokens=100000,
            supports_extended_thinking=True,
            supports_system_prompts=True,
            supports_streaming=False,
            supports_function_calling=True,
            supports_images=False,
            supports_temperature=True,
            temperature_constraint=RangeTemperatureConstraint(0.0, 2.0, 1.0),
            timeout=300.0,  # 5 minutes for reasoning models
            description="OpenAI's o3-mini reasoning model with enhanced problem-solving capabilities",
        ),
    }

    def __init__(self, api_key: str, **kwargs):
        """Initialize the Custom OpenAI provider."""
        super().__init__(api_key, **kwargs)
        self.base_url = kwargs.get("base_url", "https://api.openai.com/v1")
        
    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get capabilities for a specific model."""
        resolved_name = self._resolve_model_name(model_name)
        if resolved_name not in self.SUPPORTED_MODELS:
            raise ValueError(f"Model {model_name} not supported by CustomOpenAI provider")
        return self.SUPPORTED_MODELS[resolved_name]
    
    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using manual HTTP requests."""
        resolved_model = self._resolve_model_name(model_name)
        
        # Prepare the request payload
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_output_tokens:
            payload["max_tokens"] = max_output_tokens
            
        # Convert to JSON
        json_data = json.dumps(payload).encode('utf-8')
        
        # Create the request
        url = f"{self.base_url}/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
            'User-Agent': 'zen-mcp-server/1.0'
        }
        
        try:
            # Make the HTTP request
            request = urllib.request.Request(url, data=json_data, headers=headers)
            
            with urllib.request.urlopen(request, timeout=self.SUPPORTED_MODELS[resolved_model].timeout) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                
            # Extract content from response
            content = response_data["choices"][0]["message"]["content"]
            
            # Extract usage information
            usage = {}
            if "usage" in response_data:
                usage_data = response_data["usage"]
                usage = {
                    "input_tokens": usage_data.get("prompt_tokens", 0),
                    "output_tokens": usage_data.get("completion_tokens", 0),
                    "total_tokens": usage_data.get("total_tokens", 0)
                }
            
            return ModelResponse(
                content=content,
                usage=usage,
                model_name=resolved_model,
                friendly_name="OpenAI o3-mini",
                provider=ProviderType.OPENAI,
                metadata={"raw_response": response_data}
            )
            
        except HTTPError as e:
            error_body = e.read().decode('utf-8') if hasattr(e, 'read') else str(e)
            logger.error(f"HTTP error {e.code}: {error_body}")
            raise RuntimeError(f"OpenAI API error {e.code}: {error_body}")
        except URLError as e:
            logger.error(f"URL error: {e}")
            raise RuntimeError(f"Connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise RuntimeError(f"Invalid JSON response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise RuntimeError(f"Unexpected error: {e}")
    
    def count_tokens(self, text: str, model_name: str) -> int:
        """Count tokens for the given text. Simplified approximation."""
        # Simple approximation: ~4 characters per token
        return len(text) // 4
    
    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.OPENAI
    
    def validate_model_name(self, model_name: str) -> bool:
        """Validate if the model name is supported by this provider."""
        resolved_name = self._resolve_model_name(model_name)
        return resolved_name in self.SUPPORTED_MODELS
    
    def supports_thinking_mode(self, model_name: str) -> bool:
        """Check if the model supports extended reasoning effort mode."""
        try:
            capabilities = self.get_capabilities(model_name)
            return capabilities.supports_extended_thinking
        except ValueError:
            return False