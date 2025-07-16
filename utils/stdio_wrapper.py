"""
Wrapper for stdio operations to handle Windows-specific issues.

This module provides a wrapper around stdout operations to prevent
the "OSError: [Errno 22] Invalid argument" error that occurs on Windows
when the MCP server processes multiple requests.
"""

import asyncio
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)


class SafeStdoutWriter:
    """
    A wrapper around stdout that handles Windows-specific pipe issues.
    
    This class provides buffering and error handling to prevent the
    "Invalid argument" error that can occur when writing to stdout
    on Windows after multiple operations.
    """

    def __init__(self, original_stdout):
        self.original_stdout = original_stdout
        self._lock = asyncio.Lock()
        self._closed = False
        self._buffer = []

    async def write(self, data: Any) -> None:
        """Safely write data to stdout with error handling."""
        if self._closed:
            logger.warning("Attempted to write to closed stdout")
            return

        async with self._lock:
            try:
                # Convert to string if needed
                if not isinstance(data, (str, bytes)):
                    data = str(data)

                # Write directly
                self.original_stdout.write(data)

                # Try to flush, but don't fail if it errors
                try:
                    self.original_stdout.flush()
                except OSError as e:
                    if e.errno == 22:  # Invalid argument
                        logger.warning("Stdout flush failed with Invalid argument, continuing without flush")
                    else:
                        raise

            except Exception as e:
                logger.error(f"Error writing to stdout: {e}")
                # Don't re-raise to prevent hanging

    def close(self) -> None:
        """Mark the writer as closed."""
        self._closed = True


def patch_stdio_for_windows():
    """
    Patch sys.stdout to use SafeStdoutWriter on Windows.
    
    This helps prevent the "Invalid argument" error that can occur
    when the MCP server processes multiple requests on Windows.
    """
    import platform

    if platform.system() == "Windows":
        logger.info("Patching stdout for Windows compatibility")

        # Create wrapper
        safe_stdout = SafeStdoutWriter(sys.stdout)

        # Create a proxy that looks like stdout but uses our safe writer
        class StdoutProxy:
            def __init__(self, safe_writer):
                self.safe_writer = safe_writer
                self._original = sys.stdout

            def write(self, data):
                # Run async write in sync context
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Schedule the write
                        asyncio.create_task(self.safe_writer.write(data))
                    else:
                        # Fall back to original
                        self._original.write(data)
                except Exception:
                    # Fall back to original
                    self._original.write(data)

            def flush(self):
                # Ignore flush errors on Windows
                try:
                    self._original.flush()
                except OSError as e:
                    if e.errno == 22:  # Invalid argument
                        pass
                    else:
                        raise

            def __getattr__(self, name):
                return getattr(self._original, name)

        # Replace sys.stdout
        sys.stdout = StdoutProxy(safe_stdout)
        logger.info("Stdout patched successfully")
