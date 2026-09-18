"""Ephemeral Short-TTL Caching and Invalidation for Vision Fallback."""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple
from jarvis.core.vision.models import VisualCandidate, VisualGroundingDecision


class VisualCache:
    """Bounded, ephemeral in-memory cache for visual candidates and grounding decisions."""

    def __init__(self, default_ttl_s: float = 15.0, max_entries: int = 32) -> None:
        self.default_ttl_s = default_ttl_s
        self.max_entries = max_entries
        self._candidate_cache: Dict[str, Tuple[float, List[VisualCandidate]]] = {}
        self._decision_cache: Dict[str, Tuple[float, VisualGroundingDecision]] = {}
        self._recent_hashes: List[str] = []
        self._last_window_bounds: Optional[Tuple[int, int, int, int]] = None
        self._current_generation: int = 1

    def set_generation(self, generation: int) -> None:
        """Incrementing generation invalidates all visual caches."""
        if generation != self._current_generation:
            self.clear()
            self._current_generation = generation

    def notify_window_bounds(self, bounds: Tuple[int, int, int, int]) -> bool:
        """Check if window has moved or resized. If changed, invalidates cache."""
        if self._last_window_bounds is None:
            self._last_window_bounds = bounds
            return False

        if bounds != self._last_window_bounds:
            self.clear()
            self._last_window_bounds = bounds
            return True  # Moved or resized
        return False

    def record_image_hash(self, image_hash: str) -> None:
        """Track image hash for loop/stall detection."""
        self._recent_hashes.append(image_hash)
        if len(self._recent_hashes) > 6:
            self._recent_hashes.pop(0)

    def is_stalled(self, threshold: int = 3) -> bool:
        """Check if the screen state has remained identical for `threshold` consecutive actions."""
        if len(self._recent_hashes) < threshold:
            return False
        last_n = self._recent_hashes[-threshold:]
        return len(set(last_n)) == 1

    def get_candidates(self, image_hash: str) -> Optional[List[VisualCandidate]]:
        """Retrieve cached candidates if image hash matches and TTL is valid."""
        if image_hash in self._candidate_cache:
            ts, candidates = self._candidate_cache[image_hash]
            if time.time() - ts < self.default_ttl_s:
                return candidates
            del self._candidate_cache[image_hash]
        return None

    def store_candidates(self, image_hash: str, candidates: List[VisualCandidate]) -> None:
        """Store candidates keyed by image hash."""
        if len(self._candidate_cache) >= self.max_entries:
            oldest_key = min(self._candidate_cache.keys(), key=lambda k: self._candidate_cache[k][0])
            del self._candidate_cache[oldest_key]
        self._candidate_cache[image_hash] = (time.time(), candidates)

    def get_decision(self, goal: str, image_hash: str) -> Optional[VisualGroundingDecision]:
        """Retrieve cached grounding decision for the identical goal and image hash."""
        key = f"{goal.strip().lower()}::{image_hash}"
        if key in self._decision_cache:
            ts, decision = self._decision_cache[key]
            if time.time() - ts < self.default_ttl_s:
                return decision
            del self._decision_cache[key]
        return None

    def store_decision(self, goal: str, image_hash: str, decision: VisualGroundingDecision) -> None:
        """Store grounding decision keyed by goal and image hash."""
        if len(self._decision_cache) >= self.max_entries:
            oldest_key = min(self._decision_cache.keys(), key=lambda k: self._decision_cache[k][0])
            del self._decision_cache[oldest_key]
        key = f"{goal.strip().lower()}::{image_hash}"
        self._decision_cache[key] = (time.time(), decision)

    def clear(self) -> None:
        """Purge all ephemeral caches."""
        self._candidate_cache.clear()
        self._decision_cache.clear()
        self._recent_hashes.clear()
