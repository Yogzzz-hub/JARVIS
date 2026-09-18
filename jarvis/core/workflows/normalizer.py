"""DAG graph normalizer extracting reusable templates from concrete execution graphs."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Tuple
from jarvis.core.workflows.models import WorkflowGraphTemplate, WorkflowNodeTemplate, WorkflowSlot


class WorkflowNormalizer:
    """
    Normalizes concrete execution graphs into parameterized reusable templates.
    Strips non-essential runtime artifacts (UUIDs, timestamps, concrete file paths).
    """

    @staticmethod
    def normalize_graph(nodes_data: List[Dict[str, Any]]) -> Tuple[WorkflowGraphTemplate, List[WorkflowSlot]]:
        """
        Takes executed node dictionaries and generates a normalized WorkflowGraphTemplate
        and a list of discovered variable slots.
        """
        normalized_nodes: List[WorkflowNodeTemplate] = []
        slots: List[WorkflowSlot] = []
        slot_names_seen = set()

        for idx, node in enumerate(nodes_data):
            tool_name = node.get("tool", "unknown_tool")
            raw_args = dict(node.get("args", {}))
            depends_on = node.get("depends_on", [])
            risk = node.get("risk", "READ_ONLY")

            norm_args: Dict[str, Any] = {}
            for arg_k, arg_v in raw_args.items():
                if isinstance(arg_v, str) and (":" in arg_v or "/" in arg_v or "\\" in arg_v):
                    # File or folder path -> parameterize into slot
                    slot_name = f"{arg_k}_{idx}"
                    if slot_name not in slot_names_seen:
                        slots.append(WorkflowSlot(name=slot_name, slot_type="Path", description=f"Path parameter for {tool_name}"))
                        slot_names_seen.add(slot_name)
                    norm_args[arg_k] = f"{{{{{slot_name}}}}}"
                else:
                    norm_args[arg_k] = arg_v

            template_node_id = f"node_{idx}"
            norm_deps = [f"node_{d}" if isinstance(d, int) else str(d) for d in depends_on]

            normalized_nodes.append(
                WorkflowNodeTemplate(
                    node_template_id=template_node_id,
                    tool=tool_name,
                    args_template=norm_args,
                    depends_on=norm_deps,
                    risk=risk,
                    idempotency=node.get("idempotency", "IDEMPOTENT"),
                )
            )

        # Compute deterministic graph shape hash
        structure_repr = [
            {"tool": n.tool, "deps": sorted(n.depends_on), "risk": n.risk}
            for n in normalized_nodes
        ]
        shape_hash = hashlib.sha256(json.dumps(structure_repr, sort_keys=True).encode("utf-8")).hexdigest()[:16]

        template = WorkflowGraphTemplate(nodes=normalized_nodes, shape_hash=shape_hash)
        return template, slots
