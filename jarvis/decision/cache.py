"""LRU cache of JDE decisions keyed by normalized text + context signature + model/catalog versions.

Only routing decisions are cached - never authorization (policy always re-runs), and callers must
still re-resolve live targets/resources.
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Optional


class DecisionCache:
    def __init__(self, size: int = 2048):
        self.size = size
        self._d: "OrderedDict[str, Any]" = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            v = self._d.get(key)
            if v is None:
                self.misses += 1
                return None
            self._d.move_to_end(key)
            self.hits += 1
            return v

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._d[key] = value
            self._d.move_to_end(key)
            while len(self._d) > self.size:
                self._d.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._d.clear()
