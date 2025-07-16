#!/usr/bin/env python3
"""
Simple test to reproduce the Windows hanging issue.

This test directly calls the tools to reproduce the hanging issue
without going through the full MCP server protocol.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_hanging.log')
    ]
)
logger = logging.getLogger(__name__)

# Import tools
from tools import ChatTool


async def test_chat_tool_repeated():
    """Test the chat tool with repeated calls to reproduce hanging."""

    logger.info("="*60)
    logger.info("Testing Chat Tool - 10 iterations")
    logger.info("="*60)

    # Initialize tool
    chat_tool = ChatTool()

    # Test parameters
    iterations = 10
    continuation_id = None

    for i in range(iterations):
        logger.info(f"\n--- Iteration {i+1}/{iterations} ---")

        try:
            # Prepare arguments
            args = {
                "prompt": f"Iteration {i+1}: Write a single line Python comment. Be extremely brief.",
                "model": "gpt-4o-mini",
                "temperature": 0.1
            }

            if continuation_id:
                args["continuation_id"] = continuation_id
                logger.info(f"Using continuation_id: {continuation_id}")

            # Make the call
            logger.info("Making chat tool call...")
            start_time = asyncio.get_event_loop().time()

            result = await chat_tool.execute(args)

            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info(f"Call completed in {elapsed:.2f}s")

            # Extract continuation_id if present
            if result and len(result) > 0:
                try:
                    result_text = result[0].text
                    result_json = json.loads(result_text)

                    if "continuation_offer" in result_json:
                        continuation_id = result_json["continuation_offer"]["continuation_id"]
                        logger.info(f"Got new continuation_id: {continuation_id}")

                    # Log a snippet of the response
                    response_snippet = result_json.get("response", "")[:100]
                    logger.info(f"Response snippet: {response_snippet}...")

                except Exception as e:
                    logger.warning(f"Could not parse result as JSON: {e}")

            # Small delay between calls
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Error at iteration {i+1}: {e}", exc_info=True)
            logger.error(f"HANGING DETECTED at iteration {i+1}")
            raise

    logger.info(f"\n{'='*60}")
    logger.info(f"SUCCESS: Completed all {iterations} iterations without hanging!")
    logger.info(f"{'='*60}")


async def test_consensus_tool():
    """Test the consensus tool with repeated calls."""

    from tools import ConsensusTool

    logger.info("\n" + "="*60)
    logger.info("Testing Consensus Tool - 5 iterations")
    logger.info("="*60)

    # Initialize tool
    consensus_tool = ConsensusTool()

    # Test parameters
    iterations = 5
    continuation_id = None

    for i in range(iterations):
        logger.info(f"\n--- Iteration {i+1}/{iterations} ---")

        try:
            # Prepare arguments
            args = {
                "prompt": f"Iteration {i+1}: Is Python or JavaScript better for backend? Answer in one sentence.",
                "models": [
                    {"model": "gpt-4o-mini"},
                    {"model": "gemini-flash"}
                ],
                "enable_cross_feedback": False,  # Faster without feedback
                "temperature": 0.2
            }

            if continuation_id:
                args["continuation_id"] = continuation_id
                logger.info(f"Using continuation_id: {continuation_id}")

            # Make the call
            logger.info("Making consensus tool call...")
            start_time = asyncio.get_event_loop().time()

            result = await consensus_tool.execute(args)

            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info(f"Call completed in {elapsed:.2f}s")

            # Extract continuation_id if present
            if result and len(result) > 0:
                try:
                    result_text = result[0].text
                    result_json = json.loads(result_text)

                    if "continuation_offer" in result_json:
                        continuation_id = result_json["continuation_offer"]["continuation_id"]
                        logger.info(f"Got new continuation_id: {continuation_id}")

                    # Log status
                    status = result_json.get("status", "unknown")
                    successful = result_json.get("successful_responses", 0)
                    logger.info(f"Consensus status: {status}, successful models: {successful}")

                except Exception as e:
                    logger.warning(f"Could not parse result as JSON: {e}")

            # Small delay between calls
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error at iteration {i+1}: {e}", exc_info=True)
            logger.error(f"HANGING DETECTED at iteration {i+1}")
            raise

    logger.info(f"\n{'='*60}")
    logger.info(f"SUCCESS: Completed all {iterations} consensus iterations!")
    logger.info(f"{'='*60}")


async def test_rapid_fire():
    """Test rapid fire calls without delays to stress test."""

    logger.info("\n" + "="*60)
    logger.info("Testing Rapid Fire Calls - 20 quick calls")
    logger.info("="*60)

    chat_tool = ChatTool()

    for i in range(20):
        try:
            args = {
                "prompt": f"Say '{i+1}'",
                "model": "gpt-4o-mini",
                "temperature": 0
            }

            logger.info(f"Rapid call {i+1}...")
            result = await chat_tool.execute(args)

            # No delay - rapid fire

        except Exception as e:
            logger.error(f"Rapid fire failed at call {i+1}: {e}")
            raise

    logger.info("Rapid fire test completed!")


async def main():
    """Run all tests."""

    # Check API keys
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not set!")
        return

    # Windows-specific setup
    import platform
    if platform.system() == "Windows":
        logger.info("Running on Windows - applying patches")
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # Try to import and apply stdio patch
        try:
            from utils.stdio_wrapper import patch_stdio_for_windows
            patch_stdio_for_windows()
            logger.info("Stdio patches applied")
        except ImportError:
            logger.warning("Could not import stdio_wrapper - continuing without patch")

    try:
        # Test 1: Chat tool repeated calls
        await test_chat_tool_repeated()

        # Test 2: Consensus tool (if Gemini key available)
        if os.getenv("GEMINI_API_KEY"):
            await test_consensus_tool()
        else:
            logger.warning("Skipping consensus test - GEMINI_API_KEY not set")

        # Test 3: Rapid fire
        await test_rapid_fire()

        logger.info("\n" + "="*80)
        logger.info("ALL TESTS PASSED - NO HANGING DETECTED!")
        logger.info("="*80)

    except Exception as e:
        logger.error("\n" + "="*80)
        logger.error("TEST FAILED - HANGING OR ERROR DETECTED!")
        logger.error("="*80)
        logger.error(f"Final error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
