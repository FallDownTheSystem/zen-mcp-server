# Adding Tools to Zen MCP Server

This guide explains how to add new tools to the Zen MCP Server. Tools enable Claude to interact with AI models for specialized tasks.

## Tool Architecture

Zen uses a simplified tool architecture:

### Simple Tools
- **Pattern**: Single request → AI response → formatted output
- **Use cases**: Chat, consensus gathering, any AI-powered task
- **Benefits**: Clean, lightweight, easy to implement
- **Base class**: `SimpleTool` (`tools/simple/base.py`)

All tools in the simplified Zen MCP Server inherit from `SimpleTool`, which provides:
- Automatic conversation memory management
- File handling and deduplication
- Model resolution and validation
- Consistent response formatting

## Implementation Guide

### Simple Tool Example

```python
from tools.simple.base import SimpleTool
from tools.shared.base_models import ToolRequest
from pydantic import Field

class ChatTool(SimpleTool):
    def get_name(self) -> str:
        return "chat"
    
    def get_description(self) -> str:
        return "GENERAL CHAT & COLLABORATIVE THINKING..."
    
    def get_tool_fields(self) -> dict:
        return {
            "prompt": {
                "type": "string", 
                "description": "Your question or idea..."
            },
            "files": SimpleTool.FILES_FIELD  # Reuse common field
        }
    
    def get_required_fields(self) -> list[str]:
        return ["prompt"]
    
    async def prepare_prompt(self, request) -> str:
        return self.prepare_chat_style_prompt(request)
```

### Creating a Custom Request Model (Optional)

For tools with specific requirements, you can create a custom request model:

```python
from tools.shared.base_models import ToolRequest
from pydantic import Field

class ConsensusRequest(ToolRequest):
    """Request model for consensus tool"""
    
    prompt: str = Field(..., description="The question to gather consensus on")
    models: list[dict] = Field(..., description="List of models to consult")
    enable_cross_feedback: bool = Field(default=True, description="Enable refinement phase")
    
class ConsensusTool(SimpleTool):
    def get_request_model(self):
        return ConsensusRequest
```

## Key Implementation Points

### Required Methods
- `get_name()`: Tool identifier used in MCP calls
- `get_description()`: Brief description for tool selection
- `get_tool_fields()`: Define input fields and their types
- `get_required_fields()`: List fields that must be provided
- `prepare_prompt()` or `execute()`: Process the request

### Optional Methods
- `get_request_model()`: Use custom Pydantic model for validation
- `format_response()`: Custom response formatting
- `get_system_prompt()`: Override default system prompt
- `get_model_category()`: Specify model requirements

### Registration
1. Create system prompt in `systemprompts/`
2. Import in `server.py` 
3. Add to `TOOLS` dictionary

## Testing Your Tool

### Simulator Tests (Recommended)
The most important validation is adding your tool to the simulator test suite:

```python
# Add to communication_simulator_test.py
def test_your_tool_validation(self):
    """Test your new tool with real API calls"""
    response = self.call_tool("your_tool", {
        "prompt": "Test the tool functionality",
        "model": "flash"
    })
    
    # Validate response structure and content
    self.assertIn("status", response)
    self.assertEqual(response["status"], "success")
```

**Why simulator tests matter:**
- Test actual MCP communication with Claude
- Validate real AI model interactions  
- Catch integration issues unit tests miss
- Ensure proper conversation threading
- Verify file handling and deduplication

### Running Tests
```bash
# Test your specific tool
python communication_simulator_test.py --individual your_tool_validation

# Quick comprehensive test
python communication_simulator_test.py --quick
```

## Examples to Study

- **Chat Tool** (`tools/chat.py`): Simple conversational AI with file support
- **Consensus Tool** (`tools/consensus.py`): Advanced parallel processing with custom execute() method

### Chat Tool Pattern
Best for tools that:
- Process a single prompt
- Return AI-generated content
- Support file context
- Use standard request/response flow

### Consensus Tool Pattern  
Best for tools that:
- Need custom execution logic
- Make multiple AI calls
- Process results before returning
- Implement complex workflows in a single call

## Best Practices

1. **Keep descriptions concise**: Tool descriptions should be brief (60-80 words) to preserve context
2. **Use execute() for complex logic**: Override execute() instead of prepare_prompt() for advanced tools
3. **Leverage base functionality**: SimpleTool provides file handling, conversation memory, and model validation
4. **Test with simulator**: Always add simulator tests to validate real MCP communication
5. **Follow existing patterns**: Study the two included tools to understand implementation approaches

