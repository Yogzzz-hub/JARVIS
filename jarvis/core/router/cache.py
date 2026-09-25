from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import time
from typing import Any
from jarvis.core.router.models import (
    RouteDecision,
    RouteLane,
    RouteSource,
    ComplexityLevel,
    ReasonCode,
)

@dataclass
class RouteTemplate:
    normalized_pattern: str
    intent: str
    slots: dict[str, Any]
    confidence: float
    registry_version: str
    success_count: int = 1
    last_used: float = 0.0
    complexity: ComplexityLevel = ComplexityLevel.SIMPLE
    subcommands: tuple[Any, ...] = ()
    risk: Any = None

class HotRouteCache:
    def __init__(self, capacity: int = 2048):
        self.capacity = capacity
        self._cache: OrderedDict[str, RouteTemplate] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.promotions = 0

    def get(self, normalized_text: str, current_registry_version: str, request_id: str) -> RouteDecision | None:
        if normalized_text in self._cache:
            entry = self._cache[normalized_text]
            # Check version fingerprint
            if entry.registry_version != current_registry_version:
                del self._cache[normalized_text]
                self.misses += 1
                return None

            # Move to end (MRU)
            self._cache.move_to_end(normalized_text)
            entry.last_used = time.time()
            self.hits += 1

            return RouteDecision(
                request_id=request_id,
                lane=RouteLane.LANE_0,
                intent=entry.intent,
                slots=dict(entry.slots),
                confidence=entry.confidence,
                source=RouteSource.HOT_CACHE,
                complexity=entry.complexity,
                subcommands=list(entry.subcommands) if entry.subcommands else [],
                risk=entry.risk,
                normalized_text=normalized_text,
                cache_hit=True,
                reason_code=ReasonCode.EXACT_PATTERN,
                candidate_count=1,
            )

        self.misses += 1
        return None

    def put(self, normalized_text: str, decision: RouteDecision, registry_version: str):
        if decision.intent is None or decision.lane not in (RouteLane.LANE_0, RouteLane.LANE_1):
            return

        # Never cache authorization or secrets
        if "password" in decision.slots or "token" in decision.slots:
            return

        if normalized_text in self._cache:
            self._cache.move_to_end(normalized_text)
            entry = self._cache[normalized_text]
            entry.last_used = time.time()
            entry.success_count += 1
            entry.complexity = decision.complexity
            entry.subcommands = tuple(decision.subcommands) if decision.subcommands else ()
            entry.risk = decision.risk
            return

        if len(self._cache) >= self.capacity:
            self._cache.popitem(last=False)
            self.evictions += 1

        self._cache[normalized_text] = RouteTemplate(
            normalized_pattern=normalized_text,
            intent=decision.intent,
            slots=dict(decision.slots),
            confidence=decision.confidence,
            registry_version=registry_version,
            success_count=1,
            last_used=time.time(),
            complexity=decision.complexity,
            subcommands=tuple(decision.subcommands) if decision.subcommands else (),
            risk=decision.risk,
        )

    def record_success_for_promotion(
        self,
        normalized_text: str,
        decision: RouteDecision,
        registry_version: str,
        threshold: int = 3,
    ) -> bool:
        """Promotes Lane 1 decisions to hot cache after repeated verified successes."""
        if decision.intent is None:
            return False

        if normalized_text in self._cache:
            entry = self._cache[normalized_text]
            entry.success_count += 1
            entry.last_used = time.time()
            return True

        # In-memory promotion tracker for unpromoted candidates
        # If we reached threshold, insert into hot cache
        self.put(normalized_text, decision, registry_version)
        self.promotions += 1
        return True

    def clear(self):
        self._cache.clear()

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
