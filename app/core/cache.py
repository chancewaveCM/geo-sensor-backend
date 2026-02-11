"""Simple in-memory TTL-based cache for analytics responses."""

import time
from typing import Any


class SimpleCache:
    """TTL-based in-memory cache for analytics responses."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        """Get value from cache if not expired."""
        if key in self._store:
            value, expires_at = self._store[key]
            if time.time() < expires_at:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in cache with TTL in seconds (default 5 minutes)."""
        self._store[key] = (value, time.time() + ttl)

    def invalidate(self, pattern: str) -> int:
        """Invalidate all keys matching pattern prefix."""
        keys = [k for k in self._store if k == pattern or k.startswith(pattern + ":")]
        for k in keys:
            del self._store[k]
        return len(keys)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._store.clear()


# Global cache instance
response_cache = SimpleCache()
