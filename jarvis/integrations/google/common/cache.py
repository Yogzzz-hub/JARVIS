"""Bounded in-memory cache with TTL and write-invalidation for Google metadata."""
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple


class ConnectedContentCache:
    """Bounded in-memory LRU cache with TTL for read-only metadata."""

    def __init__(self, max_entries: int = 256, default_ttl_s: float = 60.0) -> None:
        self.max_entries = max_entries
        self.default_ttl_s = default_ttl_s
        self._cache: OrderedDict[str, Tuple[float, Any]] = OrderedDict()

        # Metrics
        self.total_hits = 0
        self.total_misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieve unexpired value from cache."""
        if key not in self._cache:
            self.total_misses += 1
            return None

        expiry, value = self._cache[key]
        if time.monotonic() > expiry:
            del self._cache[key]
            self.total_misses += 1
            return None

        # Move to end (LRU)
        self._cache.move_to_end(key)
        self.total_hits += 1
        return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None, ttl_s: Optional[float] = None) -> None:
        """Store value with TTL expiration."""
        ttl = ttl_seconds if ttl_seconds is not None else (ttl_s if ttl_s is not None else self.default_ttl_s)
        expiry = time.monotonic() + ttl

        if key in self._cache:
            del self._cache[key]
        elif len(self._cache) >= self.max_entries:
            # Evict oldest
            self._cache.popitem(last=False)

        self._cache[key] = (expiry, value)

    def invalidate(self, key: str) -> bool:
        """Invalidate a specific cache key."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all cache entries matching a prefix (e.g. upon writes)."""
        keys_to_del = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_del:
            del self._cache[k]
        return len(keys_to_del)

    def clear(self) -> None:
        """Purge all entries."""
        self._cache.clear()


_GLOBAL_CONNECTOR_CACHE: Optional[ConnectedContentCache] = None


def get_connector_cache() -> ConnectedContentCache:
    """Singleton getter for the global Google connector cache."""
    global _GLOBAL_CONNECTOR_CACHE
    if _GLOBAL_CONNECTOR_CACHE is None:
        _GLOBAL_CONNECTOR_CACHE = ConnectedContentCache()
    return _GLOBAL_CONNECTOR_CACHE
