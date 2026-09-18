"""Dedicated bounded thread pool executor for non-blocking Google API calls."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

T = TypeVar("T")

DEFAULT_WORKERS = 4


class GoogleIntegrationExecutor:
    """Manages a bounded thread pool dedicated strictly to Google API network calls."""

    def __init__(self, max_workers: int = DEFAULT_WORKERS) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="jarvis-google-io",
        )

    async def run(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run synchronous blocking function in the dedicated worker thread."""
        loop = asyncio.get_running_loop()
        if kwargs:
            def wrapper():
                return fn(*args, **kwargs)
            return await loop.run_in_executor(self._executor, wrapper)
        return await loop.run_in_executor(self._executor, fn, *args)

    def shutdown(self, wait: bool = False) -> None:
        """Shut down the executor."""
        self._executor.shutdown(wait=wait)
