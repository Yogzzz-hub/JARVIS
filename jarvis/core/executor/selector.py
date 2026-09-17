from __future__ import annotations

import asyncio
import math
import sqlite3
import time
from enum import StrEnum
from pathlib import Path
from typing import Any

from jarvis.tools.base import (
    ExecutionMethod,
    IdempotencyClass,
    RiskLevel,
    ToolDefinition,
    ToolVariant,
    VerificationResult,
    VerificationStatus,
)

class FailureClassification(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TIMEOUT = "TIMEOUT"
    RESOURCE_BUSY = "RESOURCE_BUSY"
    NETWORK_ERROR = "NETWORK_ERROR"
    PROCESS_FAILED = "PROCESS_FAILED"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    UAC_REQUIRED = "UAC_REQUIRED"
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    UNCERTAIN_SIDE_EFFECT = "UNCERTAIN_SIDE_EFFECT"

class RetryDecision(StrEnum):
    RETRY_SAME_METHOD = "RETRY_SAME_METHOD"
    TRY_NEXT_METHOD = "TRY_NEXT_METHOD"
    VERIFY_AGAIN = "VERIFY_AGAIN"
    DO_NOT_RETRY = "DO_NOT_RETRY"
    ASK_USER = "ASK_USER"

class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    """Lightweight circuit breaker for methods/providers to prevent hammering failing dependencies."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout_s: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = CircuitState.CLOSED

    def can_execute(self) -> bool:
        now = time.monotonic()
        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time > self.recovery_timeout_s:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        return True

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "db" / "jarvis.db"

class MethodStatsTracker:
    """Tracks historical method execution statistics, EWMA latency, and quarantine state."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._stats: dict[str, dict[str, Any]] = {}
        self._quarantines: dict[str, float] = {}  # key -> expiry_timestamp
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

    def _get_key(self, capability: str, method: str) -> str:
        return f"{capability}:{method}"

    def get_circuit_breaker(self, capability: str, method: str) -> CircuitBreaker:
        key = self._get_key(capability, method)
        if key not in self._circuit_breakers:
            self._circuit_breakers[key] = CircuitBreaker()
        return self._circuit_breakers[key]

    def is_quarantined(self, capability: str, method: str) -> bool:
        key = self._get_key(capability, method)
        expiry = self._quarantines.get(key)
        if expiry is None:
            return False
        if time.time() > expiry:
            del self._quarantines[key]
            return False
        return True

    def quarantine(self, capability: str, method: str, duration_s: float = 60.0) -> None:
        key = self._get_key(capability, method)
        self._quarantines[key] = time.time() + duration_s

    def record_attempt(
        self,
        capability: str,
        method: str,
        success: bool,
        verified: bool,
        duration_ms: float,
        uncertain: bool = False,
    ) -> None:
        key = self._get_key(capability, method)
        now = time.time()
        stat = self._stats.setdefault(key, {
            "attempts": 0,
            "successes": 0,
            "verified_successes": 0,
            "failures": 0,
            "uncertain": 0,
            "ewma_latency_ms": duration_ms,
            "consecutive_failures": 0,
        })

        stat["attempts"] += 1
        # EWMA decay
        stat["ewma_latency_ms"] = 0.8 * stat["ewma_latency_ms"] + 0.2 * duration_ms

        cb = self.get_circuit_breaker(capability, method)

        if success and verified:
            stat["successes"] += 1
            stat["verified_successes"] += 1
            stat["consecutive_failures"] = 0
            cb.record_success()
        elif uncertain:
            stat["uncertain"] += 1
            stat["consecutive_failures"] += 1
            cb.record_failure()
        else:
            stat["failures"] += 1
            stat["consecutive_failures"] += 1
            cb.record_failure()
            if stat["consecutive_failures"] >= 5:
                self.quarantine(capability, method, duration_s=60.0)

    def get_stats(self, capability: str, method: str) -> dict[str, Any]:
        key = self._get_key(capability, method)
        return self._stats.get(key, {
            "attempts": 0,
            "successes": 0,
            "verified_successes": 0,
            "failures": 0,
            "uncertain": 0,
            "ewma_latency_ms": 5.0,
            "consecutive_failures": 0,
        })

class MethodSelector:
    """Scores available execution variants based on reliability, latency, context, and quarantine state."""

    def __init__(self, stats_tracker: MethodStatsTracker | None = None) -> None:
        self.tracker = stats_tracker or MethodStatsTracker()

    def select_variant(
        self,
        tool_def: ToolDefinition,
        context_tags: tuple[str, ...] = (),
    ) -> ToolVariant | ExecutionMethod:
        variants = tool_def.variants
        if not variants:
            return tool_def.execution_method

        scored_variants: list[tuple[float, ToolVariant]] = []
        for variant in variants:
            m_str = variant.method.value
            is_quar = self.tracker.is_quarantined(tool_def.name, m_str)
            cb = self.tracker.get_circuit_breaker(tool_def.name, m_str)
            if not cb.can_execute():
                continue

            stat = self.tracker.get_stats(tool_def.name, m_str)
            attempts = stat["attempts"]
            success_rate = (stat["verified_successes"] / attempts) if attempts > 0 else 0.95
            ewma_lat = stat["ewma_latency_ms"]

            # Scoring: (success_rate * confidence) / (latency_cost + failure_penalty)
            quarantine_penalty = 10.0 if is_quar else 1.0
            latency_cost = math.log1p(max(ewma_lat, 1.0))
            score = (success_rate * variant.confidence * (10 / variant.priority)) / (latency_cost * quarantine_penalty)
            scored_variants.append((score, variant))

        if not scored_variants:
            # All filtered/tripped, fallback to primary default
            return tool_def.variants[0] if tool_def.variants else tool_def.execution_method

        scored_variants.sort(key=lambda x: x[0], reverse=True)
        return scored_variants[0][1]

class FailureClassifier:
    """Classifies runtime errors and exceptions into structured categories."""

    @staticmethod
    def classify(error: Exception | str | None) -> FailureClassification:
        if error is None:
            return FailureClassification.TRANSIENT

        if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
            return FailureClassification.TIMEOUT

        err_str = str(error).lower()
        if "uac" in err_str or "elevation" in err_str:
            return FailureClassification.UAC_REQUIRED
        if "not found" in err_str or "no such file" in err_str or "not exist" in err_str:
            return FailureClassification.NOT_FOUND
        if "permission" in err_str or "access is denied" in err_str or "unauthorized" in err_str:
            return FailureClassification.PERMISSION_DENIED
        if "timeout" in err_str or "timed out" in err_str:
            return FailureClassification.TIMEOUT
        if "busy" in err_str or "locked" in err_str:
            return FailureClassification.RESOURCE_BUSY
        if "connection" in err_str or "network" in err_str or "socket" in err_str:
            return FailureClassification.NETWORK_ERROR
        if "auth" in err_str or "password" in err_str or "captcha" in err_str:
            return FailureClassification.AUTH_REQUIRED
        if "invalid" in err_str or "argument" in err_str:
            return FailureClassification.INVALID_ARGUMENT
        if "uncertain" in err_str:
            return FailureClassification.UNCERTAIN_SIDE_EFFECT

        return FailureClassification.PERMANENT

class RetryEngine:
    """Computes retry decisions obeying idempotency, retry budget, and verification results."""

    @staticmethod
    def decide(
        tool_def: ToolDefinition,
        attempt: int,
        failure_class: FailureClassification,
        verification_status: VerificationStatus,
        has_next_variant: bool = False,
        max_attempts: int = 3,
    ) -> RetryDecision:
        if attempt >= max_attempts:
            return RetryDecision.DO_NOT_RETRY

        # Security stops
        if failure_class in (FailureClassification.UAC_REQUIRED, FailureClassification.AUTH_REQUIRED):
            return RetryDecision.ASK_USER

        if failure_class in (FailureClassification.PERMISSION_DENIED, FailureClassification.INVALID_ARGUMENT):
            return RetryDecision.DO_NOT_RETRY

        # Uncertainty handling: NEVER blindly retry non-idempotent operations
        if verification_status == VerificationStatus.UNCERTAIN or failure_class == FailureClassification.UNCERTAIN_SIDE_EFFECT:
            if tool_def.idempotency == IdempotencyClass.NON_IDEMPOTENT:
                return RetryDecision.DO_NOT_RETRY
            if tool_def.idempotency == IdempotencyClass.VERIFY_BEFORE_RETRY:
                return RetryDecision.VERIFY_AGAIN

        # If method variant failed with NOT_FOUND or TIMEOUT and fallback exists
        if has_next_variant and failure_class in (FailureClassification.NOT_FOUND, FailureClassification.PROCESS_FAILED, FailureClassification.TIMEOUT):
            return RetryDecision.TRY_NEXT_METHOD

        # Standard retry for idempotent tools
        if tool_def.idempotency == IdempotencyClass.IDEMPOTENT:
            return RetryDecision.RETRY_SAME_METHOD

        return RetryDecision.DO_NOT_RETRY
