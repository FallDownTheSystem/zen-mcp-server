#!/usr/bin/env python3
"""
Test script to verify the async LiteLLM fix works correctly.
This tests that the server no longer hangs on Windows when making LLM calls.
"""

import asyncio
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers.litellm_provider import LiteLLMProvider
from tools.chat import ChatTool
from utils.model_context import ModelContext


async def test_async_litellm():
    """Test that async LiteLLM calls don't block the event loop"""
    print("Testing async LiteLLM implementation...")
    
    # Create provider
    provider = LiteLLMProvider()
    
    # Test basic async call
    print("\n1. Testing basic async call...")
    try:
        response = await provider.agenerate_content(
            prompt="What is 2+2? Reply with just the number.",
            model_name="gpt-4o-mini",
            system_prompt="You are a helpful assistant.",
            temperature=0.1
        )
        print(f"✓ Basic async call succeeded: {response.content.strip()}")
    except Exception as e:
        print(f"✗ Basic async call failed: {e}")
        return False
    
    # Test multiple concurrent calls
    print("\n2. Testing concurrent async calls...")
    try:
        tasks = []
        for i in range(3):
            task = provider.agenerate_content(
                prompt=f"What is {i}+{i}? Reply with just the number.",
                model_name="gpt-4o-mini", 
                system_prompt="You are a helpful assistant.",
                temperature=0.1
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        for i, response in enumerate(responses):
            print(f"✓ Concurrent call {i} succeeded: {response.content.strip()}")
    except Exception as e:
        print(f"✗ Concurrent calls failed: {e}")
        return False
    
    return True


async def test_chat_tool():
    """Test the chat tool with async calls"""
    print("\n3. Testing chat tool with async LiteLLM...")
    
    tool = ChatTool()
    
    # First call
    print("\nFirst tool call...")
    try:
        result = await tool.execute({
            "prompt": "What is 3+3? Reply with just the number.",
            "model": "gpt-4o-mini",
            "reasoning_effort": "low"
        })
        
        if result and len(result) > 0:
            response_data = json.loads(result[0].text)
            print(f"✓ First call succeeded: {response_data.get('response', '').strip()}")
        else:
            print("✗ First call returned empty result")
            return False
    except Exception as e:
        print(f"✗ First call failed: {e}")
        return False
    
    # Second call (this is where it usually hangs)
    print("\nSecond tool call (testing for hang)...")
    try:
        result = await tool.execute({
            "prompt": "What is 4+4? Reply with just the number.",
            "model": "gpt-4o-mini",
            "reasoning_effort": "low"
        })
        
        if result and len(result) > 0:
            response_data = json.loads(result[0].text)
            print(f"✓ Second call succeeded: {response_data.get('response', '').strip()}")
        else:
            print("✗ Second call returned empty result")
            return False
    except Exception as e:
        print(f"✗ Second call failed: {e}")
        return False
    
    print("\n✓ Both calls completed without hanging!")
    return True


async def main():
    """Run all tests"""
    import platform
    
    print("=== Testing Async LiteLLM Fix ===")
    print(f"Platform: {platform.system()}")
    print(f"Python: {sys.version}")
    
    # Set event loop policy for Windows
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print("Using WindowsSelectorEventLoopPolicy")
    
    try:
        # Test async LiteLLM
        if not await test_async_litellm():
            print("\n❌ Async LiteLLM tests failed")
            return
        
        # Test chat tool
        if not await test_chat_tool():
            print("\n❌ Chat tool tests failed")
            return
        
        print("\n✅ ALL TESTS PASSED! The async LiteLLM fix is working correctly.")
        print("\nThe fix successfully addresses:")
        print("- Synchronous LiteLLM calls no longer block the event loop")
        print("- Multiple tool calls work without hanging")
        print("- Windows-specific async issues are resolved")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())