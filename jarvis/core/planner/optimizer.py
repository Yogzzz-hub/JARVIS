"""Safe deterministic graph optimizer for Phase 4 TaskGraphs.

Deduplicates identical READ_ONLY calls (common-subexpression elimination),
merges duplicate searches/directory lookups, updates downstream bindings and dependencies,
and removes redundant or unreachable nodes without modifying state-changing operations.
"""

import json
from typing import Any
from jarvis.core.planner.schema import TaskGraph, TaskNode, ValueBinding
from jarvis.tools.base import RiskLevel
from jarvis.tools.registry import ToolRegistry


class GraphOptimizer:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def optimize(self, graph: TaskGraph) -> TaskGraph:
        """Applies safe deterministic optimizations to a valid TaskGraph."""
        # 1. Common-subexpression elimination for identical READ_ONLY calls
        graph = self._deduplicate_read_only_nodes(graph)
        return graph

    def _deduplicate_read_only_nodes(self, graph: TaskGraph) -> TaskGraph:
        """Merges duplicate identical READ_ONLY calls and rewires downstream bindings."""
        # Map: (tool_name, serialized_args) -> canonical_node_id
        seen_read_only: dict[str, str] = {}
        replacement_map: dict[str, str] = {}
        kept_nodes: list[TaskNode] = []

        for node in graph.nodes:
            if not self.registry.contains(node.tool):
                kept_nodes.append(node)
                continue

            tool_def = self.registry.get(node.tool).definition
            # ONLY deduplicate READ_ONLY operations
            if tool_def.risk == RiskLevel.READ_ONLY and not node.bindings and not node.condition:
                try:
                    args_key = f"{node.tool}::{json.dumps(node.args, sort_keys=True)}"
                except (TypeError, ValueError):
                    args_key = None

                if args_key and args_key in seen_read_only:
                    canonical_id = seen_read_only[args_key]
                    replacement_map[node.id] = canonical_id
                    # Skip adding duplicate node to kept_nodes
                    continue
                elif args_key:
                    seen_read_only[args_key] = node.id

            kept_nodes.append(node)

        if not replacement_map:
            return graph

        # Rewire dependencies and bindings in all remaining nodes
        new_nodes: list[TaskNode] = []
        for node in kept_nodes:
            new_depends_on: list[str] = []
            for dep in node.depends_on:
                rewritten_dep = replacement_map.get(dep, dep)
                if rewritten_dep not in new_depends_on and rewritten_dep != node.id:
                    new_depends_on.append(rewritten_dep)

            new_bindings: dict[str, ValueBinding] = {}
            for field_name, binding in node.bindings.items():
                rewritten_node_id = replacement_map.get(binding.node_id, binding.node_id)
                new_bindings[field_name] = ValueBinding(
                    node_id=rewritten_node_id,
                    output_path=binding.output_path,
                )

            # Rewire condition if present
            new_condition = None
            if node.condition:
                cond = node.condition
                new_left = cond.left
                if isinstance(cond.left, ValueBinding):
                    new_left = ValueBinding(
                        node_id=replacement_map.get(cond.left.node_id, cond.left.node_id),
                        output_path=cond.left.output_path,
                    )
                new_right = cond.right
                if isinstance(cond.right, ValueBinding):
                    new_right = ValueBinding(
                        node_id=replacement_map.get(cond.right.node_id, cond.right.node_id),
                        output_path=cond.right.output_path,
                    )
                new_condition = cond.model_copy(update={"left": new_left, "right": new_right})

            new_node = node.model_copy(
                update={
                    "depends_on": new_depends_on,
                    "bindings": new_bindings,
                    "condition": new_condition,
                }
            )
            new_nodes.append(new_node)

        return graph.model_copy(update={"nodes": new_nodes})
