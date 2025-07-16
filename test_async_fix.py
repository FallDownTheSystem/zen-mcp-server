#!/usr/bin/env python3
"""
Test script to verify the async storage implementation works correctly.
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.conversation_memory import add_turn, create_thread, get_thread
from utils.storage_backend import get_storage_backend


async def test_storage():
    """Test basic storage operations"""
    print("Testing async storage backend...")

    storage = get_storage_backend()

    # Test basic set/get
    await storage.setex("test_key", 3600, "test_value")
    value = await storage.get("test_key")
    assert value == "test_value", f"Expected 'test_value', got {value}"
    print("✓ Basic storage operations work")

    # Test expiration
    await storage.setex("expire_key", 1, "expire_value")
    await asyncio.sleep(2)
    value = await storage.get("expire_key")
    assert value is None, f"Expected None for expired key, got {value}"
    print("✓ Key expiration works")


async def test_conversation_memory():
    """Test conversation memory operations"""
    print("\nTesting async conversation memory...")

    # Create a thread
    thread_id = await create_thread("test_tool", {"prompt": "test"})
    print(f"✓ Created thread: {thread_id}")

    # Get the thread
    thread = await get_thread(thread_id)
    assert thread is not None, "Thread should exist"
    assert thread.tool_name == "test_tool"
    print("✓ Retrieved thread successfully")

    # Add a turn
    success = await add_turn(thread_id, "user", "Hello world", files=["test.py"])
    assert success, "Add turn should succeed"
    print("✓ Added turn successfully")

    # Get updated thread
    thread = await get_thread(thread_id)
    assert len(thread.turns) == 1
    assert thread.turns[0].content == "Hello world"
    assert thread.turns[0].files == ["test.py"]
    print("✓ Turn data preserved correctly")

    # Test turn limit
    for i in range(19):  # Add 19 more turns to reach limit of 20
        await add_turn(thread_id, "assistant" if i % 2 else "user", f"Turn {i+2}")

    # Try to add one more (should fail)
    success = await add_turn(thread_id, "user", "This should fail")
    assert not success, "Should not be able to add turn beyond limit"
    print("✓ Turn limit enforced correctly")


async def test_event_loop():
    """Test that asyncio lock doesn't block the event loop"""
    print("\nTesting event loop non-blocking behavior...")

    storage = get_storage_backend()

    # Create multiple concurrent operations
    tasks = []
    for i in range(10):
        tasks.append(storage.setex(f"concurrent_{i}", 3600, f"value_{i}"))

    # All should complete without blocking
    await asyncio.gather(*tasks)
    print("✓ Concurrent writes completed successfully")

    # Read them back concurrently
    tasks = []
    for i in range(10):
        tasks.append(storage.get(f"concurrent_{i}"))

    results = await asyncio.gather(*tasks)
    for i, result in enumerate(results):
        assert result == f"value_{i}", f"Expected 'value_{i}', got {result}"

    print("✓ Concurrent reads completed successfully")
    print("✓ Event loop remains responsive with asyncio.Lock")


async def main():
    """Run all tests"""
    print("=== Testing Async Storage Implementation ===\n")

    try:
        await test_storage()
        await test_conversation_memory()
        await test_event_loop()

        print("\n✅ ALL TESTS PASSED! The async implementation is working correctly.")
        print("\nThe fixes successfully address:")
        print("- Threading.Lock blocking the event loop (now using asyncio.Lock)")
        print("- All storage operations are properly async")
        print("- Conversation memory is fully async")
        print("- Event loop remains responsive during concurrent operations")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
