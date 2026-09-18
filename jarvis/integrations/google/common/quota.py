"""Token bucket rate limiter and quota guardian for Google APIs."""
from __future__ import annotations

import asyncio
import time
from typing import Dict


class ServiceRateLimiter:
    """Token bucket rate limiter protecting Google API quota limits."""

    def __init__(self, rate_per_second: float = 5.0, burst: int = 10) -> None:
        self.rate = rate_per_second
        self.capacity = burst
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
        self.total_requests = 0
        self.total_delayed = 0

    async def acquire(self) -> None:
        """Acquire a quota token, waiting if bucket is exhausted."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

            if self.tokens < 1.0:
                deficit = 1.0 - self.tokens
                wait_time = deficit / self.rate
                self.total_delayed += 1
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0

            self.total_requests += 1


class QuotaManager:
    """Central registry of rate limiters per Google service."""

    def __init__(self) -> None:
        self._limiters: Dict[str, ServiceRateLimiter] = {
            "gmail": ServiceRateLimiter(rate_per_second=5.0, burst=10),
            "calendar": ServiceRateLimiter(rate_per_second=5.0, burst=10),
            "drive": ServiceRateLimiter(rate_per_second=8.0, burst=15),
        }

    async def acquire(self, service: str) -> None:
        limiter = self._limiters.get(service)
        if limiter:
            await limiter.acquire()

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        return {
            name: {
                "total_requests": lim.total_requests,
                "delayed_requests": lim.total_delayed,
            }
            for name, lim in self._limiters.items()
        }
