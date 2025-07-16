#!/usr/bin/env python3
"""
Quick test to verify the singleton state fix works.
This test makes multiple calls to verify the server doesn't hang.
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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from tools import ChatTool


async def test_fresh_instances():
    """Test that we get fresh tool instances each time."""
    
    logger.info("="*60)
    logger.info("Testing Fresh Tool Instances - 5 iterations")
    logger.info("="*60)
    
    for i in range(5):
        logger.info(f"\n--- Iteration {i+1}/5 ---")
        
        # Create a new ChatTool instance
        tool = ChatTool()
        logger.info(f"Created tool instance: {id(tool)}")
        
        # Make a call
        args = {
            "prompt": f"Iteration {i+1}: Say 'Hello {i+1}'",
            "model": "gpt-3.5-turbo",
            "temperature": 0
        }
        
        try:
            result = await tool.execute(args)
            if result:
                logger.info("✅ Tool call succeeded")
            else:
                logger.error("❌ Tool call returned None")
        except Exception as e:
            logger.error(f"❌ Tool call failed: {e}")
            raise
        
        # Small delay
        await asyncio.sleep(0.2)
    
    logger.info(f"\n{'='*60}")
    logger.info("✅ SUCCESS: All iterations completed without hanging!")
    logger.info(f"{'='*60}")


async def main():
    """Run the test."""
    
    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not set!")
        return
    
    # Windows setup
    import platform
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        await test_fresh_instances()
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())