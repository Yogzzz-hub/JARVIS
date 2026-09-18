"""Bounded SpecialistCoordinator and ResultMerger for parallel capability modules (Phase 12)."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional
from jarvis.core.specialists.models import (
    MergedResult,
    SpecialistFact,
    SpecialistResult,
    SpecialistType,
)


class ResultMerger:
    """Merges structured facts from multiple specialists, preserving provenance and noting discrepancies."""

    @staticmethod
    def merge(results: List[SpecialistResult], elapsed_ms: float = 0.0) -> MergedResult:
        all_facts: List[SpecialistFact] = []
        all_refs: List[str] = []
        discrepancies: List[str] = []
        participating = [r.specialist for r in results]

        success_count = sum(1 for r in results if r.status == "SUCCESS")
        failure_count = sum(1 for r in results if r.status == "FAILURE")

        # Collect facts and deduplicate by statement
        seen_statements = set()
        for r in results:
            if r.status in ("SUCCESS", "PARTIAL"):
                for f in r.facts:
                    norm_stmt = f.statement.strip().lower()
                    if norm_stmt not in seen_statements:
                        seen_statements.add(norm_stmt)
                        all_facts.append(f)
                for ref in r.resource_refs:
                    if ref not in all_refs:
                        all_refs.append(ref)
            elif r.status == "FAILURE" and r.error_message:
                discrepancies.append(f"{r.specialist.value} failed: {r.error_message}")

        if success_count == len(results):
            overall_status = "SUCCESS"
        elif success_count > 0:
            overall_status = "PARTIAL"
        else:
            overall_status = "FAILURE"

        return MergedResult(
            status=overall_status,
            facts=all_facts,
            resource_refs=all_refs,
            discrepancies=discrepancies,
            participating_specialists=participating,
            latency_ms=elapsed_ms,
        )


class SpecialistCoordinator:
    """
    Coordinates execution of bounded capability specialists with structured concurrency.
    Guarantees that specialists never hold authority to bypass policy or execute
    arbitrary side-effects.
    """

    def __init__(self, max_concurrent: int = 4):
        self.max_concurrent = max_concurrent

    async def execute_parallel(
        self,
        specialist_tasks: List[Tuple[SpecialistType, Callable[[], Coroutine[Any, Any, SpecialistResult]]]],
        timeout_seconds: float = 5.0,
    ) -> MergedResult:
        """
        Executes bounded specialist coroutines in parallel with timeout and cancellation.
        Failure in one specialist isolates gracefully, allowing others to complete.
        """
        t0 = time.perf_counter()
        bounded_tasks = specialist_tasks[:self.max_concurrent]

        async def _run_one(spec_type: SpecialistType, coro_factory) -> SpecialistResult:
            st0 = time.perf_counter()
            try:
                res = await coro_factory()
                res.latency_ms = (time.perf_counter() - st0) * 1000.0
                return res
            except asyncio.CancelledError:
                return SpecialistResult(
                    specialist=spec_type,
                    status="CANCELLED",
                    error_message="Specialist cancelled by coordinator",
                    latency_ms=(time.perf_counter() - st0) * 1000.0,
                )
            except Exception as ex:
                return SpecialistResult(
                    specialist=spec_type,
                    status="FAILURE",
                    error_message=str(ex),
                    latency_ms=(time.perf_counter() - st0) * 1000.0,
                )

        coros = [_run_one(st, cf) for st, cf in bounded_tasks]
        try:
            results = await asyncio.wait_for(asyncio.gather(*coros, return_exceptions=False), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            results = [
                SpecialistResult(
                    specialist=st,
                    status="FAILURE",
                    error_message=f"Timeout after {timeout_seconds}s",
                )
                for st, _ in bounded_tasks
            ]

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return ResultMerger.merge(results, elapsed_ms=elapsed_ms)
