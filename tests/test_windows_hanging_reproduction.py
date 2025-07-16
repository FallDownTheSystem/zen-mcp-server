#!/usr/bin/env python3
"""
Integration test to reproduce Windows hanging issue.

This test makes real API calls through the MCP server, including
continuations, to reproduce the race condition/deadlock that causes
the server to hang after 2-3 requests.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.types import TextContent

from server import Server, handle_call_tool, initialize_server

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def make_tool_call(server: Server, tool_name: str, arguments: dict, iteration: int):
    """Make a single tool call and return the result."""
    logger.info(f"[Iteration {iteration}] Making {tool_name} call with continuation_id: {arguments.get('continuation_id', 'None')}")

    try:
        result = await handle_call_tool(tool_name, arguments)

        # Extract text content
        if result and isinstance(result, list) and len(result) > 0:
            if isinstance(result[0], TextContent):
                text_result = result[0].text
                logger.info(f"[Iteration {iteration}] Got response of length: {len(text_result)}")

                # Parse JSON if possible to extract continuation_id
                try:
                    json_result = json.loads(text_result)
                    if "continuation_offer" in json_result:
                        continuation_id = json_result["continuation_offer"].get("continuation_id")
                        logger.info(f"[Iteration {iteration}] Got continuation_id: {continuation_id}")
                        return continuation_id, json_result
                except json.JSONDecodeError:
                    pass

                return None, text_result

        logger.warning(f"[Iteration {iteration}] Unexpected result format: {type(result)}")
        return None, result

    except Exception as e:
        logger.error(f"[Iteration {iteration}] Error in tool call: {e}", exc_info=True)
        raise


async def test_repeated_calls_with_continuations():
    """Test making repeated tool calls with continuations to reproduce hanging."""

    # Initialize server
    server = Server("test-server")
    await initialize_server(server)

    # Test configuration
    num_iterations = 10
    tools_to_test = [
        {
            "name": "chat",
            "initial_args": {
                "prompt": "Write a Python function to calculate fibonacci numbers. Be concise.",
                "model": "gpt-4o-mini",
                "temperature": 0.3
            },
            "continuation_prompt": "Now optimize the function for better performance. Be concise."
        },
        {
            "name": "consensus",
            "initial_args": {
                "prompt": "Should we use async/await or threads for concurrent operations in Python? Be concise.",
                "models": [
                    {"model": "gpt-4o-mini"},
                    {"model": "gemini-flash"}
                ],
                "enable_cross_feedback": False,  # Disable to make it faster
                "temperature": 0.3
            },
            "continuation_prompt": "What about for I/O bound vs CPU bound tasks? Be concise."
        }
    ]

    # Test each tool
    for tool_config in tools_to_test:
        tool_name = tool_config["name"]
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing {tool_name} tool with {num_iterations} iterations")
        logger.info(f"{'='*60}\n")

        continuation_id = None

        for i in range(num_iterations):
            try:
                # Prepare arguments
                if i == 0:
                    # First call - no continuation
                    args = tool_config["initial_args"].copy()
                else:
                    # Subsequent calls - use continuation
                    args = tool_config["initial_args"].copy()
                    args["prompt"] = tool_config["continuation_prompt"]
                    if continuation_id:
                        args["continuation_id"] = continuation_id

                # Make the call
                logger.info(f"\n[Iteration {i+1}/{num_iterations}] Starting {tool_name} call...")
                start_time = asyncio.get_event_loop().time()

                new_continuation_id, result = await make_tool_call(server, tool_name, args, i+1)

                elapsed = asyncio.get_event_loop().time() - start_time
                logger.info(f"[Iteration {i+1}/{num_iterations}] Completed in {elapsed:.2f}s")

                # Update continuation_id if we got a new one
                if new_continuation_id:
                    continuation_id = new_continuation_id

                # Small delay between calls to avoid overwhelming
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"[Iteration {i+1}/{num_iterations}] Failed: {e}")
                logger.error(f"Server might be hanging at iteration {i+1}")
                raise

        logger.info(f"\n{'='*60}")
        logger.info(f"Successfully completed {num_iterations} iterations of {tool_name}")
        logger.info(f"{'='*60}\n")

        # Delay between different tools
        await asyncio.sleep(2)

    logger.info("\nAll tests completed successfully!")


async def test_parallel_calls():
    """Test making parallel calls to stress test the server."""

    # Initialize server
    server = Server("test-server")
    await initialize_server(server)

    logger.info("\n" + "="*60)
    logger.info("Testing parallel calls")
    logger.info("="*60 + "\n")

    # Create multiple concurrent tasks
    async def make_chat_call(task_id: int):
        args = {
            "prompt": f"Task {task_id}: Count from 1 to 5. Be very concise.",
            "model": "gpt-4o-mini",
            "temperature": 0.1
        }
        logger.info(f"[Task {task_id}] Starting parallel call")
        _, result = await make_tool_call(server, "chat", args, task_id)
        logger.info(f"[Task {task_id}] Completed parallel call")
        return result

    # Launch 5 parallel tasks
    tasks = [make_chat_call(i) for i in range(5)]

    try:
        results = await asyncio.gather(*tasks)
        logger.info(f"All {len(results)} parallel tasks completed successfully")
    except Exception as e:
        logger.error(f"Parallel test failed: {e}")
        raise


async def main():
    """Run all tests."""
    # Check if we have necessary API keys
    required_keys = ["OPENAI_API_KEY", "GEMINI_API_KEY"]
    missing_keys = [key for key in required_keys if not os.getenv(key)]

    if missing_keys:
        logger.error(f"Missing required API keys: {missing_keys}")
        logger.error("Please set these environment variables to run integration tests")
        return

    # Set up Windows-specific configuration
    import platform
    if platform.system() == "Windows":
        logger.info("Running on Windows - using WindowsSelectorEventLoopPolicy")
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # Apply stdio patches
        from utils.stdio_wrapper import patch_stdio_for_windows
        patch_stdio_for_windows()

    try:
        # Test 1: Repeated calls with continuations
        await test_repeated_calls_with_continuations()

        # Test 2: Parallel calls
        await test_parallel_calls()

        logger.info("\n" + "="*60)
        logger.info("ALL TESTS PASSED!")
        logger.info("="*60)

    except Exception as e:
        logger.error("\n" + "="*60)
        logger.error("TEST FAILED!")
        logger.error("="*60)
        logger.error(f"Error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Run with asyncio
    asyncio.run(main())
