"""Bounded exponential backoff and idempotency-aware retries for Google APIs."""
from __future__ import annotations

import asyncio
import inspect
import logging
import random
import time
from typing import Any, Callable, TypeVar

from jarvis.integrations.google.common.errors import GoogleErrorCode, GoogleProviderError

logger = logging.getLogger(__name__)

T = TypeVar("T")


def execute_with_retry(
    fn: Callable[[], Any],
    service: str = "google",
    operation_name: str = "",
    max_retries: int = 3,
    initial_delay_s: float = 0.5,
    max_delay_s: float = 8.0,
    jitter_factor: float = 0.25,
    is_write: bool = False,
) -> Any:
    """Execute provider operation with bounded exponential backoff.
    
    Supports both synchronous functions and async coroutines seamlessly.
    If `is_write=True`, non-idempotent operations will NOT be blindly retried
    on timeout or network ambiguity to prevent double-writes or duplicate emails.
    """
    svc_name = operation_name or service

    async def _async_runner(first_coro: Any) -> Any:
        attempt = 1
        delay = initial_delay_s
        coro = first_coro
        while True:
            try:
                return await coro
            except GoogleProviderError as err:
                if is_write and err.code in (GoogleErrorCode.TIMEOUT, GoogleErrorCode.NETWORK_UNAVAILABLE):
                    logger.warning(
                        "[%s] Write operation failed with %s; blind retry suppressed to prevent double-execution",
                        svc_name,
                        err.code.value,
                    )
                    raise err

                if not err.retryable or attempt > max_retries:
                    raise err

                jitter = random.uniform(-jitter_factor * delay, jitter_factor * delay)
                sleep_time = min(max_delay_s, max(0.1, delay + jitter))
                logger.info(
                    "[%s] Retryable error %s (attempt %d/%d). Backing off for %.2fs",
                    svc_name,
                    err.code.value,
                    attempt,
                    max_retries,
                    sleep_time,
                )
                await asyncio.sleep(sleep_time)
                delay = min(max_delay_s, delay * 2.0)
                attempt += 1
                coro = fn()

    if inspect.iscoroutinefunction(fn):
        return _async_runner(fn())

    attempt = 1
    delay = initial_delay_s
    while True:
        try:
            val = fn()
            if inspect.iscoroutine(val):
                return _async_runner(val)
            return val
        except GoogleProviderError as err:
            if is_write and err.code in (GoogleErrorCode.TIMEOUT, GoogleErrorCode.NETWORK_UNAVAILABLE):
                logger.warning(
                    "[%s] Write operation failed with %s; blind retry suppressed to prevent double-execution",
                    svc_name,
                    err.code.value,
                )
                raise err

            if not err.retryable or attempt > max_retries:
                raise err

            jitter = random.uniform(-jitter_factor * delay, jitter_factor * delay)
            sleep_time = min(max_delay_s, max(0.1, delay + jitter))
            logger.info(
                "[%s] Retryable error %s (attempt %d/%d). Backing off for %.2fs",
                svc_name,
                err.code.value,
                attempt,
                max_retries,
                sleep_time,
            )
            time.sleep(sleep_time)
            delay = min(max_delay_s, delay * 2.0)
            attempt += 1
