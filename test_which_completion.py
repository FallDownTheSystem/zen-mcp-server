#!/usr/bin/env python3
"""
Test to verify which completion method is actually being called
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Monkey patch to track which method is called
original_completion = None
original_acompletion = None
completion_calls = []
acompletion_calls = []

def track_completion(*args, **kwargs):
    completion_calls.append("sync completion called")
    print("!!! SYNC completion() called !!!")
    return original_completion(*args, **kwargs)

async def track_acompletion(*args, **kwargs):
    acompletion_calls.append("async acompletion called")
    print("!!! ASYNC acompletion() called !!!")
    return await original_acompletion(*args, **kwargs)

# Apply monkey patch
import litellm

original_completion = litellm.completion
original_acompletion = litellm.acompletion
litellm.completion = track_completion
litellm.acompletion = track_acompletion

from providers.litellm_provider import LiteLLMProvider


async def test_provider_methods():
    """Test which methods the provider actually calls"""
    provider = LiteLLMProvider()

    print("\n=== Testing generate_content (sync method) ===")
    try:
        # This should call completion()
        response = provider.generate_content(
            prompt="Say 'sync'",
            model_name="gpt-4o-mini",
            temperature=0.1
        )
        print(f"Response: {response.content}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n=== Testing agenerate_content (async method) ===")
    try:
        # This should call acompletion()
        response = await provider.agenerate_content(
            prompt="Say 'async'",
            model_name="gpt-4o-mini",
            temperature=0.1
        )
        print(f"Response: {response.content}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n=== Summary ===")
    print(f"Sync completion() calls: {len(completion_calls)}")
    print(f"Async acompletion() calls: {len(acompletion_calls)}")


async def main():
    import platform

    print("=== Testing Which Completion Method is Called ===")
    print(f"Platform: {platform.system()}")

    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    await test_provider_methods()


if __name__ == "__main__":
    asyncio.run(main())
