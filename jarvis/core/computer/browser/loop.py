"""Dedicated event loop thread that owns the Playwright browser.

Playwright objects are bound to the event loop that created them. The browser tools run in
the ExecutionEngine's worker threads, and previously each call did ``asyncio.run(...)``,
which created a fresh loop per call: the first action worked, then every following action
failed with "Event loop is closed" because the page belonged to a dead loop. All browser
coroutines now run on this single long-lived loop, so a session (navigate -> type -> click
-> read) keeps working across tool calls.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from typing import Any, Awaitable, Callable, Optional, TypeVar

logger = logging.getLogger("jarvis.computer.browser.loop")

T = TypeVar("T")


class BrowserLoop:
    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._ready = threading.Event()

    def _serve(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    def ensure_started(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None or self._loop.is_closed() or not (self._thread and self._thread.is_alive()):
                self._ready.clear()
                self._thread = threading.Thread(target=self._serve, name="jarvis-browser-loop", daemon=True)
                self._thread.start()
                self._ready.wait(5.0)
        assert self._loop is not None
        return self._loop

    @property
    def in_loop_thread(self) -> bool:
        return self._thread is not None and threading.current_thread() is self._thread

    def run(self, coro: Awaitable[T], timeout: float = 60.0) -> T:
        """Run a coroutine on the browser loop from any other thread and wait for its result."""
        if self.in_loop_thread:
            raise RuntimeError("BrowserLoop.run() called from the browser loop itself (would deadlock)")
        loop = self.ensure_started()
        future = asyncio.run_coroutine_threadsafe(coro, loop)  # type: ignore[arg-type]
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError(f"Browser action timed out after {timeout:.0f}s")

    async def run_async(self, coro_factory: Callable[[], Awaitable[T]], timeout: float = 60.0) -> T:
        """Await browser work from another event loop without blocking it."""
        loop = self.ensure_started()
        future = asyncio.run_coroutine_threadsafe(coro_factory(), loop)  # type: ignore[arg-type]
        return await asyncio.wait_for(asyncio.wrap_future(future), timeout)

    def stop(self) -> None:
        with self._lock:
            if self._loop is not None and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread is not None:
                self._thread.join(timeout=5.0)
            self._loop = None
            self._thread = None


_browser_loop = BrowserLoop()


def get_browser_loop() -> BrowserLoop:
    return _browser_loop


def run_browser(coro: Awaitable[T], timeout: float = 60.0) -> T:
    return _browser_loop.run(coro, timeout=timeout)
