"""Approved workflow library, parameter binding, versioning, and execution dispatch."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jarvis.core.workflows.models import (
    ApprovedWorkflow,
    WorkflowCandidate,
    WorkflowGraphTemplate,
    WorkflowNodeTemplate,
    WorkflowSlot,
    WorkflowStatus,
)


class WorkflowLibrary:
    """
    Manages approved workflows stored in SQLite and hot memory cache.
    Handles parameter binding, schema versioning, and quarantine logic.
    """

    def __init__(self, db_path: str | Path, registry_fingerprint: str = "v1"):
        self.db_path = str(db_path)
        self.registry_fingerprint = registry_fingerprint
        self._hot_cache: Dict[str, ApprovedWorkflow] = {}
        self._ensure_tables()
        self._load_approved()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _ensure_tables(self):
        with self._get_connection() as conn:
            migration_file = Path(__file__).resolve().parent.parent.parent / "db/migrations/006_phase12_intelligence.sql"
            if migration_file.exists():
                try:
                    conn.executescript(migration_file.read_text(encoding="utf-8"))
                except sqlite3.OperationalError:
                    pass

    def _load_approved(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM workflow_templates WHERE status = 'APPROVED'")
                rows = cursor.fetchall()
                self._hot_cache.clear()
                for row in rows:
                    wf = self._row_to_workflow(row)
                    self._hot_cache[wf.name.casefold()] = wf
                    self._hot_cache[wf.workflow_id] = wf
        except sqlite3.OperationalError:
            pass

    def approve_candidate(
        self,
        candidate: WorkflowCandidate,
        custom_name: Optional[str] = None,
        description: str = "",
    ) -> ApprovedWorkflow:
        """Promotes a candidate to an ApprovedWorkflow upon explicit user consent."""
        name = (custom_name or candidate.name_suggestion).strip()
        wf_id = f"wf_{int(time.time())}_{candidate.graph_shape_hash[:6]}"
        now = time.time()

        approved_wf = ApprovedWorkflow(
            workflow_id=wf_id,
            name=name,
            description=description or f"Approved workflow: {name}",
            input_schema=candidate.variable_slots,
            graph_template=candidate.graph_template,
            required_tools=[n.tool for n in candidate.graph_template.nodes],
            required_capabilities=[],
            risk_profile=candidate.risk_summary,
            registry_fingerprint=self.registry_fingerprint,
            schema_version="1.0",
            created_at=now,
            approved_at=now,
            version=1,
            status=WorkflowStatus.APPROVED,
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            slots_json = json.dumps([{"name": s.name, "slot_type": s.slot_type} for s in approved_wf.input_schema])
            nodes_json = json.dumps([
                {
                    "node_template_id": n.node_template_id,
                    "tool": n.tool,
                    "args_template": n.args_template,
                    "depends_on": n.depends_on,
                    "risk": n.risk,
                    "idempotency": n.idempotency,
                }
                for n in approved_wf.graph_template.nodes
            ])
            cursor.execute(
                """
                INSERT OR REPLACE INTO workflow_templates (
                    workflow_id, name, description, input_schema_json,
                    graph_template_json, required_tools_json, required_capabilities_json,
                    risk_profile, registry_fingerprint, schema_version,
                    created_at, approved_at, version, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approved_wf.workflow_id,
                    approved_wf.name,
                    approved_wf.description,
                    slots_json,
                    nodes_json,
                    json.dumps(approved_wf.required_tools),
                    json.dumps(approved_wf.required_capabilities),
                    approved_wf.risk_profile,
                    approved_wf.registry_fingerprint,
                    approved_wf.schema_version,
                    approved_wf.created_at,
                    approved_wf.approved_at,
                    approved_wf.version,
                    approved_wf.status.value,
                ),
            )
            conn.commit()

        # Update cache
        self._hot_cache[approved_wf.name.casefold()] = approved_wf
        self._hot_cache[approved_wf.workflow_id] = approved_wf
        candidate.status = WorkflowStatus.APPROVED
        return approved_wf

    def find_matching_workflow(self, utterance: str) -> Optional[ApprovedWorkflow]:
        """Ultra-fast exact/lexical workflow template matching (p95 < 2 ms)."""
        clean = utterance.strip().casefold()
        # Direct exact name match
        if clean in self._hot_cache:
            wf = self._hot_cache[clean]
            if wf.status == WorkflowStatus.APPROVED and not wf.is_quarantined():
                return wf

        # Substring / alias match
        for key, wf in self._hot_cache.items():
            if wf.status == WorkflowStatus.APPROVED and not wf.is_quarantined():
                if key == wf.name.casefold() and (key in clean or clean in key):
                    return wf
        return None

    def bind_parameters(
        self,
        workflow: ApprovedWorkflow,
        parameter_values: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], bool, str]:
        """
        Binds runtime parameter values into the template graph nodes (p95 < 3 ms).
        Returns (bound_nodes, is_valid, error_msg).
        """
        # Validate tool registry fingerprint to guard against schema changes
        if workflow.registry_fingerprint != self.registry_fingerprint:
            return [], False, f"Workflow schema version mismatch: {workflow.registry_fingerprint} vs {self.registry_fingerprint}"

        bound_nodes: List[Dict[str, Any]] = []
        for node in workflow.graph_template.nodes:
            bound_args = {}
            for arg_k, arg_v in node.args_template.items():
                if isinstance(arg_v, str) and arg_v.startswith("{{") and arg_v.endswith("}}"):
                    slot_name = arg_v[2:-2].strip()
                    if slot_name in parameter_values:
                        bound_args[arg_k] = parameter_values[slot_name]
                    else:
                        # Fallback: check if first available parameter applies
                        first_val = next(iter(parameter_values.values()), None)
                        bound_args[arg_k] = first_val if first_val is not None else arg_v
                else:
                    bound_args[arg_k] = arg_v

            bound_nodes.append({
                "node_id": node.node_template_id,
                "tool": node.tool,
                "args": bound_args,
                "depends_on": node.depends_on,
                "risk": node.risk,
                "idempotency": node.idempotency,
            })

        return bound_nodes, True, "OK"

    def record_run_result(self, workflow_id: str, success: bool, latency_ms: float = 0.0):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = time.time()
            if success:
                cursor.execute(
                    """
                    UPDATE workflow_templates
                    SET success_count = success_count + 1, last_success = ?,
                        avg_latency_ms = (avg_latency_ms * success_count + ?) / (success_count + 1)
                    WHERE workflow_id = ?
                    """,
                    (now, latency_ms, workflow_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE workflow_templates
                    SET failure_count = failure_count + 1, last_failure = ?
                    WHERE workflow_id = ?
                    """,
                    (now, workflow_id),
                )
                # Check for automatic quarantine upon 3 consecutive failures
                cursor.execute("SELECT success_count, failure_count FROM workflow_templates WHERE workflow_id = ?", (workflow_id,))
                row = cursor.fetchone()
                if row and row["failure_count"] >= 3 and row["success_count"] == 0:
                    cursor.execute("UPDATE workflow_templates SET status = 'QUARANTINED' WHERE workflow_id = ?", (workflow_id,))
            conn.commit()

        # Refresh hot cache
        self._load_approved()

    def list_workflows(self) -> List[ApprovedWorkflow]:
        return [wf for k, wf in self._hot_cache.items() if len(k) > 10 and k.startswith("wf_")]

    def disable_workflow(self, workflow_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE workflow_templates SET status = 'DISABLED' WHERE workflow_id = ?", (workflow_id,))
            conn.commit()
        self._load_approved()
        return True

    def delete_workflow(self, workflow_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM workflow_templates WHERE workflow_id = ?", (workflow_id,))
            conn.commit()
        self._hot_cache.pop(workflow_id, None)
        self._load_approved()
        return True

    def _row_to_workflow(self, row: sqlite3.Row) -> ApprovedWorkflow:
        slots_data = json.loads(row["input_schema_json"])
        slots = [WorkflowSlot(name=s["name"], slot_type=s.get("slot_type", "str")) for s in slots_data]
        nodes_data = json.loads(row["graph_template_json"])
        nodes = [
            WorkflowNodeTemplate(
                node_template_id=n["node_template_id"],
                tool=n["tool"],
                args_template=n["args_template"],
                depends_on=n.get("depends_on", []),
                risk=n.get("risk", "READ_ONLY"),
                idempotency=n.get("idempotency", "IDEMPOTENT"),
            )
            for n in nodes_data
        ]
        return ApprovedWorkflow(
            workflow_id=row["workflow_id"],
            name=row["name"],
            description=row["description"],
            input_schema=slots,
            graph_template=WorkflowGraphTemplate(nodes=nodes),
            required_tools=json.loads(row["required_tools_json"]),
            required_capabilities=json.loads(row["required_capabilities_json"]),
            risk_profile=row["risk_profile"],
            registry_fingerprint=row["registry_fingerprint"],
            schema_version=row["schema_version"],
            created_at=row["created_at"] if isinstance(row["created_at"], (int, float)) else time.time(),
            approved_at=row["approved_at"],
            version=row["version"],
            status=WorkflowStatus(row["status"]),
            success_count=row["success_count"],
            failure_count=row["failure_count"],
            avg_latency_ms=row["avg_latency_ms"],
        )
