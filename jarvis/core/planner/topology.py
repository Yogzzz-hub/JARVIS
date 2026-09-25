"""Task graph topology validation using Kahn's topological sort.

Implements the research-verified reference algorithm:
- Validates node count within bounded range (1 to max_nodes).
- Validates unique, non-empty step identifiers.
- Validates all tools against registered capability set.
- Detects duplicate dependencies and self-dependencies.
- Enforces strict acyclicity via Kahn's in-degree reduction.
- Returns verified topological execution order.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    """Immutable plan step representation for structural topology validation."""
    id: str
    tool: str
    depends_on: tuple[str, ...] = ()


def validate_topology(
    steps: list[Step], allowed_tools: set[str], max_nodes: int = 32
) -> list[str]:
    """Validate graph structure; argument and authority checks are separate."""
    if not 0 < len(steps) <= max_nodes:
        raise ValueError("Invalid plan size")
    ids = {step.id for step in steps}
    if len(ids) != len(steps) or "" in ids:
        raise ValueError("Missing or duplicate step IDs")
    outgoing: dict[str, list[str]] = {step.id: [] for step in steps}
    indegree: dict[str, int] = {}
    for step in steps:
        if step.tool not in allowed_tools:
            raise ValueError("Unknown tool")
        if len(set(step.depends_on)) != len(step.depends_on):
            raise ValueError("Duplicate dependency")
        indegree[step.id] = len(step.depends_on)
        for parent in step.depends_on:
            if parent not in ids or parent == step.id:
                raise ValueError("Invalid dependency")
            outgoing[parent].append(step.id)
    ready = deque(step.id for step in steps if indegree[step.id] == 0)
    order: list[str] = []
    while ready:
        node = ready.popleft()
        order.append(node)
        for child in outgoing[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if len(order) != len(steps):
        raise ValueError("Cyclic plan")
    return order
