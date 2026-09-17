"""Priority-driven, bounded Audio Output Queue for JARVIS EDGE Phase 7.

Enforces:
1. Strict priority ordering (Emergency > Confirmation > Final > Progress > ACK).
2. Obsolete ACK drop when final response arrives.
3. Stale response purge when a request is completed or cancelled.
4. Response idempotency and duplicate final prevention per request.
"""
from __future__ import annotations

import heapq
import logging
import threading
from typing import Dict, List, Optional, Set, Tuple

from jarvis.core.response.models import (
    DeliveryStatus,
    ResponseLifecycle,
    ResponsePriority,
    ResponseType,
    SpokenResponse,
)

logger = logging.getLogger("jarvis.audio.output.queue")


class AudioOutputQueue:
    """Thread-safe bounded priority queue for spoken audio output."""

    def __init__(self, max_size: int = 10) -> None:
        self.max_size = max_size
        self._heap: List[Tuple[int, int, SpokenResponse]] = []
        self._counter = 0
        self._lock = threading.Lock()

        # Idempotency & lifecycle tracking
        self._seen_response_ids: Set[str] = set()
        self._request_lifecycles: Dict[str, ResponseLifecycle] = {}
        self._active_requests: Set[str] = set()

        # Metrics
        self.total_enqueued = 0
        self.total_dropped_stale = 0
        self.total_dropped_obsolete_ack = 0
        self.total_duplicates_prevented = 0

    def register_active_request(self, request_id: str) -> None:
        """Register that a request is active."""
        with self._lock:
            self._active_requests.add(request_id)
            if request_id not in self._request_lifecycles:
                self._request_lifecycles[request_id] = ResponseLifecycle.NONE

    def put(self, response: SpokenResponse) -> bool:
        """Enqueue a spoken response according to priority and idempotency rules.

        Returns True if enqueued, False if rejected (duplicate/stale/dropped).
        """
        with self._lock:
            # 1. Idempotency check on response_id
            if response.response_id in self._seen_response_ids:
                logger.debug("Duplicate response_id %s dropped", response.response_id)
                self.total_duplicates_prevented += 1
                return False
            self._seen_response_ids.add(response.response_id)

            req_id = response.request_id
            if req_id and self._request_lifecycles.get(req_id) != ResponseLifecycle.FINAL_COMPLETED:
                self._active_requests.add(req_id)

            current_state = self._request_lifecycles.get(req_id, ResponseLifecycle.NONE)

            # 2. Duplicate FINAL prevention
            if response.type == ResponseType.FINAL:
                if current_state in (
                    ResponseLifecycle.FINAL_QUEUED,
                    ResponseLifecycle.FINAL_STARTED,
                    ResponseLifecycle.FINAL_COMPLETED,
                ):
                    logger.debug("Duplicate FINAL for request %s dropped", req_id)
                    self.total_duplicates_prevented += 1
                    return False
                self._request_lifecycles[req_id] = ResponseLifecycle.FINAL_QUEUED

                # 3. Drop obsolete pending ACK for this request if still in queue
                self._drop_pending_acks_for_request(req_id)

            elif response.type == ResponseType.ACK:
                # If final is already queued or completed, don't enqueue ACK
                if current_state in (
                    ResponseLifecycle.FINAL_QUEUED,
                    ResponseLifecycle.FINAL_STARTED,
                    ResponseLifecycle.FINAL_COMPLETED,
                ):
                    logger.debug("Obsolete ACK for request %s dropped (final arrived)", req_id)
                    self.total_dropped_obsolete_ack += 1
                    return False
                self._request_lifecycles[req_id] = ResponseLifecycle.ACK_SENT

            # 4. Check queue capacity
            if len(self._heap) >= self.max_size:
                # Evict lowest-priority item (highest priority number)
                worst_idx = -1
                worst_prio = -1
                for i, (prio, _, resp) in enumerate(self._heap):
                    if prio > worst_prio and resp.priority > response.priority:
                        worst_prio = prio
                        worst_idx = i

                if worst_idx >= 0:
                    evicted = self._heap.pop(worst_idx)
                    heapq.heapify(self._heap)
                    logger.warning("Queue overflow: evicted lower priority %s", evicted[2].type)
                    self.total_dropped_stale += 1
                else:
                    logger.warning("Queue full: cannot enqueue %s", response.type)
                    return False

            self._counter += 1
            # heapq is min-heap: lowest priority integer = popped first
            heapq.heappush(self._heap, (int(response.priority), self._counter, response))
            self.total_enqueued += 1
            return True

    def get(self) -> Optional[SpokenResponse]:
        """Pop the highest priority response from the queue."""
        with self._lock:
            while self._heap:
                prio, _, resp = heapq.heappop(self._heap)
                req_id = resp.request_id

                # Verify request is still active / relevant
                if req_id and req_id not in self._active_requests and resp.priority > ResponsePriority.EMERGENCY:
                    logger.debug("Stale item dropped for inactive request %s", req_id)
                    resp.delivery_status = DeliveryStatus.DROPPED_STALE
                    self.total_dropped_stale += 1
                    continue

                return resp
            return None

    def cancel_request(self, request_id: str) -> int:
        """Purge all pending audio items associated with a request ID."""
        dropped = 0
        with self._lock:
            new_heap = []
            for prio, count, resp in self._heap:
                if resp.request_id == request_id:
                    resp.delivery_status = DeliveryStatus.DROPPED_STALE
                    dropped += 1
                else:
                    new_heap.append((prio, count, resp))
            self._heap = new_heap
            heapq.heapify(self._heap)
            self._active_requests.discard(request_id)
            self.total_dropped_stale += dropped
        return dropped

    def mark_request_completed(self, request_id: str) -> None:
        """Mark request as completed."""
        with self._lock:
            self._request_lifecycles[request_id] = ResponseLifecycle.FINAL_COMPLETED
            self._active_requests.discard(request_id)

    def _drop_pending_acks_for_request(self, request_id: str) -> None:
        """Internal helper to remove ACKs for a specific request when final arrives."""
        new_heap = []
        for prio, count, resp in self._heap:
            if resp.request_id == request_id and resp.type == ResponseType.ACK:
                resp.delivery_status = DeliveryStatus.DROPPED_STALE
                self.total_dropped_obsolete_ack += 1
            else:
                new_heap.append((prio, count, resp))
        self._heap = new_heap
        heapq.heapify(self._heap)

    def clear(self) -> None:
        """Clear all items from queue."""
        with self._lock:
            self._heap.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._heap)
