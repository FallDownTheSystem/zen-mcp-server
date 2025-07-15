"""LiteLLM provider wrapper for unified model access."""

import logging
import os
from typing import Optional

import litellm
from litellm import acompletion, completion
from litellm.exceptions import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

from .base import (
    ModelCapabilities,
    ModelProvider,
    ModelResponse,
    ProviderType,
    create_temperature_constraint,
)

logger = logging.getLogger(__name__)


class LiteLLMProvider(ModelProvider):
    """Unified provider using LiteLLM for all model access.

    This is a thin wrapper around LiteLLM that:
    1. Calls litellm.completion() or litellm.acompletion()
    2. Maps LiteLLM exceptions to MCP error types
    3. Returns responses in the expected format
    4. Preserves timeout parameter passing from tools
    """

    FRIENDLY_NAME = "LiteLLM"

    def __init__(self, **kwargs):
        """Initialize the LiteLLM provider.

        Args:
            **kwargs: Additional configuration options
        """
        # No API key needed - LiteLLM will use environment variables
        super().__init__(api_key="", **kwargs)

        # Load LiteLLM configuration if available
        config_path = kwargs.get("config_path", "litellm_config.yaml")
        if os.path.exists(config_path):
            logger.info(f"Loading LiteLLM config from {config_path}")
            # LiteLLM will automatically load config from environment

        # Get model metadata (if provided)
        self.model_metadata = kwargs.get("model_metadata", {})

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        # Return CUSTOM as this is a meta-provider
        return ProviderType.CUSTOM

    def validate_model_name(self, model_name: str) -> bool:
        """Validate if the model name is supported.

        LiteLLM handles its own model validation, so we always return True
        and let LiteLLM handle any errors.
        """
        return True

    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get capabilities for a specific model.

        Returns default capabilities as LiteLLM handles model-specific
        behavior internally.
        """
        # Check if we have metadata for this model
        if model_name in self.model_metadata:
            metadata = self.model_metadata[model_name]
            return ModelCapabilities(
                provider=ProviderType.CUSTOM,
                model_name=model_name,
                friendly_name=metadata.get("friendly_name", "LiteLLM Model"),
                context_window=metadata.get("context_window", 128000),
                max_output_tokens=metadata.get("max_output_tokens", 8192),
                supports_extended_thinking=metadata.get("supports_extended_thinking", False),
                supports_system_prompts=metadata.get("supports_system_prompts", True),
                supports_streaming=metadata.get("supports_streaming", True),
                supports_function_calling=metadata.get("supports_function_calling", False),
                supports_images=metadata.get("supports_images", False),
                max_image_size_mb=metadata.get("max_image_size_mb", 0.0),
                supports_temperature=metadata.get("supports_temperature", True),
                temperature_constraint=create_temperature_constraint(metadata.get("temperature_constraint", "range")),
                supports_json_mode=metadata.get("supports_json_mode", False),
                max_thinking_tokens=metadata.get("max_thinking_tokens", 0),
                is_custom=metadata.get("is_custom", False),
            )

        # Return default capabilities for unknown models
        return ModelCapabilities(
            provider=ProviderType.CUSTOM,
            model_name=model_name,
            friendly_name="LiteLLM Model",
            context_window=128000,  # Default to large context
            max_output_tokens=8192,  # Default to 8k output
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=False,
            supports_images=False,
            supports_temperature=True,
            temperature_constraint=create_temperature_constraint("range"),
        )

    def supports_thinking_mode(self, model_name: str) -> bool:
        """Check if the model supports extended thinking mode."""
        if model_name in self.model_metadata:
            return self.model_metadata[model_name].get("supports_extended_thinking", False)
        # Check for known thinking models
        return "o3" in model_name.lower() or "o4" in model_name.lower()

    def count_tokens(self, text: str, model_name: str) -> int:
        """Count tokens for the given text.

        Uses LiteLLM's token counting functionality.
        """
        try:
            # LiteLLM provides token counting
            return litellm.token_counter(model=model_name, text=text)
        except Exception as e:
            logger.debug(f"Token counting failed for {model_name}: {e}")
            # Fallback to simple estimation (4 chars per token)
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
        """Generate content using LiteLLM.

        This is a thin wrapper that:
        1. Formats the request for LiteLLM
        2. Calls litellm.completion()
        3. Maps exceptions to MCP errors
        4. Returns response in expected format
        """
        try:
            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Extract timeout if provided by tools
            timeout = kwargs.pop("timeout", None)

            # Extract images if provided
            images = kwargs.pop("images", None)
            if images:
                # LiteLLM expects images in the message content
                # Format depends on the model, but generally base64 or URLs work
                user_message = messages[-1]
                user_message["content"] = [
                    {"type": "text", "text": prompt},
                ]
                for image in images:
                    if image.startswith("data:") or image.startswith("http"):
                        # URL or base64 data URI
                        user_message["content"].append({"type": "image_url", "image_url": {"url": image}})
                    else:
                        # File path - read and convert to base64
                        import base64

                        with open(image, "rb") as f:
                            img_data = base64.b64encode(f.read()).decode()
                            user_message["content"].append(
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_data}"}}
                            )

            # Build completion kwargs
            completion_kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
            }

            # Add optional parameters
            if max_output_tokens:
                completion_kwargs["max_tokens"] = max_output_tokens

            if timeout:
                completion_kwargs["timeout"] = timeout

            # Add any additional kwargs that LiteLLM might use
            # (e.g., thinking_mode, response_format, etc.)
            for key, value in kwargs.items():
                if value is not None:
                    completion_kwargs[key] = value

            # Call LiteLLM
            response = completion(**completion_kwargs)

            # Extract response content
            content = response.choices[0].message.content

            # Build usage dict
            usage = {}
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "input_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "output_tokens": getattr(response.usage, "completion_tokens", 0),
                    "total_tokens": getattr(response.usage, "total_tokens", 0),
                }

            # Return in expected format
            return ModelResponse(
                content=content,
                usage=usage,
                model_name=model_name,
                friendly_name=self.FRIENDLY_NAME,
                provider=self.get_provider_type(),
                metadata={
                    "litellm_model_id": getattr(response, "id", None),
                    "litellm_model": getattr(response, "model", model_name),
                },
            )

        except Timeout as e:
            # Timeout error - re-raise as-is for proper handling
            logger.error(f"LiteLLM timeout error: {e}")
            raise
        except RateLimitError as e:
            # Rate limit error - re-raise as-is
            logger.error(f"LiteLLM rate limit error: {e}")
            raise
        except AuthenticationError as e:
            # Auth error - re-raise as-is
            logger.error(f"LiteLLM authentication error: {e}")
            raise
        except BadRequestError as e:
            # Bad request - re-raise as-is
            logger.error(f"LiteLLM bad request error: {e}")
            raise
        except NotFoundError as e:
            # Model not found - re-raise as-is
            logger.error(f"LiteLLM not found error: {e}")
            raise
        except APIConnectionError as e:
            # Connection error - re-raise as-is
            logger.error(f"LiteLLM connection error: {e}")
            raise
        except (InternalServerError, ServiceUnavailableError) as e:
            # Server errors - re-raise as-is
            logger.error(f"LiteLLM server error: {e}")
            raise
        except Exception as e:
            # Unexpected error - log and re-raise
            logger.error(f"Unexpected LiteLLM error: {type(e).__name__}: {e}")
            raise

    async def agenerate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Async version of generate_content using litellm.acompletion."""
        try:
            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Extract timeout if provided by tools
            timeout = kwargs.pop("timeout", None)

            # Extract images if provided
            images = kwargs.pop("images", None)
            if images:
                # LiteLLM expects images in the message content
                user_message = messages[-1]
                user_message["content"] = [
                    {"type": "text", "text": prompt},
                ]
                for image in images:
                    if image.startswith("data:") or image.startswith("http"):
                        # URL or base64 data URI
                        user_message["content"].append({"type": "image_url", "image_url": {"url": image}})
                    else:
                        # File path - read and convert to base64
                        import base64

                        with open(image, "rb") as f:
                            img_data = base64.b64encode(f.read()).decode()
                            user_message["content"].append(
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_data}"}}
                            )

            # Build completion kwargs
            completion_kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
            }

            # Add optional parameters
            if max_output_tokens:
                completion_kwargs["max_tokens"] = max_output_tokens

            if timeout:
                completion_kwargs["timeout"] = timeout

            # Add any additional kwargs
            for key, value in kwargs.items():
                if value is not None:
                    completion_kwargs[key] = value

            # Call LiteLLM async
            response = await acompletion(**completion_kwargs)

            # Extract response content
            content = response.choices[0].message.content

            # Build usage dict
            usage = {}
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "input_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "output_tokens": getattr(response.usage, "completion_tokens", 0),
                    "total_tokens": getattr(response.usage, "total_tokens", 0),
                }

            # Return in expected format
            return ModelResponse(
                content=content,
                usage=usage,
                model_name=model_name,
                friendly_name=self.FRIENDLY_NAME,
                provider=self.get_provider_type(),
                metadata={
                    "litellm_model_id": getattr(response, "id", None),
                    "litellm_model": getattr(response, "model", model_name),
                },
            )

        except Exception as e:
            # Same exception handling as sync version
            logger.error(f"Async LiteLLM error: {type(e).__name__}: {e}")
            raise
