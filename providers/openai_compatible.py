"""Base class for OpenAI-compatible API providers."""

import base64
import ipaddress
import logging
import os
import threading
import time
from abc import abstractmethod
from typing import Optional
from urllib.parse import urlparse

from openai import OpenAI, AsyncOpenAI

from .base import (
    ModelCapabilities,
    ModelProvider,
    ModelResponse,
    ProviderType,
)


class OpenAICompatibleProvider(ModelProvider):
    """Base class for any provider using an OpenAI-compatible API.

    This includes:
    - Direct OpenAI API
    - OpenRouter
    - Any other OpenAI-compatible endpoint
    """

    DEFAULT_HEADERS = {}
    FRIENDLY_NAME = "OpenAI Compatible"

    def __init__(self, api_key: str, base_url: str = None, **kwargs):
        """Initialize the provider with API key and optional base URL.

        Args:
            api_key: API key for authentication
            base_url: Base URL for the API endpoint
            **kwargs: Additional configuration options including timeout
        """
        super().__init__(api_key, **kwargs)
        self._client = None
        self._async_client = None
        self._client_lock = threading.Lock()  # Thread-safe lazy initialization
        self._async_client_lock = None  # Will be initialized as asyncio.Lock when needed
        self.base_url = base_url
        self.organization = kwargs.get("organization")
        self.allowed_models = self._parse_allowed_models()

        # Configure timeouts - especially important for custom/local endpoints
        self.timeout_config = self._configure_timeouts(**kwargs)

        # Validate base URL for security
        if self.base_url:
            self._validate_base_url()

        # Warn if using external URL without authentication
        if self.base_url and not self._is_localhost_url() and not api_key:
            logging.warning(
                f"Using external URL '{self.base_url}' without API key. "
                "This may be insecure. Consider setting an API key for authentication."
            )

    def _parse_allowed_models(self) -> Optional[set[str]]:
        """Parse allowed models from environment variable.

        Returns:
            Set of allowed model names (lowercase) or None if not configured
        """
        # Get provider-specific allowed models
        provider_type = self.get_provider_type().value.upper()
        env_var = f"{provider_type}_ALLOWED_MODELS"
        models_str = os.getenv(env_var, "")

        if models_str:
            # Parse and normalize to lowercase for case-insensitive comparison
            models = {m.strip().lower() for m in models_str.split(",") if m.strip()}
            if models:
                logging.info(f"Configured allowed models for {self.FRIENDLY_NAME}: {sorted(models)}")
                return models

        # Log info if no allow-list configured for proxy providers
        if self.get_provider_type() not in [ProviderType.GOOGLE, ProviderType.OPENAI]:
            logging.info(
                f"Model allow-list not configured for {self.FRIENDLY_NAME} - all models permitted. "
                f"To restrict access, set {env_var} with comma-separated model names."
            )

        return None

    def _configure_timeouts(self, **kwargs):
        """Configure timeout settings based on provider type and custom settings.

        Custom URLs and local models often need longer timeouts due to:
        - Network latency on local networks
        - Extended thinking models taking longer to respond
        - Local inference being slower than cloud APIs

        Returns:
            httpx.Timeout object with appropriate timeout settings
        """
        import httpx

        # Default timeouts - more generous for custom/local endpoints
        default_connect = 30.0  # 30 seconds for connection (vs OpenAI's 5s)
        default_read = 600.0  # 10 minutes for reading (same as OpenAI default)
        default_write = 600.0  # 10 minutes for writing
        default_pool = 600.0  # 10 minutes for pool

        # For custom/local URLs, use even longer timeouts
        if self.base_url and self._is_localhost_url():
            default_connect = 60.0  # 1 minute for local connections
            default_read = 1800.0  # 30 minutes for local models (extended thinking)
            default_write = 1800.0  # 30 minutes for local models
            default_pool = 1800.0  # 30 minutes for local models
            logging.info(f"Using extended timeouts for local endpoint: {self.base_url}")
        elif self.base_url:
            default_connect = 45.0  # 45 seconds for custom remote endpoints
            default_read = 900.0  # 15 minutes for custom remote endpoints
            default_write = 900.0  # 15 minutes for custom remote endpoints
            default_pool = 900.0  # 15 minutes for custom remote endpoints
            logging.info(f"Using extended timeouts for custom endpoint: {self.base_url}")

        # Allow override via kwargs or environment variables in future, for now...
        connect_timeout = kwargs.get("connect_timeout", float(os.getenv("CUSTOM_CONNECT_TIMEOUT", default_connect)))
        read_timeout = kwargs.get("read_timeout", float(os.getenv("CUSTOM_READ_TIMEOUT", default_read)))
        write_timeout = kwargs.get("write_timeout", float(os.getenv("CUSTOM_WRITE_TIMEOUT", default_write)))
        pool_timeout = kwargs.get("pool_timeout", float(os.getenv("CUSTOM_POOL_TIMEOUT", default_pool)))

        timeout = httpx.Timeout(connect=connect_timeout, read=read_timeout, write=write_timeout, pool=pool_timeout)

        logging.debug(
            f"Configured timeouts - Connect: {connect_timeout}s, Read: {read_timeout}s, "
            f"Write: {write_timeout}s, Pool: {pool_timeout}s"
        )

        return timeout

    def _is_localhost_url(self) -> bool:
        """Check if the base URL points to localhost or local network.

        Returns:
            True if URL is localhost or local network, False otherwise
        """
        if not self.base_url:
            return False

        try:
            parsed = urlparse(self.base_url)
            hostname = parsed.hostname

            # Check for common localhost patterns
            if hostname in ["localhost", "127.0.0.1", "::1"]:
                return True

            # Check for private network ranges (local network)
            if hostname:
                try:
                    ip = ipaddress.ip_address(hostname)
                    return ip.is_private or ip.is_loopback
                except ValueError:
                    # Not an IP address, might be a hostname
                    pass

            return False
        except Exception:
            return False

    def _validate_base_url(self) -> None:
        """Validate base URL for security (SSRF protection).

        Raises:
            ValueError: If URL is invalid or potentially unsafe
        """
        if not self.base_url:
            return

        try:
            parsed = urlparse(self.base_url)

            # Check URL scheme - only allow http/https
            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"Invalid URL scheme: {parsed.scheme}. Only http/https allowed.")

            # Check hostname exists
            if not parsed.hostname:
                raise ValueError("URL must include a hostname")

            # Check port is valid (if specified)
            port = parsed.port
            if port is not None and (port < 1 or port > 65535):
                raise ValueError(f"Invalid port number: {port}. Must be between 1 and 65535.")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Invalid base URL '{self.base_url}': {str(e)}")

    @property
    def client(self):
        """Lazy and thread-safe initialization of OpenAI client with security checks and timeout configuration."""
        if self._client is not None:
            return self._client

        with self._client_lock:
            # Double-check in case another thread initialized it while we waited for the lock
            if self._client is not None:
                return self._client
            import os

            import httpx

            # Temporarily disable proxy environment variables to prevent httpx from detecting them
            original_env = {}
            proxy_env_vars = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]

            for var in proxy_env_vars:
                if var in os.environ:
                    original_env[var] = os.environ[var]
                    del os.environ[var]

            try:
                # Create a custom httpx client that explicitly avoids proxy parameters
                timeout_config = (
                    self.timeout_config
                    if hasattr(self, "timeout_config") and self.timeout_config
                    else httpx.Timeout(300.0)  # 5 minutes default for o3-pro and other long-running models
                )

                # Create httpx client with minimal config to avoid proxy conflicts
                # Note: proxies parameter was removed in httpx 0.28.0
                #
                # CRITICAL: Disable all connection pooling to prevent deadlocks
                # The issue appears to be resource exhaustion in connection pools.
                # By setting max_connections=1 and disabling keepalive, we force
                # each request to use a new connection, preventing pool exhaustion.
                #
                # This is less efficient but prevents the consistent deadlock pattern
                # we see on the 5th call (2 models) or 3rd call (4 models).
                
                # Configure httpx to disable connection pooling entirely
                limits = httpx.Limits(
                    max_connections=1,  # Only 1 connection at a time
                    max_keepalive_connections=0,  # No keepalive
                    keepalive_expiry=0.0,  # Disable keepalive
                )
                
                # Create a minimal httpx client with no connection pooling
                http_client = httpx.Client(
                    timeout=timeout_config,
                    limits=limits,
                    follow_redirects=True,
                    headers={"Connection": "close"},  # Force connection closure
                    trust_env=False,  # Disable proxy detection
                    http1=True,  # Use HTTP/1.1 only
                    http2=False,  # Disable HTTP/2
                )

                # Keep client initialization minimal to avoid proxy parameter conflicts
                client_kwargs = {
                    "api_key": self.api_key,
                    "http_client": http_client,
                }

                if self.base_url:
                    client_kwargs["base_url"] = self.base_url

                if self.organization:
                    client_kwargs["organization"] = self.organization

                # Add default headers if any
                if self.DEFAULT_HEADERS:
                    client_kwargs["default_headers"] = self.DEFAULT_HEADERS.copy()

                logging.info(
                    f"Creating OpenAI client with custom httpx config - "
                    f"max_connections={limits.max_connections}, "
                    f"keepalive={limits.max_keepalive_connections}, "
                    f"timeout={timeout_config}"
                )

                # Create OpenAI client with custom httpx client
                self._client = OpenAI(**client_kwargs)
                
                logging.info("Successfully created OpenAI client with connection pooling disabled")

            except Exception as e:
                # CRITICAL: The custom httpx client is ESSENTIAL to prevent deadlocks
                # when running in an asyncio event loop via to_thread. Falling back
                # to the default client is known to cause hangs.
                logging.error(
                    "CRITICAL: Failed to create OpenAI client with custom httpx configuration. "
                    "This will likely lead to deadlocks in consensus tool. "
                    "Error: %s",
                    e,
                    exc_info=True  # Log the full traceback for debugging
                )
                # Re-raising the exception is safer than continuing with a known-bad configuration.
                # The provider will fail to initialize, but this is better than a production deadlock.
                raise RuntimeError(
                    "Failed to initialize a deadlock-safe HTTP client for OpenAI provider. "
                    "The custom httpx client configuration is required to prevent asyncio deadlocks."
                ) from e
            finally:
                # Restore original proxy environment variables
                for var, value in original_env.items():
                    os.environ[var] = value

        return self._client

    async def _get_async_client(self) -> AsyncOpenAI:
        """
        Initializes and returns the async client, ensuring thread-safe
        initialization in async context.
        """
        if self._async_client is not None:
            return self._async_client

        # Create async lock on first use
        if self._async_client_lock is None:
            import asyncio
            self._async_client_lock = asyncio.Lock()

        async with self._async_client_lock:
            # Double-check pattern for async safety
            if self._async_client is not None:
                return self._async_client

            try:
                import httpx
                
                # Create the same connection limits for async client to prevent pool exhaustion
                limits = httpx.Limits(
                    max_connections=1,  # Only 1 connection at a time
                    max_keepalive_connections=0,  # No keepalive
                    keepalive_expiry=0.0,  # Disable keepalive
                )
                
                # Create custom async httpx client with same restrictions as sync
                async_http_client = httpx.AsyncClient(
                    timeout=self.timeout_config,
                    limits=limits,
                    follow_redirects=True,
                    headers={"Connection": "close"},  # Force connection closure
                    trust_env=False,  # Disable proxy detection
                    http1=True,  # Use HTTP/1.1 only
                    http2=False,  # Disable HTTP/2
                )
                
                client_kwargs = {
                    "api_key": self.api_key,
                    "http_client": async_http_client,
                }

                if self.base_url:
                    client_kwargs["base_url"] = self.base_url

                if self.organization:
                    client_kwargs["organization"] = self.organization

                if self.DEFAULT_HEADERS:
                    client_kwargs["default_headers"] = self.DEFAULT_HEADERS.copy()

                logging.info(
                    f"Creating AsyncOpenAI client with connection pooling disabled - "
                    f"max_connections={limits.max_connections}, "
                    f"keepalive={limits.max_keepalive_connections}"
                )

                # Create AsyncOpenAI client
                self._async_client = AsyncOpenAI(**client_kwargs)
                
                logging.info("Successfully created AsyncOpenAI client for async operations")

            except Exception as e:
                logging.error(
                    "Failed to create AsyncOpenAI client: %s",
                    e,
                    exc_info=True
                )
                raise RuntimeError(
                    "Failed to initialize AsyncOpenAI client"
                ) from e

        return self._async_client

    async def aclose(self):
        """Close the async client if it was initialized."""
        if self._async_client:
            await self._async_client.close()
            self._async_client = None
            logging.info("Closed AsyncOpenAI client")

    def _safe_extract_output_text(self, response) -> str:
        """Safely extract output text from o3-pro response with validation.

        The o3-pro response has an output array containing ResponseOutputMessage items
        with ResponseOutputText content.
        """
        content = ""

        # Check if response has output array (actual o3-pro format)
        if hasattr(response, "output") and response.output:
            # Iterate through output items
            for output_item in response.output:
                # Look for message type outputs
                if hasattr(output_item, "type") and output_item.type == "message":
                    # Check if it has content
                    if hasattr(output_item, "content") and output_item.content:
                        # Extract text from content items
                        for content_item in output_item.content:
                            if hasattr(content_item, "type") and content_item.type == "output_text":
                                if hasattr(content_item, "text"):
                                    content = content_item.text
                                    logging.debug(f"Extracted from output message content: {len(content)} chars")
                                    break
                if content:
                    break

        # Fallback: check for direct output_text field
        if not content and hasattr(response, "output_text") and response.output_text:
            content = response.output_text
            logging.debug(f"Extracted output_text directly: {len(content)} chars")

        if not content:
            logging.warning("No output text found in response")

        return content

    def _generate_with_responses_endpoint(
        self,
        model_name: str,
        messages: list,
        temperature: float,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using the /v1/responses endpoint for o3-pro via OpenAI library.

        Note: o3-pro can take several minutes to process complex requests, so we need
        to ensure the client has appropriate timeout settings.
        """
        # Convert messages to simple format for o3-pro responses endpoint
        # The responses API expects a simple input string, not a messages array

        # Extract system message as instructions if present
        instructions = None
        input_text = ""

        for message in messages:
            role = message.get("role", "")
            content = message.get("content", "")

            if role == "system" and not instructions:
                # Use first system message as instructions
                instructions = content
            elif role == "user":
                # Concatenate user messages as input
                if input_text:
                    input_text += "\n"
                input_text += content
            elif role == "assistant":
                # Include assistant context if present
                if input_text:
                    input_text += f"\nAssistant: {content}\nUser: "

        # Extract request-specific timeout from kwargs
        request_timeout = kwargs.pop("timeout", None)

        # Prepare completion parameters for responses endpoint
        # Based on OpenAI documentation examples
        completion_params = {
            "model": model_name,
            "input": input_text.strip(),
            "reasoning": {"effort": "high"},  # Use high effort for o3-pro
        }

        # Add timeout if provided (for consensus and other tools that need faster failure)
        if request_timeout:
            completion_params["timeout"] = request_timeout

        # Add instructions if we have them
        if instructions:
            completion_params["instructions"] = instructions

        # The responses endpoint doesn't support max_completion_tokens parameter
        # We'll log it but not include it in the request
        if max_output_tokens:
            logging.debug(f"max_output_tokens {max_output_tokens} requested but not supported by responses endpoint")

        # For responses endpoint, we only add parameters that are explicitly supported
        # Remove unsupported chat completion parameters that may cause API errors

        # Retry logic with progressive delays
        max_retries = 4
        retry_delays = [1, 3, 5, 8]
        last_exception = None

        for attempt in range(max_retries):
            try:  # Log the exact payload being sent for debugging
                import json

                logging.info(
                    f"o3-pro API request payload: {json.dumps(completion_params, indent=2, ensure_ascii=False)}"
                )

                # Use OpenAI client's responses endpoint
                response = self.client.responses.create(**completion_params)

                # Log the raw response for debugging
                logging.info(f"o3-pro raw response type: {type(response)}")
                logging.info(f"o3-pro raw response: {response}")

                # Log response attributes
                if hasattr(response, "__dict__"):
                    logging.info(f"o3-pro response attributes: {list(response.__dict__.keys())}")

                # Extract content and usage from responses endpoint format
                # The response format is different for responses endpoint
                content = self._safe_extract_output_text(response)

                # Try to extract usage information
                usage = None
                if hasattr(response, "usage"):
                    usage = self._extract_usage(response)
                elif hasattr(response, "input_tokens") and hasattr(response, "output_tokens"):
                    # Safely extract token counts with None handling
                    input_tokens = getattr(response, "input_tokens", 0) or 0
                    output_tokens = getattr(response, "output_tokens", 0) or 0
                    usage = {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    }

                return ModelResponse(
                    content=content,
                    usage=usage,
                    model_name=model_name,
                    friendly_name=self.FRIENDLY_NAME,
                    provider=self.get_provider_type(),
                    metadata={
                        "model": getattr(response, "model", model_name),
                        "id": getattr(response, "id", ""),
                        "created": getattr(response, "created_at", 0),
                        "endpoint": "responses",
                    },
                )

            except Exception as e:
                last_exception = e

                # Check if this is a retryable error using structured error codes
                is_retryable = self._is_error_retryable(e)

                if is_retryable and attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logging.warning(
                        f"Retryable error for o3-pro responses endpoint, attempt {attempt + 1}/{max_retries}: {str(e)}. Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    break

        # If we get here, all retries failed
        actual_attempts = attempt + 1  # Convert from 0-based index to human-readable count
        error_msg = f"o3-pro responses endpoint error after {actual_attempts} attempt{'s' if actual_attempts > 1 else ''}: {str(last_exception)}"
        logging.error(error_msg)
        raise RuntimeError(error_msg) from last_exception

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
        images: Optional[list[str]] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using the OpenAI-compatible API.

        Args:
            prompt: User prompt to send to the model
            model_name: Name of the model to use
            system_prompt: Optional system prompt for model behavior
            temperature: Sampling temperature
            max_output_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            ModelResponse with generated content and metadata
        """
        # Validate model name against allow-list
        if not self.validate_model_name(model_name):
            raise ValueError(f"Model '{model_name}' not in allowed models list. Allowed models: {self.allowed_models}")

        # Get effective temperature for this model
        effective_temperature = self.get_effective_temperature(model_name, temperature)

        # Only validate if temperature is not None (meaning the model supports it)
        if effective_temperature is not None:
            # Validate parameters with the effective temperature
            self.validate_parameters(model_name, effective_temperature)

        # Prepare messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Prepare user message with text and potentially images
        user_content = []
        user_content.append({"type": "text", "text": prompt})

        # Add images if provided and model supports vision
        if images and self._supports_vision(model_name):
            for image_path in images:
                try:
                    image_content = self._process_image(image_path)
                    if image_content:
                        user_content.append(image_content)
                except Exception as e:
                    logging.warning(f"Failed to process image {image_path}: {e}")
                    # Continue with other images and text
                    continue
        elif images and not self._supports_vision(model_name):
            logging.warning(f"Model {model_name} does not support images, ignoring {len(images)} image(s)")

        # Add user message
        if len(user_content) == 1:
            # Only text content, use simple string format for compatibility
            messages.append({"role": "user", "content": prompt})
        else:
            # Text + images, use content array format
            messages.append({"role": "user", "content": user_content})

        # Extract request-specific timeout from kwargs
        request_timeout = kwargs.pop("timeout", None)

        # Prepare completion parameters
        completion_params = {
            "model": model_name,
            "messages": messages,
        }

        # Add timeout if provided (for consensus and other tools that need faster failure)
        if request_timeout:
            completion_params["timeout"] = request_timeout

        # Check model capabilities once to determine parameter support
        resolved_model = self._resolve_model_name(model_name)

        # Use the effective temperature we calculated earlier
        if effective_temperature is not None:
            completion_params["temperature"] = effective_temperature
            supports_temperature = True
        else:
            # Model doesn't support temperature
            supports_temperature = False

        # Add max tokens if specified and model supports it
        # O3/O4 models that don't support temperature also don't support max_tokens
        if max_output_tokens and supports_temperature:
            completion_params["max_tokens"] = max_output_tokens

        # Add any additional OpenAI-specific parameters
        # Use capabilities to filter parameters for reasoning models
        for key, value in kwargs.items():
            if key in ["top_p", "frequency_penalty", "presence_penalty", "seed", "stop", "stream"]:
                # Reasoning models (those that don't support temperature) also don't support these parameters
                if not supports_temperature and key in ["top_p", "frequency_penalty", "presence_penalty"]:
                    continue  # Skip unsupported parameters for reasoning models
                completion_params[key] = value

        # Check if this is o3-pro or o3-deep-research and needs the responses endpoint
        if resolved_model in ["o3-pro-2025-06-10", "o3-deep-research-2025-06-26"]:
            # These models require the /v1/responses endpoint
            # If it fails, we should not fall back to chat/completions
            return self._generate_with_responses_endpoint(
                model_name=resolved_model,
                messages=messages,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                **kwargs,
            )

        # DEADLOCK_DEBUG: Log the actual payload size
        import json
        payload_json = json.dumps(completion_params)
        payload_size = len(payload_json)
        logging.warning(f"[DEADLOCK_DEBUG] OpenAI API request size: {payload_size:,} chars (~{payload_size//4:,} tokens)")
        logging.warning(f"[DEADLOCK_DEBUG] Messages: {len(messages)} messages, prompt length: {len(prompt):,} chars")
        
        # Retry logic with progressive delays
        max_retries = 4  # Total of 4 attempts
        retry_delays = [1, 3, 5, 8]  # Progressive delays: 1s, 3s, 5s, 8s

        last_exception = None

        for attempt in range(max_retries):
            try:
                # Generate completion
                response = self.client.chat.completions.create(**completion_params)

                # Extract content and usage
                content = response.choices[0].message.content
                usage = self._extract_usage(response)

                return ModelResponse(
                    content=content,
                    usage=usage,
                    model_name=model_name,
                    friendly_name=self.FRIENDLY_NAME,
                    provider=self.get_provider_type(),
                    metadata={
                        "finish_reason": response.choices[0].finish_reason,
                        "model": response.model,  # Actual model used
                        "id": response.id,
                        "created": response.created,
                    },
                )

            except Exception as e:
                last_exception = e

                # Check if this is a retryable error using structured error codes
                is_retryable = self._is_error_retryable(e)

                # If this is the last attempt or not retryable, give up
                if attempt == max_retries - 1 or not is_retryable:
                    break

                # Get progressive delay
                delay = retry_delays[attempt]

                # Log retry attempt
                logging.warning(
                    f"{self.FRIENDLY_NAME} error for model {model_name}, attempt {attempt + 1}/{max_retries}: {str(e)}. Retrying in {delay}s..."
                )
                time.sleep(delay)

        # If we get here, all retries failed
        actual_attempts = attempt + 1  # Convert from 0-based index to human-readable count
        error_msg = f"{self.FRIENDLY_NAME} API error for model {model_name} after {actual_attempts} attempt{'s' if actual_attempts > 1 else ''}: {str(last_exception)}"
        logging.error(error_msg)
        raise RuntimeError(error_msg) from last_exception

    async def agenerate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
        images: Optional[list[str]] = None,
        **kwargs,
    ) -> ModelResponse:
        """Async version using native AsyncOpenAI client.
        
        This avoids all the threading and deadlock issues by using the async client directly.
        """
        # Handle o3-pro models differently - they use /v1/responses endpoint
        if model_name.startswith("o3-pro"):
            return await self._agenerate_o3_pro_response(
                prompt=prompt,
                model_name=model_name,
                system_prompt=system_prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                images=images,
                **kwargs,
            )

        # Standard chat completions for all other models
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Build user message with potential images
        user_content = []
        user_content.append({"type": "text", "text": prompt})

        # Add images if provided and model supports vision
        if images and self._supports_vision(model_name):
            for image_path in images:
                try:
                    image_content = self._process_image(image_path)
                    if image_content:
                        user_content.append(image_content)
                except Exception as e:
                    logging.warning(f"Failed to process image {image_path}: {e}")
                    continue
        elif images and not self._supports_vision(model_name):
            logging.warning(f"Model {model_name} does not support images, ignoring {len(images)} image(s)")

        # Add user message
        if len(user_content) == 1:
            messages.append({"role": "user", "content": user_content[0]["text"]})
        else:
            messages.append({"role": "user", "content": user_content})

        # Build completion parameters
        completion_params = {
            "model": model_name,
            "messages": messages,
        }

        # Handle temperature based on model support
        effective_temperature = self.get_effective_temperature(model_name, temperature)
        if effective_temperature is not None:
            completion_params["temperature"] = effective_temperature
            supports_temperature = True
        else:
            supports_temperature = False
        
        # Handle thinking mode for supported models
        reasoning_effort = kwargs.get("reasoning_effort", "medium")
        if self.supports_thinking_mode(model_name):
            completion_params["reasoning_effort"] = reasoning_effort

        # Add max tokens if specified and model supports it
        # O3/O4 models that don't support temperature also don't support max_tokens
        if max_output_tokens and supports_temperature:
            completion_params["max_tokens"] = max_output_tokens

        # Get timeout from kwargs or use model-specific timeout
        timeout = kwargs.get("timeout")

        # Check if this is o3-pro or o3-deep-research and needs the responses endpoint
        resolved_model = self._resolve_model_name(model_name)
        if resolved_model in ["o3-pro-2025-06-10", "o3-deep-research-2025-06-26"]:
            # These models require the /v1/responses endpoint
            return await self._agenerate_o3_pro_response(
                prompt=prompt,
                model_name=resolved_model,
                system_prompt=system_prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                images=images,
                **kwargs,
            )

        # Use async client for the API call
        try:
            client = await self._get_async_client()
            response = await client.chat.completions.create(**completion_params)

            # Extract content and usage
            content = response.choices[0].message.content
            usage = self._extract_usage(response)

            return ModelResponse(
                content=content,
                usage=usage,
                model_name=model_name,
                friendly_name=self.FRIENDLY_NAME,
                provider=self.get_provider_type(),
                metadata={
                    "finish_reason": response.choices[0].finish_reason,
                    "model": response.model,  # Actual model used
                    "id": response.id,
                    "created": response.created,
                },
            )

        except Exception as e:
            error_msg = f"{self.FRIENDLY_NAME} async API error for model {model_name}: {str(e)}"
            logging.error(error_msg)
            raise RuntimeError(error_msg) from e

    async def _agenerate_o3_pro_response(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
        images: Optional[list[str]] = None,
        **kwargs,
    ) -> ModelResponse:
        """Async version of o3-pro response generation."""
        # Build the simplified request for /v1/responses endpoint
        completion_params = {
            "model": model_name,
            "input": prompt,
        }

        if system_prompt:
            completion_params["instructions"] = system_prompt

        # o3-pro models use reasoning_effort instead of temperature
        reasoning_effort = kwargs.get("reasoning_effort", "high")
        completion_params["reasoning_effort"] = reasoning_effort

        try:
            # Use async client's responses endpoint
            client = await self._get_async_client()
            response = await client.responses.create(**completion_params)

            # Extract content from o3-pro response
            content = self._safe_extract_output_text(response)

            # Extract usage information
            usage = {}
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "input_tokens": getattr(response.usage, "input_tokens", 0) or 0,
                    "output_tokens": getattr(response.usage, "output_tokens", 0) or 0,
                    "total_tokens": getattr(response.usage, "total_tokens", 0) or 0,
                }
            elif hasattr(response, "input_tokens") and hasattr(response, "output_tokens"):
                input_tokens = getattr(response, "input_tokens", 0) or 0
                output_tokens = getattr(response, "output_tokens", 0) or 0
                usage = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                }

            return ModelResponse(
                content=content,
                usage=usage,
                model_name=model_name,
                friendly_name=self.FRIENDLY_NAME,
                provider=self.get_provider_type(),
                metadata={
                    "model": getattr(response, "model", model_name),
                    "id": getattr(response, "id", ""),
                    "created": getattr(response, "created_at", 0),
                    "endpoint": "responses",
                },
            )

        except Exception as e:
            error_msg = f"o3-pro async API error: {str(e)}"
            logging.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e

    def count_tokens(self, text: str, model_name: str) -> int:
        """Count tokens for the given text.

        Uses a layered approach:
        1. Try provider-specific token counting endpoint
        2. Try tiktoken for known model families
        3. Fall back to character-based estimation

        Args:
            text: Text to count tokens for
            model_name: Model name for tokenizer selection

        Returns:
            Estimated token count
        """
        # 1. Check if provider has a remote token counting endpoint
        if hasattr(self, "count_tokens_remote"):
            try:
                return self.count_tokens_remote(text, model_name)
            except Exception as e:
                logging.debug(f"Remote token counting failed: {e}")

        # 2. Try tiktoken for known models
        try:
            import tiktoken

            # Try to get encoding for the specific model
            try:
                encoding = tiktoken.encoding_for_model(model_name)
            except KeyError:
                # Try common encodings based on model patterns
                if "gpt-4" in model_name or "gpt-3.5" in model_name:
                    encoding = tiktoken.get_encoding("cl100k_base")
                else:
                    encoding = tiktoken.get_encoding("cl100k_base")  # Default

            return len(encoding.encode(text))

        except (ImportError, Exception) as e:
            logging.debug(f"Tiktoken not available or failed: {e}")

        # 3. Fall back to character-based estimation
        logging.warning(
            f"No specific tokenizer available for '{model_name}'. "
            "Using character-based estimation (~4 chars per token)."
        )
        return len(text) // 4

    def validate_parameters(self, model_name: str, temperature: float, **kwargs) -> None:
        """Validate model parameters.

        For proxy providers, this may use generic capabilities.

        Args:
            model_name: Model to validate for
            temperature: Temperature to validate
            **kwargs: Additional parameters to validate
        """
        try:
            capabilities = self.get_capabilities(model_name)

            # Check if we're using generic capabilities
            if hasattr(capabilities, "_is_generic"):
                logging.debug(
                    f"Using generic parameter validation for {model_name}. Actual model constraints may differ."
                )

            # Validate temperature using parent class method
            super().validate_parameters(model_name, temperature, **kwargs)

        except Exception as e:
            # For proxy providers, we might not have accurate capabilities
            # Log warning but don't fail
            logging.warning(f"Parameter validation limited for {model_name}: {e}")

    def _extract_usage(self, response) -> dict[str, int]:
        """Extract token usage from OpenAI response.

        Args:
            response: OpenAI API response object

        Returns:
            Dictionary with usage statistics
        """
        usage = {}

        if hasattr(response, "usage") and response.usage:
            # Safely extract token counts with None handling
            usage["input_tokens"] = getattr(response.usage, "prompt_tokens", 0) or 0
            usage["output_tokens"] = getattr(response.usage, "completion_tokens", 0) or 0
            usage["total_tokens"] = getattr(response.usage, "total_tokens", 0) or 0

        return usage

    @abstractmethod
    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get capabilities for a specific model.

        Must be implemented by subclasses.
        """
        pass

    @abstractmethod
    def get_provider_type(self) -> ProviderType:
        """Get the provider type.

        Must be implemented by subclasses.
        """
        pass

    @abstractmethod
    def validate_model_name(self, model_name: str) -> bool:
        """Validate if the model name is supported.

        Must be implemented by subclasses.
        """
        pass

    def supports_thinking_mode(self, model_name: str) -> bool:
        """Check if the model supports extended thinking mode.

        Default is False for OpenAI-compatible providers.
        """
        return False

    def _supports_vision(self, model_name: str) -> bool:
        """Check if the model supports vision (image processing).

        Default implementation for OpenAI-compatible providers.
        Subclasses should override with specific model support.
        """
        # Common vision-capable models - only include models that actually support images
        vision_models = {
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4-vision-preview",
            "gpt-4.1-2025-04-14",  # GPT-4.1 supports vision
            "o3",
            "o3-mini",
            "o3-pro",
            "o4-mini",
            # Note: Claude models would be handled by a separate provider
        }
        supports = model_name.lower() in vision_models
        logging.debug(f"Model '{model_name}' vision support: {supports}")
        return supports

    def _is_error_retryable(self, error: Exception) -> bool:
        """Determine if an error should be retried based on structured error codes.

        Uses OpenAI API error structure instead of text pattern matching for reliability.

        Args:
            error: Exception from OpenAI API call

        Returns:
            True if error should be retried, False otherwise
        """
        error_str = str(error).lower()

        # Check for 429 errors first - these need special handling
        if "429" in error_str:
            # Try to extract structured error information
            error_type = None
            error_code = None

            # Parse structured error from OpenAI API response
            # Format: "Error code: 429 - {'error': {'type': 'tokens', 'code': 'rate_limit_exceeded', ...}}"
            try:
                import ast
                import json
                import re

                # Extract JSON part from error string using regex
                # Look for pattern: {...} (from first { to last })
                json_match = re.search(r"\{.*\}", str(error))
                if json_match:
                    json_like_str = json_match.group(0)

                    # First try: parse as Python literal (handles single quotes safely)
                    try:
                        error_data = ast.literal_eval(json_like_str)
                    except (ValueError, SyntaxError):
                        # Fallback: try JSON parsing with simple quote replacement
                        # (for cases where it's already valid JSON or simple replacements work)
                        json_str = json_like_str.replace("'", '"')
                        error_data = json.loads(json_str)

                    if "error" in error_data:
                        error_info = error_data["error"]
                        error_type = error_info.get("type")
                        error_code = error_info.get("code")

            except (json.JSONDecodeError, ValueError, SyntaxError, AttributeError):
                # Fall back to checking hasattr for OpenAI SDK exception objects
                if hasattr(error, "response") and hasattr(error.response, "json"):
                    try:
                        response_data = error.response.json()
                        if "error" in response_data:
                            error_info = response_data["error"]
                            error_type = error_info.get("type")
                            error_code = error_info.get("code")
                    except Exception:
                        pass

            # Determine if 429 is retryable based on structured error codes
            if error_type == "tokens":
                # Token-related 429s are typically non-retryable (request too large)
                logging.debug(f"Non-retryable 429: token-related error (type={error_type}, code={error_code})")
                return False
            elif error_code in ["invalid_request_error", "context_length_exceeded"]:
                # These are permanent failures
                logging.debug(f"Non-retryable 429: permanent failure (type={error_type}, code={error_code})")
                return False
            else:
                # Other 429s (like requests per minute) are retryable
                logging.debug(f"Retryable 429: rate limiting (type={error_type}, code={error_code})")
                return True

        # For non-429 errors, check if they're retryable
        # Note: We exclude "timeout" and "408" from retries to prevent infinite retry loops
        # on hanging requests. HTTP timeouts suggest the server is unresponsive and
        # retrying will likely hang again for the same duration.
        retryable_indicators = [
            "connection",  # Connection errors (network issues)
            "network",  # Network errors
            "temporary",  # Temporary failures
            "unavailable",  # Service temporarily unavailable
            "retry",  # Explicit retry suggestions
            "500",  # Internal server error
            "502",  # Bad gateway
            "503",  # Service unavailable
            "504",  # Gateway timeout (server-side timeout, different from read timeout)
            "ssl",  # SSL errors
            "handshake",  # Handshake failures
        ]

        # Explicitly exclude HTTP read timeouts from retries
        # These suggest the server is hanging and retrying will likely hang again
        non_retryable_indicators = [
            "read timeout",
            "timeout error",
            "408",  # Request timeout
            "httpx.readtimeout",
            "httpx.connecttimeout",
        ]

        # Don't retry if it's a timeout-related error
        if any(indicator in error_str for indicator in non_retryable_indicators):
            return False

        return any(indicator in error_str for indicator in retryable_indicators)

    def _process_image(self, image_path: str) -> Optional[dict]:
        """Process an image for OpenAI-compatible API."""
        try:
            if image_path.startswith("data:image/"):
                # Handle data URL: data:image/png;base64,iVBORw0...
                return {"type": "image_url", "image_url": {"url": image_path}}
            else:
                # Handle file path
                if not os.path.exists(image_path):
                    logging.warning(f"Image file not found: {image_path}")
                    return None

                # Detect MIME type from file extension using centralized mappings
                from utils.file_types import get_image_mime_type

                ext = os.path.splitext(image_path)[1].lower()
                mime_type = get_image_mime_type(ext)
                logging.debug(f"Processing image '{image_path}' with extension '{ext}' as MIME type '{mime_type}'")

                # Read and encode the image
                with open(image_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode()

                # Create data URL for OpenAI API
                data_url = f"data:{mime_type};base64,{image_data}"

                return {"type": "image_url", "image_url": {"url": data_url}}
        except Exception as e:
            logging.error(f"Error processing image {image_path}: {e}")
            return None

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None:
            try:
                # Get the http_client from the OpenAI client
                if hasattr(self._client, "_client") and hasattr(self._client._client, "close"):
                    self._client._client.close()
                elif hasattr(self._client, "close"):
                    self._client.close()
            except Exception as e:
                logging.debug(f"Error closing OpenAI client: {e}")
            finally:
                self._client = None
