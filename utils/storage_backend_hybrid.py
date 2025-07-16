"""
In-memory storage backend for conversation threads (Hybrid sync/async version)

This module provides both sync and async interfaces to fix the threading.Lock
deadlock issue while maintaining backward compatibility.

The async methods use asyncio.Lock for proper event loop integration,
while sync methods use threading.Lock for non-async callers.
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
        self._sync_lock = threading.Lock()  # For sync methods
        self._async_lock = None  # Will be created when first async method is called
        # Match Redis behavior: cleanup interval based on conversation timeout
        timeout_hours = int(os.getenv("CONVERSATION_TIMEOUT_HOURS", "3"))
        self._cleanup_interval = (timeout_hours * 3600) // 10
        self._cleanup_interval = max(300, self._cleanup_interval)  # Minimum 5 minutes
        self._shutdown = False
        self._cleanup_task = None

        # Start background cleanup thread (sync version for now)
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker_sync, daemon=True)
        self._cleanup_thread.start()

        logger.info(
            f"In-memory storage initialized with {timeout_hours}h timeout, cleanup every {self._cleanup_interval // 60}m"
        )

    def _ensure_async_lock(self):
        """Ensure async lock exists (lazy initialization)."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()

    # Sync methods (original interface)

    def set_with_ttl(self, key: str, ttl_seconds: int, value: str) -> None:
        """Store value with expiration time (sync version)"""
        with self._sync_lock:
            expires_at = time.time() + ttl_seconds
            self._store[key] = (value, expires_at)
            logger.debug(f"Stored key {key} with TTL {ttl_seconds}s")

    def get(self, key: str) -> Optional[str]:
        """Retrieve value if not expired (sync version)"""
        with self._sync_lock:
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

    def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        """Redis-compatible setex method (sync version)"""
        self.set_with_ttl(key, ttl_seconds, value)

    # Async methods (new interface)

    async def set_with_ttl_async(self, key: str, ttl_seconds: int, value: str) -> None:
        """Store value with expiration time (async version)"""
        self._ensure_async_lock()
        async with self._async_lock:
            expires_at = time.time() + ttl_seconds
            self._store[key] = (value, expires_at)
            logger.debug(f"Stored key {key} with TTL {ttl_seconds}s (async)")

    async def get_async(self, key: str) -> Optional[str]:
        """Retrieve value if not expired (async version)"""
        self._ensure_async_lock()
        async with self._async_lock:
            if key in self._store:
                value, expires_at = self._store[key]
                if time.time() < expires_at:
                    logger.debug(f"Retrieved key {key} (async)")
                    return value
                else:
                    # Clean up expired entry
                    del self._store[key]
                    logger.debug(f"Key {key} expired and removed (async)")
        return None

    async def setex_async(self, key: str, ttl_seconds: int, value: str) -> None:
        """Redis-compatible setex method (async version)"""
        await self.set_with_ttl_async(key, ttl_seconds, value)

    # Cleanup methods

    def _cleanup_worker_sync(self):
        """Background thread that periodically cleans up expired entries"""
        while not self._shutdown:
            time.sleep(self._cleanup_interval)
            self._cleanup_expired_sync()

    def _cleanup_expired_sync(self):
        """Remove all expired entries (sync version)"""
        with self._sync_lock:
            current_time = time.time()
            expired_keys = [k for k, (_, exp) in self._store.items() if exp < current_time]
            for key in expired_keys:
                del self._store[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired conversation threads")

    async def _cleanup_expired_async(self):
        """Remove all expired entries (async version)"""
        self._ensure_async_lock()
        async with self._async_lock:
            current_time = time.time()
            expired_keys = [k for k, (_, exp) in self._store.items() if exp < current_time]
            for key in expired_keys:
                del self._store[key]
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired conversation threads (async)")

    def shutdown(self):
        """Graceful shutdown of background thread"""
        self._shutdown = True
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=1)


# Global singleton instance
_storage_instance = None
_storage_lock = threading.Lock()


def get_storage_backend() -> InMemoryStorage:
    """Get the global storage instance (singleton pattern)"""
    global _storage_instance
    if _storage_instance is None:
        with _storage_lock:
            if _storage_instance is None:
                _storage_instance = InMemoryStorage()
                logger.info("Initialized in-memory conversation storage (hybrid mode)")
    return _storage_instance
