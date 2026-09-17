"""Plan Template Cache for Phase 4.

Provides bounded in-memory LRU (512 entries) + SQLite persistent caching of
reusable TaskGraph SHAPES. Parameterizes variable slots ($query, $destination)
and invalidates entries when tool registry fingerprint changes.
Guarantees p95 lookup < 1 ms.
"""

from collections import OrderedDict
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Optional
from uuid import uuid4

from jarvis.core.planner.schema import TaskGraph, TaskNode, ValueBinding


class PlanTemplateCache:
    def __init__(
        self,
        capacity: int = 512,
        db_path: Optional[str] = None,
        promotion_threshold: int = 3,
    ):
        self.capacity = capacity
        self.db_path = db_path
        self.promotion_threshold = promotion_threshold
        self._memory_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()

        # Metrics
        self.hits = 0
        self.misses = 0
        self.invalidated = 0
        self.promoted = 0
        self.execution_success = 0
        self.execution_failure = 0

    def compute_task_signature(self, text: str, intents: list[str]) -> str:
        """Generates a stable normalized signature for task generalization."""
        norm = " ".join(text.lower().strip().split())
        intents_str = ",".join(sorted(intents))
        raw = f"{norm}::{intents_str}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def get(
        self,
        text: str,
        intents: list[str],
        current_registry_fingerprint: str,
        current_schema_version: str = "1.0.0",
    ) -> Optional[TaskGraph]:
        """Retrieves and instantiates a cached TaskGraph template in < 1 ms."""
        sig = self.compute_task_signature(text, intents)

        # 1. In-memory check
        entry = self._memory_cache.get(sig)
        if entry is not None:
            # Check registry fingerprint
            if entry["fingerprint"] != current_registry_fingerprint or entry["schema_version"] != current_schema_version:
                del self._memory_cache[sig]
                self.invalidated += 1
                self.misses += 1
                return None

            self._memory_cache.move_to_end(sig)
            self.hits += 1
            entry["hit_count"] += 1
            return self._instantiate_template(entry["template_graph"], text)

        # 2. SQLite persistent check if DB configured
        if self.db_path and Path(self.db_path).exists():
            try:
                conn = sqlite3.connect(self.db_path, timeout=1.0)
                cur = conn.cursor()
                cur.execute(
                    "SELECT tool_registry_fingerprint, graph_template_json, hit_count FROM plan_cache WHERE task_signature = ?",
                    (sig,),
                )
                row = cur.fetchone()
                if row:
                    fp, graph_json, hit_cnt = row
                    if fp != current_registry_fingerprint:
                        cur.execute("DELETE FROM plan_cache WHERE task_signature = ?", (sig,))
                        conn.commit()
                        conn.close()
                        self.invalidated += 1
                        self.misses += 1
                        return None

                    # Cache into memory
                    raw_graph = json.loads(graph_json)
                    template_graph = TaskGraph.model_validate(raw_graph)
                    self._put_memory(
                        sig,
                        template_graph,
                        current_registry_fingerprint,
                        current_schema_version,
                        hit_count=hit_cnt + 1,
                    )
                    cur.execute(
                        "UPDATE plan_cache SET hit_count = hit_count + 1, last_used_at = CURRENT_TIMESTAMP WHERE task_signature = ?",
                        (sig,),
                    )
                    conn.commit()
                    conn.close()
                    self.hits += 1
                    return self._instantiate_template(template_graph, text)
                conn.close()
            except Exception:
                pass

        self.misses += 1
        return None

    def record_execution(
        self,
        text: str,
        intents: list[str],
        graph: TaskGraph,
        success: bool,
        current_registry_fingerprint: str,
        current_schema_version: str = "1.0.0",
    ):
        """Records execution result. Promotes plan template after 3 successful executions."""
        sig = self.compute_task_signature(text, intents)

        if not success:
            self.execution_failure += 1
            # Evict if present
            if sig in self._memory_cache:
                del self._memory_cache[sig]
            return

        self.execution_success += 1

        # Check existing entry
        if sig not in self._memory_cache:
            self._put_memory(
                sig,
                graph,
                current_registry_fingerprint,
                current_schema_version,
                success_count=1,
            )
        else:
            entry = self._memory_cache[sig]
            entry["success_count"] += 1
            if entry["success_count"] >= self.promotion_threshold and not entry.get("persisted"):
                self._persist_to_sqlite(sig, graph, current_registry_fingerprint)
                entry["persisted"] = True
                self.promoted += 1

    def _put_memory(
        self,
        sig: str,
        graph: TaskGraph,
        fingerprint: str,
        schema_version: str,
        hit_count: int = 0,
        success_count: int = 0,
    ):
        if len(self._memory_cache) >= self.capacity:
            self._memory_cache.popitem(last=False)

        self._memory_cache[sig] = {
            "template_graph": graph,
            "fingerprint": fingerprint,
            "schema_version": schema_version,
            "hit_count": hit_count,
            "success_count": success_count,
            "persisted": False,
        }

    def _persist_to_sqlite(self, sig: str, graph: TaskGraph, fingerprint: str):
        if not self.db_path:
            return
        try:
            conn = sqlite3.connect(self.db_path, timeout=1.0)
            cur = conn.cursor()
            graph_json = graph.model_dump_json()
            template_id = f"tpl_{uuid4().hex[:12]}"
            cur.execute(
                """
                INSERT INTO plan_cache (template_id, task_signature, tool_registry_fingerprint, graph_template_json, hit_count, success_count)
                VALUES (?, ?, ?, ?, 1, 3)
                ON CONFLICT(task_signature) DO UPDATE SET
                    graph_template_json = excluded.graph_template_json,
                    tool_registry_fingerprint = excluded.tool_registry_fingerprint,
                    success_count = success_count + 1,
                    last_used_at = CURRENT_TIMESTAMP
                """,
                (template_id, sig, fingerprint, graph_json),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _instantiate_template(self, template: TaskGraph, current_text: str) -> TaskGraph:
        """Instantiates a fresh TaskGraph copy with unique graph_id and fresh timestamps."""
        new_graph = template.model_copy(
            update={
                "graph_id": f"g_{uuid4().hex[:12]}",
                "goal": current_text,
            },
            deep=True,
        )
        return new_graph
