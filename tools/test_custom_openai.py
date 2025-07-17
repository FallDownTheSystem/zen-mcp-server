"""Test tool for CustomOpenAI provider with 150k character payload."""

import logging
from typing import Any, Dict, List, Optional

from providers.custom_openai import CustomOpenAI
from tools.simple.base import SimpleTool

logger = logging.getLogger(__name__)


class TestCustomOpenAITool(SimpleTool):
    """Test tool that uses CustomOpenAI provider with a large payload."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model_cache = {}

    def get_name(self) -> str:
        return "test_custom_openai"

    def get_description(self) -> str:
        return "Test tool that uses CustomOpenAI provider with a 150k character payload to test deadlock issues."

    def get_tool_fields(self) -> Dict[str, Dict[str, Any]]:
        return {}  # No parameters needed

    def get_required_fields(self) -> List[str]:
        return []  # No required fields

    def supports_auto_mode(self) -> bool:
        return False  # Don't support auto mode

    def is_effective_auto_mode(self) -> bool:
        return False  # Force manual mode

    def get_model_field_schema(self) -> Dict[str, Any]:
        return {
            "type": "string",
            "enum": ["o3-mini"],
            "default": "o3-mini",
            "description": "Fixed to o3-mini for testing"
        }

    async def prepare_prompt(self, request) -> str:
        """Prepare a prompt with ~150k characters of content."""
        # Generate ~150k characters of content
        base_text = "This is a test message to create a large payload for testing the CustomOpenAI provider. "
        base_length = len(base_text)
        
        # Calculate how many repetitions we need for ~150k characters
        target_length = 150000
        repetitions = target_length // base_length
        
        # Create the large payload
        large_payload = base_text * repetitions
        
        # Add some padding to get closer to 150k
        padding_needed = target_length - len(large_payload)
        if padding_needed > 0:
            large_payload += "X" * padding_needed
        
        # Add a question at the end
        prompt = f"""{large_payload}

Given the above repetitive text, please respond with a simple acknowledgment that you received the message and can see it contains repetitive content. Keep your response brief (under 100 words).
"""
        
        logger.info(f"Generated prompt with {len(prompt):,} characters")
        return prompt

    def get_system_prompt(self) -> str:
        return """You are a test assistant. You will receive a large message with repetitive content. 
Simply acknowledge that you received it and can see the repetitive pattern. Keep your response brief."""

    def format_response(self, response: str, request, model_info: Optional[dict] = None) -> str:
        """Format the response with test information."""
        prompt_length = len(getattr(self, '_last_prompt', ''))
        
        formatted = f"""=== CustomOpenAI Test Results ===

Model: o3-mini
Prompt Length: {prompt_length:,} characters
Response Length: {len(response):,} characters

Response:
{response}

=== Test Status ===
✅ Successfully processed large payload without deadlock
✅ CustomOpenAI provider handled {prompt_length:,} characters
"""
        return formatted

    async def execute(self, arguments: Dict[str, Any]) -> List:
        """Execute the test with CustomOpenAI provider."""
        import os
        from mcp.types import TextContent
        from tools.models import ToolOutput
        
        try:
            # Get OpenAI API key from environment
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                error_output = ToolOutput(
                    status="error",
                    content="OPENAI_API_KEY environment variable not set",
                    content_type="text"
                )
                return [TextContent(type="text", text=error_output.model_dump_json())]
            
            # Create CustomOpenAI provider instance
            provider = CustomOpenAI(api_key=api_key)
            
            # Generate the large prompt
            prompt = await self.prepare_prompt(None)
            self._last_prompt = prompt
            
            # Get system prompt
            system_prompt = self.get_system_prompt()
            
            logger.info(f"Testing CustomOpenAI provider with {len(prompt):,} character prompt")
            
            # Test the provider directly
            try:
                import time
                start_time = time.time()
                
                response = provider.generate_content(
                    prompt=prompt,
                    model_name="o3-mini",
                    system_prompt=system_prompt,
                    temperature=1.0
                )
                
                end_time = time.time()
                response_time = end_time - start_time
                
                logger.info(f"CustomOpenAI provider completed in {response_time:.2f}s")
                
                # Format the response
                formatted_response = self.format_response(response.content, None, {
                    "provider": provider,
                    "model_name": "o3-mini",
                    "response_time": response_time
                })
                
                # Create success output
                success_output = ToolOutput(
                    status="success",
                    content=formatted_response,
                    content_type="text",
                    metadata={
                        "prompt_length": len(prompt),
                        "response_length": len(response.content),
                        "response_time": response_time,
                        "provider": "CustomOpenAI",
                        "model": "o3-mini",
                        "tokens_used": response.usage
                    }
                )
                
                return [TextContent(type="text", text=success_output.model_dump_json())]
                
            except Exception as e:
                logger.error(f"CustomOpenAI provider error: {e}")
                error_output = ToolOutput(
                    status="error",
                    content=f"CustomOpenAI provider failed: {str(e)}",
                    content_type="text",
                    metadata={
                        "prompt_length": len(prompt),
                        "error_type": type(e).__name__
                    }
                )
                return [TextContent(type="text", text=error_output.model_dump_json())]
                
        except Exception as e:
            logger.error(f"Test execution error: {e}")
            error_output = ToolOutput(
                status="error",
                content=f"Test execution failed: {str(e)}",
                content_type="text"
            )
            return [TextContent(type="text", text=error_output.model_dump_json())]