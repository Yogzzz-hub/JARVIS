"""Optional operational evidence. Never an execution or authentication authority.

Only enumerated metadata is persisted; event payloads, queries, messages, URLs,
recipient identifiers and model reasoning cannot enter this store.
"""
from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
import math
from pathlib import Path
import sqlite3
import time
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class OperationalTrace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    label: str = Field(default_factory=lambda: uuid4().hex, pattern=r"^[a-f0-9]{32}$")
    timestamp: float = Field(default_factory=time.time, ge=0, allow_inf_nan=False)
    provenance: Literal["REAL_SHADOW", "SYNTHETIC", "MOCK"] = "SYNTHETIC"
    source: Literal["http", "cli", "websocket", "voice", "whatsapp", "test", "benchmark"]
    language: Literal["ENGLISH", "TANGLISH", "TAMIL", "MIXED", "MIXED_TAMIL_ENGLISH", "UNKNOWN"] = "UNKNOWN"
    route: Literal["LANE_0", "LANE_1", "LANE_2", "LANE_3", "CLARIFY", "REJECT", "CONTROL", "UNKNOWN"] = "UNKNOWN"
    tool: str = Field(default="", pattern=r"^[a-z0-9_]{0,80}$")
    outcome: Literal["SUCCESS", "PARTIAL_SUCCESS", "COMPLETED", "FAILED", "CANCELLED", "WAITING_CONFIRMATION", "UNCERTAIN", "WAITING_FOR_USER"]
    verified: bool | None = None
    duration_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    recommendation: Literal["LANE_0", "LANE_1", "LANE_2", "LANE_3", "CLARIFY", "REJECT", "CONTROL"] | None = None
    advisor_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    # These are coarse classifications, never raw policy/exception messages.
    policy: Literal["NOT_OBSERVED", "CONFIRM", "BLOCK", "COMPLETED"] = "NOT_OBSERVED"


class TraceStore:
    def __init__(self, path: Path, max_rows: int = 10000):
        self.path = Path(path)
        self.max_rows = max(1, min(max_rows, 100000))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS operational_traces (seq INTEGER PRIMARY KEY, payload TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=2)

    def append(self, trace: OperationalTrace):
        with self.connect() as con:
            con.execute("INSERT INTO operational_traces(payload) VALUES (?)", (trace.model_dump_json(),))
            con.execute("DELETE FROM operational_traces WHERE seq <= COALESCE((SELECT seq FROM operational_traces ORDER BY seq DESC LIMIT 1 OFFSET ?), 0)", (self.max_rows,))

    def recent(self, limit: int = 10000):
        with self.connect() as con:
            rows = con.execute("SELECT payload FROM operational_traces ORDER BY seq DESC LIMIT ?", (max(1, min(limit, self.max_rows)),)).fetchall()
        return [OperationalTrace.model_validate_json(row[0]) for row in rows]

    def aggregate(self):
        rows = self.recent()
        real = [r for r in rows if r.provenance == "REAL_SHADOW"]
        comparisons = [r for r in real if r.recommendation is not None]
        lanes = defaultdict(list)
        for r in rows:
            lanes[r.route].append(r.duration_ms)
        def pct(values, q):
            values = sorted(values)
            return values[min(len(values)-1, max(0, math.ceil(len(values)*q)-1))]
        return {"total": len(rows), "real_shadow": len(real), "owner_reviewed": 0,
                "verified_real": 0, "languages": dict(Counter(r.language for r in real)),
                "outcomes": dict(Counter(r.outcome for r in rows)),
                "advisor": {"eligible": len(real), "abstentions": len(real)-len(comparisons),
                            "comparisons": len(comparisons),
                            "agreements": sum(r.route == r.recommendation for r in comparisons)},
                "latency_by_route": {k: {"count": len(v), "p50_ms": pct(v, .5), "p95_ms": pct(v, .95)} for k, v in lanes.items()},
                "accuracy": "UNREVIEWED; no accuracy inferred"}


class TraceDrivenRouterAdvisor:
    """Historical majority recommendation; abstains without sufficient evidence.

    Advises only. No production binding, executable tool or permission API.
    Successful traces are operational outcomes, not owner-reviewed route gold.
    """
    def __init__(self, minimum: int = 20):
        self.minimum = max(5, minimum)
        self._counts = defaultdict(Counter)

    def observe(self, trace: OperationalTrace):
        if trace.provenance == "REAL_SHADOW" and trace.outcome in {"SUCCESS", "COMPLETED"} and trace.verified is not False:
            self._counts[(trace.language, trace.source)][trace.route] += 1

    def recommend(self, language: str, source: str):
        counts = self._counts.get((language, source), {})
        total = sum(counts.values())
        if total < self.minimum:
            return None
        route = max(counts, key=counts.get)
        return route if counts[route] / total >= .8 and route != "UNKNOWN" else None


class OperationalDiagnostics:
    """Bounded EventBus subscriber; SQLite runs off the command event loop."""
    def __init__(self, store: TraceStore, advisor_enabled: bool = False):
        self.store = store
        self.advisor = TraceDrivenRouterAdvisor()
        self.advisor_enabled = advisor_enabled
        self.errors = 0

    async def consume(self, event):
        if event.name != "trace.completed":
            return
        try:
            trace = OperationalTrace.model_validate(event.data)
            start = time.perf_counter()
            recommendation = self.advisor.recommend(trace.language, trace.source) if self.advisor_enabled else None
            trace = trace.model_copy(update={"recommendation": recommendation, "advisor_ms": (time.perf_counter()-start)*1000})
            await asyncio.to_thread(self.store.append, trace)
            self.advisor.observe(trace)
        except Exception:
            self.errors += 1


class CandidateOverlay(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    candidate_id: str = Field(pattern=r"^[a-z0-9_-]{1,64}$")
    target: Literal["capability_description", "skill_prompt", "retrieval_weights", "routing_threshold"]
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidate_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    state: Literal["DEVELOPMENT", "SHADOW", "ACCEPTANCE_READY", "PROMOTED", "ROLLED_BACK"] = "DEVELOPMENT"
    gates: dict[Literal["quality", "latency", "resource", "safety", "regression", "real_evidence"], bool] = Field(default_factory=dict)
    rollback_pointer: str = ""

    def transition(self, state: str, *, owner_approved: bool = False):
        allowed = {"DEVELOPMENT": {"SHADOW"}, "SHADOW": {"ACCEPTANCE_READY"},
                   "ACCEPTANCE_READY": {"PROMOTED", "SHADOW"}, "PROMOTED": {"ROLLED_BACK"}, "ROLLED_BACK": {"SHADOW"}}
        if state not in allowed[self.state]:
            raise ValueError("Invalid candidate transition")
        if state in {"ACCEPTANCE_READY", "PROMOTED"} and not all(self.gates.get(k, False) for k in ("quality", "latency", "resource", "safety", "regression", "real_evidence")):
            raise ValueError("All evidence gates must pass")
        if state == "PROMOTED" and (not owner_approved or not self.rollback_pointer):
            raise ValueError("Explicit owner approval and rollback pointer required")
        # Metadata only: never writes production configuration or source files.
        return self.model_copy(update={"state": state})
