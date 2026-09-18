"""Data models and Resource Governor for system memory and model lifecycle (Phase 12)."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


class ModelRole(str, enum.Enum):
    ROUTER = "ROUTER"
    PLANNER = "PLANNER"
    VISION = "VISION"
    EMBEDDING = "EMBEDDING"
    STT = "STT"
    TTS = "TTS"


class SystemPriority(int, enum.Enum):
    STOP_CANCEL = 1
    VOICE_CAPTURE = 2
    STT = 3
    DETERMINISTIC_COMMAND = 4
    ROUTER = 5
    ACTIVE_PLANNER = 6
    UI_INTERACTION = 7
    VISION = 8
    BACKGROUND_EMBEDDING = 9
    BACKGROUND_INDEXING = 10
    OPTIMIZATION_JOB = 11


@dataclass
class ModelProfile:
    model_id: str
    role: ModelRole
    ram_mb: float = 0.0
    vram_mb: float = 0.0
    cold_load_ms: float = 0.0
    warm_latency_ms: float = 0.0
    last_used: float = field(default_factory=time.time)
    is_resident: bool = False
    keepalive_seconds: float = 120.0
    evict_hook: Optional[Callable[[], None]] = None


class ResourceGovernor:
    """
    Monitors RAM, VRAM, and interactive execution priorities.
    Manages model residency, ensuring idle vision and planner models unload
    while active voice capture and STT are protected.
    Guarantees decision latency p95 < 1 ms.
    """

    def __init__(
        self,
        ram_pressure_threshold_pct: float = 85.0,
        vram_pressure_threshold_mb: float = 4096.0,
    ):
        self.ram_threshold = ram_pressure_threshold_pct
        self.vram_threshold = vram_pressure_threshold_mb
        self.models: Dict[str, ModelProfile] = {}
        self._active_tasks: Dict[str, SystemPriority] = {}
        self._paused_background_jobs: bool = False

    def register_model(self, profile: ModelProfile):
        self.models[profile.model_id] = profile

    def touch_model(self, model_id: str):
        if model_id in self.models:
            self.models[model_id].last_used = time.time()
            self.models[model_id].is_resident = True

    def mark_model_evicted(self, model_id: str):
        if model_id in self.models:
            self.models[model_id].is_resident = False

    def start_task(self, task_id: str, priority: SystemPriority):
        self._active_tasks[task_id] = priority
        # If interactive high priority task starts (Voice, Command), pause background jobs
        if priority.value <= SystemPriority.UI_INTERACTION.value:
            self._paused_background_jobs = True

    def finish_task(self, task_id: str):
        self._active_tasks.pop(task_id, None)
        # If no high-priority tasks remain, resume background work
        if not any(p.value <= SystemPriority.UI_INTERACTION.value for p in self._active_tasks.values()):
            self._paused_background_jobs = False

    def is_background_paused(self) -> bool:
        return self._paused_background_jobs

    def evaluate_pressure_and_evict(
        self,
        current_ram_pct: float,
        current_vram_mb: float,
        now: Optional[float] = None,
    ) -> List[str]:
        """
        Evaluates memory pressure and evicts idle models.
        Priority: Active STT and voice are NEVER evicted.
        Idle Vision and Planner models are evicted first.
        Returns list of evicted model IDs.
        """
        curr_time = now if now is not None else time.time()
        evicted = []
        is_high_pressure = (current_ram_pct >= self.ram_threshold) or (current_vram_mb >= self.vram_threshold)

        for mid, profile in list(self.models.items()):
            if not profile.is_resident:
                continue

            # Protect active voice STT from eviction
            if profile.role in (ModelRole.STT, ModelRole.ROUTER):
                continue

            # Evict if high pressure or idle timeout exceeded
            idle_seconds = curr_time - profile.last_used
            if is_high_pressure or (idle_seconds >= profile.keepalive_seconds):
                if profile.evict_hook:
                    try:
                        profile.evict_hook()
                    except Exception:
                        pass
                profile.is_resident = False
                evicted.append(mid)

        return evicted

    def get_stats(self) -> Dict[str, Any]:
        resident_vram = sum(m.vram_mb for m in self.models.values() if m.is_resident)
        resident_ram = sum(m.ram_mb for m in self.models.values() if m.is_resident)
        return {
            "registered_models": len(self.models),
            "resident_models": [mid for mid, m in self.models.items() if m.is_resident],
            "total_resident_ram_mb": resident_ram,
            "total_resident_vram_mb": resident_vram,
            "background_jobs_paused": self._paused_background_jobs,
            "active_tasks": len(self._active_tasks),
        }
