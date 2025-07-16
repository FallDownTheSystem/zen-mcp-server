"""
Response chunking utility for large MCP responses.

This module provides utilities to chunk large responses to prevent
stdout buffer overflow issues on Windows.
"""

import json
import logging
from typing import Any, List

from mcp.types import TextContent

logger = logging.getLogger(__name__)

# Maximum size for a single response chunk (in characters)
# Set conservatively to avoid Windows pipe buffer issues
MAX_CHUNK_SIZE = 32768  # 32KB


def chunk_text_response(text: str, chunk_size: int = MAX_CHUNK_SIZE) -> List[TextContent]:
    """
    Split a large text response into multiple smaller TextContent chunks.
    
    This helps prevent stdout buffer overflow on Windows when sending
    large responses through the MCP protocol.
    
    Args:
        text: The text to chunk
        chunk_size: Maximum size of each chunk in characters
        
    Returns:
        List of TextContent objects, each containing a chunk
    """
    if len(text) <= chunk_size:
        # No chunking needed
        return [TextContent(type="text", text=text)]
    
    chunks = []
    total_chunks = (len(text) + chunk_size - 1) // chunk_size
    
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        chunk_num = i // chunk_size + 1
        
        # Add chunk metadata for reassembly
        if total_chunks > 1:
            chunk_prefix = f"[CHUNK {chunk_num}/{total_chunks}]\n"
            chunk = chunk_prefix + chunk
            
        chunks.append(TextContent(type="text", text=chunk))
    
    logger.debug(f"Split response into {len(chunks)} chunks")
    return chunks


def should_chunk_response(content: Any) -> bool:
    """
    Determine if a response should be chunked.
    
    Args:
        content: The response content
        
    Returns:
        True if the response should be chunked
    """
    # Only chunk on Windows
    import platform
    if platform.system() != "Windows":
        return False
    
    # Check if content is large enough to warrant chunking
    if isinstance(content, str):
        return len(content) > MAX_CHUNK_SIZE
    elif isinstance(content, dict):
        # Estimate JSON size
        try:
            json_str = json.dumps(content, ensure_ascii=False)
            return len(json_str) > MAX_CHUNK_SIZE
        except Exception:
            return False
    
    return False


def create_chunked_response(content: Any) -> List[TextContent]:
    """
    Create a potentially chunked response from content.
    
    Args:
        content: The content to send (string or dict)
        
    Returns:
        List of TextContent objects
    """
    if isinstance(content, dict):
        # Convert to JSON first
        text = json.dumps(content, indent=2, ensure_ascii=False)
    else:
        text = str(content)
    
    if should_chunk_response(text):
        return chunk_text_response(text)
    else:
        return [TextContent(type="text", text=text)]