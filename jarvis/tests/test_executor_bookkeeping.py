"""A busy jarvis.db (another writer holding the lock) must not hold the reply after an action already ran: the
ledger / audit / stats / undo records finish in the background instead of stacking 15-30 s lock waits."""
from __future__ import annotations

import asyncio
import threading
import time

from jarvis.core.executor.engine import ExecutionEngine


def test_slow_records_do_not_hold_the_reply(tmp_path):
    engine = ExecutionEngine.__new__(ExecutionEngine)       # only the bookkeeping parts are needed
    from concurrent.futures import ThreadPoolExecutor
    engine._records = ThreadPoolExecutor(max_workers=1)
    engine._pending_records = set()
    engine.pool = ThreadPoolExecutor(max_workers=1)
    engine.BOOKKEEP_WAIT_S = 0.2
    finished = threading.Event()

    def slow():
        time.sleep(1.0)        # stands in for a write waiting on a locked database
        finished.set()

    async def run():
        started = time.perf_counter()
        await engine._bookkeep(slow, "open_app")
        waited = time.perf_counter() - started
        assert waited < 0.6 and not finished.is_set()
        await engine.close()                                    # shutdown still lets the record land
        assert finished.is_set()

    asyncio.run(run())


def test_fast_records_complete_before_returning():
    engine = ExecutionEngine.__new__(ExecutionEngine)
    from concurrent.futures import ThreadPoolExecutor
    engine._records = ThreadPoolExecutor(max_workers=1)
    engine._pending_records = set()
    engine.pool = ThreadPoolExecutor(max_workers=1)
    done = []

    async def run():
        await engine._bookkeep(lambda: done.append(1), "get_time")
        assert done == [1]
        await engine.close()

    asyncio.run(run())
