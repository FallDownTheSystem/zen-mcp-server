"""
In-memory storage backend for conversation threads (Async version)

This module provides a thread-safe AND asyncio-safe in-memory alternative to Redis
for storing conversation contexts. It's designed for ephemeral MCP server sessions
where conversations only need to persist during a single Claude session.

This async version fixes the threading.Lock deadlock issue by using asyncio.Lock
instead, which properly yields control to the event loop.

⚠️  PROCESS-SPECIFIC STORAGE: This storage is confined to a single Python process.
    Data stored in one process is NOT accessible from other processes or subprocesses.
    This is why simulator tests that run server.py as separate subprocesses cannot
    share conversation state between tool calls.

Key Features:
- Asyncio-safe operations using asyncio.Lock
- TTL support with automatic expiration
- Background cleanup task for memory management
- Singleton pattern for consistent state within a single process
- Drop-in replacement for Redis storage (for single-process scenarios)
"""

import asyncio
import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class InMemoryStorage:
    """Thread-safe AND asyncio-safe in-memory storage for conversation threads"""

    def __init__(self):
        self._store: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()  # Use asyncio.Lock instead of threading.Lock
        # Match Redis behavior: cleanup interval based on conversation timeout
        # Run cleanup at 1/10th of timeout interval (e.g., 18 mins for 3 hour timeout)
        timeout_hours = int(os.getenv("CONVERSATION_TIMEOUT_HOURS", "3"))
        self._cleanup_interval = (timeout_hours * 3600) // 10
        self._cleanup_interval = max(300, self._cleanup_interval)  # Minimum 5 minutes
        self._shutdown = asyncio.Event()

        # Start background cleanup as an asyncio task
        self._cleanup_task = asyncio.create_task(self._cleanup_worker())

        logger.info(
            f"In-memory storage initialized with {timeout_hours}h timeout, cleanup every {self._cleanup_interval // 60}m"
        )

    async def set_with_ttl(self, key: str, ttl_seconds: int, value: str) -> None:
        """Store value with expiration time"""
        async with self._lock:
            expires_at = time.time() + ttl_seconds
            self._store[key] = (value, expires_at)
            logger.debug(f"Stored key {key} with TTL {ttl_seconds}s")

    async def get(self, key: str) -> Optional[str]:
        """Retrieve value if not expired"""
        async with self._lock:
            if key in self._store:
                value, expires_at = self._store[key]
                if time.time() < expires_at:
                    logger.debug(f"Retrieved key {key}")
                    return value
                else:
                    # Clean up expired entry
                    del self._store[key]
                    logger.debug(f"Key {key} expired and removed")
        return None

    async def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        """Redis-compatible setex method"""
        await self.set_with_ttl(key, ttl_seconds, value)

    async def _cleanup_worker(self):
        """Background task that periodically cleans up expired entries"""
        while not self._shutdown.is_set():
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break

    async def _cleanup_expired(self):
        """Remove all expired entries"""
        async with self._lock:
            current_time = time.time()
            expired_keys = [k for k, (_, exp) in self._store.items() if exp < current_time]
            for key in expired_keys:
                del self._store[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired conversation threads")

    async def shutdown(self):
        """Graceful shutdown of background task"""
        self._shutdown.set()
        self._cleanup_task.cancel()
        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass  # Expected


# Global singleton instance
_storage_instance = None
_storage_lock = threading.Lock()  # This lock is fine for singleton creation


def get_storage_backend() -> InMemoryStorage:
    """Get the global storage instance (singleton pattern)"""
    global _storage_instance
    if _storage_instance is None:
        with _storage_lock:
            if _storage_instance is None:
                _storage_instance = InMemoryStorage()
                logger.info("Initialized in-memory conversation storage")
    return _storage_instance