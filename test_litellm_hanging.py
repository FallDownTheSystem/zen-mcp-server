#!/usr/bin/env python3
"""
Direct test of LiteLLM to reproduce hanging issue.

This test directly calls LiteLLM to see if the hanging is at the LiteLLM level
or in our server code.
"""

import asyncio
import logging
import os
import sys
import time

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

import litellm
from litellm import acompletion


async def test_litellm_repeated_calls():
    """Test repeated LiteLLM calls to see if they hang."""

    logger.info("="*60)
    logger.info("Testing Direct LiteLLM Calls - 10 iterations")
    logger.info("="*60)

    # Configure LiteLLM
    litellm.drop_params = True
    litellm.request_timeout = 60  # 1 minute timeout

    # Test parameters
    iterations = 10
    model = "gpt-3.5-turbo"  # Use a basic model

    for i in range(iterations):
        logger.info(f"\n--- Iteration {i+1}/{iterations} ---")

        try:
            # Prepare messages
            messages = [
                {"role": "system", "content": "You are a helpful assistant. Be very brief."},
                {"role": "user", "content": f"Iteration {i+1}: Say hello in exactly 3 words."}
            ]

            # Make the async call
            logger.info(f"Making acompletion call to {model}...")
            start_time = time.time()

            response = await acompletion(
                model=model,
                messages=messages,
                temperature=0.1,
                max_tokens=50,
                timeout=30  # 30 second timeout per call
            )

            elapsed = time.time() - start_time
            logger.info(f"Call completed in {elapsed:.2f}s")

            # Extract response
            content = response.choices[0].message.content
            logger.info(f"Response: {content}")

            # Small delay between calls
            await asyncio.sleep(0.2)

        except Exception as e:
            logger.error(f"Error at iteration {i+1}: {e}")
            logger.error(f"POTENTIAL HANGING at iteration {i+1}")
            raise

    logger.info(f"\n{'='*60}")
    logger.info(f"SUCCESS: Completed all {iterations} iterations!")
    logger.info(f"{'='*60}")


async def test_parallel_litellm_calls():
    """Test parallel LiteLLM calls."""

    logger.info("\n" + "="*60)
    logger.info("Testing Parallel LiteLLM Calls - 5 concurrent")
    logger.info("="*60)

    async def make_call(task_id: int):
        messages = [
            {"role": "user", "content": f"Task {task_id}: Count to 3."}
        ]

        logger.info(f"[Task {task_id}] Starting...")
        start = time.time()

        response = await acompletion(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.1,
            max_tokens=50,
            timeout=30
        )

        elapsed = time.time() - start
        content = response.choices[0].message.content
        logger.info(f"[Task {task_id}] Completed in {elapsed:.2f}s: {content[:50]}...")

        return content

    # Create parallel tasks
    tasks = [make_call(i) for i in range(5)]

    try:
        results = await asyncio.gather(*tasks)
        logger.info(f"All {len(results)} parallel tasks completed!")
    except Exception as e:
        logger.error(f"Parallel test failed: {e}")
        raise


async def test_with_shared_client():
    """Test with a shared HTTP client like in our fix."""

    import httpx

    logger.info("\n" + "="*60)
    logger.info("Testing with Shared HTTP Client")
    logger.info("="*60)

    # Create shared client
    async_client = httpx.AsyncClient(
        timeout=httpx.Timeout(60.0),
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
    )

    # Set it in LiteLLM
    litellm.client_session = async_client
    logger.info("Configured shared HTTP client")

    try:
        # Run repeated calls with shared client
        for i in range(5):
            logger.info(f"\nCall {i+1} with shared client...")

            response = await acompletion(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": f"Say {i+1}"}],
                temperature=0,
                max_tokens=10
            )

            content = response.choices[0].message.content
            logger.info(f"Response: {content}")

            await asyncio.sleep(0.1)

        logger.info("\nShared client test completed!")

    finally:
        # Clean up
        await async_client.aclose()
        logger.info("Closed shared client")


async def main():
    """Run all tests."""

    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not set!")
        logger.error("Please set: export OPENAI_API_KEY=your-key-here")
        return

    # Windows-specific setup
    import platform
    if platform.system() == "Windows":
        logger.info("Running on Windows")
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # Try stdio patch
        try:
            from utils.stdio_wrapper import patch_stdio_for_windows
            patch_stdio_for_windows()
            logger.info("Applied stdio patches")
        except:
            logger.info("Running without stdio patches")

    try:
        # Test 1: Sequential calls
        await test_litellm_repeated_calls()

        # Test 2: Parallel calls
        await test_parallel_litellm_calls()

        # Test 3: With shared client
        await test_with_shared_client()

        logger.info("\n" + "="*80)
        logger.info("ALL TESTS COMPLETED SUCCESSFULLY!")
        logger.info("="*80)

    except Exception as e:
        logger.error("\n" + "="*80)
        logger.error("TEST FAILED!")
        logger.error("="*80)
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
