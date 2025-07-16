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

    def _find_yaml_file(self, filename: str) -> Optional[str]:
        """Find a YAML file using multiple fallback approaches.

        This method tries different approaches to find YAML files:
        1. Using importlib.resources (modern approach for installed packages)
        2. Using relative paths (for development)
        3. Using package data approaches

        Args:
            filename: Name of the YAML file to find

        Returns:
            Path to the file if found, None otherwise
        """
        from pathlib import Path

        logger.debug(f"Looking for YAML file: {filename}")

        # Approach 1: Try importlib.resources (Python 3.9+)
        try:
            if hasattr(__import__("importlib"), "resources"):
                import importlib.resources as resources

                # Try different package name variations
                package_names = ["zen-mcp-server", "zen_mcp_server", "zen-mcp-server-0.1.0"]
                for pkg_name in package_names:
                    try:
                        logger.debug(f"Trying importlib.resources with package: {pkg_name}")
                        ref = resources.files(pkg_name) / filename
                        if ref.is_file():
                            logger.debug(f"Found {filename} using importlib.resources with package {pkg_name}")
                            return str(ref)
                    except Exception as e:
                        logger.debug(f"Failed to find {filename} with package {pkg_name}: {e}")
                        continue

                try:
                    # Try to find the file in the current package
                    ref = resources.files(__package__.split(".")[0]) / filename
                    if ref.is_file():
                        return str(ref)
                except Exception:
                    pass
        except Exception:
            pass

        # Approach 2: Try pkg_resources (legacy approach) - only if importlib.resources fails
        try:
            import pkg_resources

            # Try different package name variations
            package_names = ["zen-mcp-server", "zen_mcp_server", "zen-mcp-server-0.1.0"]
            for pkg_name in package_names:
                try:
                    filepath = pkg_resources.resource_filename(pkg_name, filename)
                    if Path(filepath).exists():
                        return filepath
                except Exception:
                    continue
        except (ImportError, UserWarning):
            # pkg_resources is deprecated, but we'll keep it as a fallback
            pass

        # Approach 3: Try relative paths (for development)
        try:
            # Current approach - relative to this file
            relative_path = Path(__file__).parent.parent / filename
            if relative_path.exists():
                return str(relative_path)
        except Exception:
            pass

        # Approach 4: Try current working directory
        try:
            cwd_path = Path.cwd() / filename
            if cwd_path.exists():
                return str(cwd_path)
        except Exception:
            pass

        # Approach 5: Try common installation locations
        try:
            import sys

            for path in sys.path:
                if path:
                    potential_path = Path(path) / filename
                    if potential_path.exists():
                        return str(potential_path)
        except Exception:
            pass

        logger.warning(f"Could not find {filename} in any of the expected locations")
        return None

    def __init__(self, **kwargs):
        """Initialize the LiteLLM provider.

        Args:
            **kwargs: Additional configuration options
        """
        # No API key needed - LiteLLM will use environment variables
        super().__init__(api_key="", **kwargs)

        # Load LiteLLM config if available
        config_path = self._find_yaml_file("litellm_config.yaml")
        if config_path:
            os.environ["LITELLM_CONFIG_PATH"] = str(config_path)
            logger.info(f"Set LITELLM_CONFIG_PATH to {config_path}")
        else:
            logger.warning("litellm_config.yaml not found, LiteLLM will use default configuration")

        # Enable drop_params globally to handle model-specific restrictions
        litellm.drop_params = True

        # Set timeout configuration to prevent hanging
        # These will be used as defaults if not specified in the request
        litellm.request_timeout = 600  # 10 minutes default
        litellm.connect_timeout = 30  # 30 seconds to establish connection

        # Also set environment variables for some providers that use them
        os.environ["LITELLM_REQUEST_TIMEOUT"] = "600"
        os.environ["LITELLM_CONNECT_TIMEOUT"] = "30"

        # Get model metadata (if provided, or load from file)
        self.model_metadata = kwargs.get("model_metadata", {})

        # If no model metadata provided, try to load it from the YAML file
        if not self.model_metadata:
            metadata_path = self._find_yaml_file("model_metadata.yaml")
            if metadata_path:
                try:
                    import yaml

                    with open(metadata_path) as f:
                        metadata = yaml.safe_load(f)
                        if metadata and "models" in metadata:
                            self.model_metadata = metadata["models"]
                            logger.debug(f"Loaded model metadata for {len(self.model_metadata)} models")
                except Exception as e:
                    logger.warning(f"Failed to load model metadata from {metadata_path}: {e}")
            else:
                logger.warning("model_metadata.yaml not found, model capabilities will use defaults")

        # Configure observability callbacks
        self._configure_observability()

        # Build model alias mapping
        self.model_alias_map = self._build_alias_map()

    def _build_alias_map(self) -> dict[str, str]:
        """Build a mapping of model aliases to actual model names from litellm_config.yaml."""
        alias_map = {}

        config_path = self._find_yaml_file("litellm_config.yaml")
        if config_path:
            try:
                import yaml

                with open(config_path) as f:
                    config = yaml.safe_load(f)
                    if config and "model_list" in config:
                        for model_config in config["model_list"]:
                            model_name = model_config.get("model_name")
                            if not model_name:
                                continue

                            # Get the actual model path from litellm_params
                            litellm_params = model_config.get("litellm_params", {})
                            actual_model = litellm_params.get("model")
                            if not actual_model:
                                continue

                            # Map model_name to actual model path
                            # Only add if they're different (model_name is an alias)
                            if model_name != actual_model:
                                alias_map[model_name] = actual_model

                            # Also map any additional aliases
                            aliases = model_config.get("model_alias", [])
                            if isinstance(aliases, list):
                                for alias in aliases:
                                    alias_map[alias] = actual_model
                            elif isinstance(aliases, str):
                                alias_map[aliases] = actual_model

                logger.debug(f"Built alias map with {len(alias_map)} aliases")
            except Exception as e:
                logger.warning(f"Failed to build alias map from {config_path}: {e}")

        return alias_map

    def _resolve_model_alias(self, model_name: str) -> str:
        """Resolve a model alias to the actual model name.

        Args:
            model_name: The model name or alias to resolve

        Returns:
            The actual model name to use with LiteLLM
        """
        # Check if it's an alias
        if model_name in self.model_alias_map:
            resolved = self.model_alias_map[model_name]
            logger.debug(f"Resolved model alias '{model_name}' to '{resolved}'")
            return resolved

        # Not an alias, return as-is
        return model_name

    def _configure_observability(self):
        """Configure LiteLLM observability callbacks."""
        try:
            # TEMPORARILY DISABLED TO TEST HANGING ISSUE
            logger.warning("OBSERVABILITY TEMPORARILY DISABLED FOR DEBUGGING")
            return

            # Check if observability is enabled
            enable_observability = os.getenv("OBSERVABILITY_ENABLED", "true").lower() == "true"

            if enable_observability:
                from observability.callbacks import configure_litellm_callbacks

                configure_litellm_callbacks(enable_observability=True)
                logger.info("LiteLLM observability callbacks configured")
            else:
                logger.info("LiteLLM observability callbacks disabled")

        except Exception as e:
            logger.warning(f"Failed to configure observability callbacks: {e}")
            # Don't fail initialization if observability setup fails

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
        # Resolve any aliases first
        resolved_model = self._resolve_model_alias(model_name)

        # Check if we have metadata for this model (try both alias and resolved name)
        metadata = None
        if model_name in self.model_metadata:
            metadata = self.model_metadata[model_name]
        elif resolved_model in self.model_metadata:
            # Check the resolved model name in metadata
            metadata = self.model_metadata[resolved_model]
            # Also check just the model name without provider prefix
            # e.g., "gemini/gemini-2.5-pro" -> "gemini-2.5-pro"
        elif "/" in resolved_model:
            base_model = resolved_model.split("/", 1)[1]
            if base_model in self.model_metadata:
                metadata = self.model_metadata[base_model]

        if metadata:
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
        # Resolve any aliases first
        resolved_model = self._resolve_model_alias(model_name)

        # Check metadata with same logic as get_capabilities
        if model_name in self.model_metadata:
            return self.model_metadata[model_name].get("supports_extended_thinking", False)
        elif resolved_model in self.model_metadata:
            return self.model_metadata[resolved_model].get("supports_extended_thinking", False)
        elif "/" in resolved_model:
            base_model = resolved_model.split("/", 1)[1]
            if base_model in self.model_metadata:
                return self.model_metadata[base_model].get("supports_extended_thinking", False)

        # Check for known thinking models
        return "o3" in model_name.lower() or "o4" in model_name.lower()

    def count_tokens(self, text: str, model_name: str) -> int:
        """Count tokens for the given text.

        Uses LiteLLM's token counting functionality.
        """
        try:
            # Resolve model alias to actual model name
            resolved_model = self._resolve_model_alias(model_name)
            # LiteLLM provides token counting
            return litellm.token_counter(model=resolved_model, text=text)
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

            # Resolve model alias to actual model name
            resolved_model = self._resolve_model_alias(model_name)

            # Build completion kwargs
            completion_kwargs = {
                "model": resolved_model,
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

            # Add additional_drop_params for XAI models to handle reasoning_effort
            if "xai/" in resolved_model.lower() or "grok" in resolved_model.lower():
                completion_kwargs["additional_drop_params"] = ["reasoning_effort"]
                logger.debug(f"Added additional_drop_params for XAI model {resolved_model}")

            # Call LiteLLM
            response = completion(**completion_kwargs)

            # Handle streaming response (not fully implemented, convert to regular response)
            if hasattr(response, "__iter__") and not hasattr(response, "choices"):
                # This is a streaming response - consume it and convert to regular response
                logger.warning(
                    f"Streaming requested but not fully implemented for model {model_name}, converting to regular response"
                )
                content_chunks = []
                for chunk in response:
                    if hasattr(chunk, "choices") and chunk.choices:
                        if hasattr(chunk.choices[0], "delta") and hasattr(chunk.choices[0].delta, "content"):
                            if chunk.choices[0].delta.content:
                                content_chunks.append(chunk.choices[0].delta.content)
                content = "".join(content_chunks)

                # For streaming, we don't have usage info typically
                usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

                # Return early for streaming
                return ModelResponse(
                    content=content,
                    usage=usage,
                    model_name=model_name,
                    friendly_name=self.FRIENDLY_NAME,
                    provider=self.get_provider_type(),
                    metadata={"streaming": True},
                )

            # Extract response content
            content = response.choices[0].message.content

            # Debug: Log the response structure if content is None
            if content is None:
                logger.warning(f"LiteLLM response content is None for model {model_name}")
                logger.debug(f"Full response: {response}")
                logger.debug(f"Message: {response.choices[0].message}")

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

            # Resolve model alias to actual model name
            resolved_model = self._resolve_model_alias(model_name)

            # Build completion kwargs
            completion_kwargs = {
                "model": resolved_model,
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

    def list_models(self, respect_restrictions: bool = True) -> list[str]:
        """Return a list of model names available through LiteLLM.

        This reads models from the model_metadata.yaml file which contains
        all models configured for use with LiteLLM, and also includes
        model aliases from litellm_config.yaml.

        Args:
            respect_restrictions: Whether to apply model restrictions

        Returns:
            List of model names available through LiteLLM
        """
        import yaml

        from utils.model_restrictions import get_restriction_service

        models = []

        # Load model metadata to get list of available models
        metadata_path = self._find_yaml_file("model_metadata.yaml")
        if metadata_path:
            try:
                with open(metadata_path) as f:
                    metadata = yaml.safe_load(f)
                    if metadata and "models" in metadata:
                        models = list(metadata["models"].keys())
                        logger.debug(f"Loaded {len(models)} models from model_metadata.yaml")
            except Exception as e:
                logger.warning(f"Failed to load model metadata from {metadata_path}: {e}")
        else:
            logger.warning("model_metadata.yaml not found, falling back to default model list")

        # Also load aliases from litellm_config.yaml
        config_path = self._find_yaml_file("litellm_config.yaml")
        if config_path:
            try:
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                    if config and "model_list" in config:
                        for model_config in config["model_list"]:
                            # Add the main model name if not already present
                            model_name = model_config.get("model_name")
                            if model_name and model_name not in models:
                                models.append(model_name)

                            # Add any aliases (model_alias is at top level, not in litellm_params)
                            aliases = model_config.get("model_alias", [])
                            if isinstance(aliases, list):
                                for alias in aliases:
                                    if alias not in models:
                                        models.append(alias)
                            elif isinstance(aliases, str) and aliases not in models:
                                models.append(aliases)
                        logger.debug(f"Loaded additional models/aliases from litellm_config.yaml, total: {len(models)}")
            except Exception as e:
                logger.warning(f"Failed to load litellm config from {config_path}: {e}")
        else:
            logger.warning("litellm_config.yaml not found, using model_metadata.yaml only")

        # If no models were loaded, fall back to a default list
        if not models:
            logger.warning("No models loaded from YAML files, using fallback list")
            models = [
                "o3",
                "o3-mini",
                "o3-pro",
                "o3-deep-research",
                "o4-mini",
                "gpt-4.1-2025-04-14",
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-2.0-flash",
                "gemini-2.0-flash-lite",
                "grok-3",
                "grok-3-fast",
                "grok-4-0709",
            ]

        # Apply restrictions if requested
        if respect_restrictions:
            restriction_service = get_restriction_service()
            filtered_models = []
            for model in models:
                if restriction_service.is_allowed(self.get_provider_type(), model):
                    filtered_models.append(model)
            models = filtered_models
            logger.debug(f"After applying restrictions: {len(models)} models available")

        return models

    def get_observability_stats(self):
        """Get observability statistics from the callback handler."""
        try:
            # Find the ZenObservabilityHandler in the callbacks
            for callback in litellm.callbacks:
                if hasattr(callback, "get_stats"):
                    return callback.get_stats()
            return {"error": "No observability handler found"}
        except Exception as e:
            logger.warning(f"Failed to get observability stats: {e}")
            return {"error": str(e)}
