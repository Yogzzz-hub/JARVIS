"""Resource Lock Manager for Phase 4 DAG Scheduler.

Provides asynchronous key-based locking (e.g. file:<path>, directory:<path>, system:<resource>)
to serialize conflicting operations across parallel DAG branches without deadlocks.
"""

import asyncio
from contextlib import asynccontextmanager
import os
from typing import AsyncGenerator, Sequence


class ResourceLockManager:
    def __init__(self):
        self._locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()

    async def _get_lock(self, key: str) -> asyncio.Lock:
        async with self._meta_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    @asynccontextmanager
    async def acquire(self, keys: Sequence[str]) -> AsyncGenerator[None, None]:
        """Acquires multiple resource locks in sorted key order to prevent deadlocks."""
        # Normalize and sort unique keys
        unique_sorted_keys = sorted(set(keys))
        acquired_locks: list[asyncio.Lock] = []

        try:
            for k in unique_sorted_keys:
                lock = await self._get_lock(k)
                await lock.acquire()
                acquired_locks.append(lock)
            yield
        finally:
            # Release in reverse order
            for lock in reversed(acquired_locks):
                lock.release()

    @staticmethod
    def extract_resource_keys(tool_name: str, args: dict) -> list[str]:
        """Extracts standard resource keys from tool arguments."""
        keys = []
        for param in ("path", "source", "destination", "directory", "file_path"):
            val = args.get(param)
            if isinstance(val, str) and val.strip():
                norm = os.path.normpath(val.strip()).lower()
                keys.append(f"file:{norm}")

        if tool_name in ("open_app", "close_app"):
            target = args.get("target_app") or args.get("app_name") or args.get("target")
            if target:
                keys.append(f"app:{str(target).lower()}")

        return keys
