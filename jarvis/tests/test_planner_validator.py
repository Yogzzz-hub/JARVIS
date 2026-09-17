"""Tests for TaskGraph schema, GraphValidator, and GraphOptimizer (Phase 4)."""

import pytest
from jarvis.core.planner.schema import (
    ConditionDSL,
    ConditionOperator,
    FailurePolicy,
    TaskGraph,
    TaskNode,
    ValueBinding,
)
from jarvis.core.planner.validator import GraphValidator
from jarvis.core.planner.optimizer import GraphOptimizer
from jarvis.tools.system.app_resolver import AppResolver
from jarvis.tools.system.native import create_tools
from jarvis.tools.registry import ToolRegistry


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.discover(create_tools(AppResolver(), {}))
    reg.finalize()
    return reg



@pytest.fixture
def validator(registry):
    return GraphValidator(registry=registry, max_nodes=20, max_depth=8, max_fan_out=8)


def test_valid_task_graph_two_step(registry, validator):
    # n1: find_file -> n2: open_file
    graph = TaskGraph(
        goal="Find and open NLP PDF",
        nodes=[
            TaskNode(
                id="n1",
                tool="find_file",
                args={"query": "NLP", "type_hint": "pdf"},
                description="Search for NLP PDF",
            ),
            TaskNode(
                id="n2",
                tool="open_file",
                depends_on=["n1"],
                bindings={"path": ValueBinding(node_id="n1", output_path="results[0].path")},
                description="Open found PDF",
            ),
        ],
    )
    result = validator.validate(graph)
    assert result.is_valid, [f"{e.code}: {e.message}" for e in result.errors]
    assert result.topological_order == ["n1", "n2"]
    assert result.depth == 2


def test_validator_rejects_duplicate_node_ids(validator):
    graph = TaskGraph(
        goal="Duplicate IDs test",
        nodes=[
            TaskNode(id="n1", tool="find_file", args={"query": "A"}),
            TaskNode(id="n1", tool="find_file", args={"query": "B"}),
        ],
    )
    result = validator.validate(graph)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "DUPLICATE_NODE_ID" in codes


def test_validator_rejects_unknown_tool(validator):
    graph = TaskGraph(
        goal="Unknown tool test",
        nodes=[
            TaskNode(id="n1", tool="delete_everything", args={}),
        ],
    )
    result = validator.validate(graph)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "UNKNOWN_TOOL" in codes


def test_validator_rejects_invalid_node_id_format():
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        TaskNode(id="step_one", tool="find_file", args={"query": "A"})



def test_validator_rejects_missing_required_argument(validator):
    # find_file requires 'query'
    graph = TaskGraph(
        goal="Missing query argument",
        nodes=[
            TaskNode(id="n1", tool="find_file", args={}),
        ],
    )
    result = validator.validate(graph)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "MISSING_ARGUMENT" in codes


def test_validator_rejects_invalid_argument_name(validator):
    graph = TaskGraph(
        goal="Invalid arg name",
        nodes=[
            TaskNode(id="n1", tool="find_file", args={"query": "NLP", "invented_flag": True}),
        ],
    )
    result = validator.validate(graph)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "INVALID_ARGUMENT" in codes


def test_validator_rejects_cycle(validator):
    # n1 -> n2 -> n3 -> n1
    graph = TaskGraph(
        goal="Cycle test",
        nodes=[
            TaskNode(id="n1", tool="find_file", args={"query": "A"}, depends_on=["n3"]),
            TaskNode(id="n2", tool="find_file", args={"query": "B"}, depends_on=["n1"]),
            TaskNode(id="n3", tool="find_file", args={"query": "C"}, depends_on=["n2"]),
        ],
    )
    result = validator.validate(graph)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "GRAPH_CYCLE" in codes


def test_validator_rejects_self_dependency(validator):
    graph = TaskGraph(
        goal="Self dependency test",
        nodes=[
            TaskNode(id="n1", tool="find_file", args={"query": "A"}, depends_on=["n1"]),
        ],
    )
    result = validator.validate(graph)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "SELF_DEPENDENCY" in codes


def test_validator_rejects_forward_invalid_binding(validator):
    # n1 binds to n2, but n1 cannot consume future output of n2
    graph = TaskGraph(
        goal="Forward binding test",
        nodes=[
            TaskNode(
                id="n1",
                tool="open_file",
                depends_on=["n2"],
                bindings={"path": ValueBinding(node_id="n2", output_path="results[0].path")},
            ),
            TaskNode(id="n2", tool="find_file", args={"query": "NLP"}),
        ],
    )
    # Note: topological sort will place n2 before n1 because n1 depends on n2.
    # But if n1 does NOT depend on n2, it fails MISSING_DEPENDENCY_EDGE:
    graph_missing_edge = TaskGraph(
        goal="Missing dependency edge",
        nodes=[
            TaskNode(
                id="n1",
                tool="open_file",
                bindings={"path": ValueBinding(node_id="n2", output_path="results[0].path")},
            ),
            TaskNode(id="n2", tool="find_file", args={"query": "NLP"}),
        ],
    )
    res = validator.validate(graph_missing_edge)
    assert not res.is_valid
    assert "MISSING_DEPENDENCY_EDGE" in [e.code for e in res.errors]


def test_validator_rejects_invalid_output_path(validator):
    # upstream find_file has no 'nonexistent_field'
    graph = TaskGraph(
        goal="Invalid output path",
        nodes=[
            TaskNode(id="n1", tool="find_file", args={"query": "NLP"}),
            TaskNode(
                id="n2",
                tool="open_file",
                depends_on=["n1"],
                bindings={"path": ValueBinding(node_id="n1", output_path="nonexistent_field")},
            ),
        ],
    )
    result = validator.validate(graph)
    assert not result.is_valid
    assert "INVALID_OUTPUT_PATH" in [e.code for e in result.errors]


def test_validator_enforces_max_nodes(validator):
    nodes = [
        TaskNode(id=f"n{i}", tool="find_file", args={"query": f"doc_{i}"})
        for i in range(1, 25)
    ]
    graph = TaskGraph(goal="Over 20 nodes", nodes=nodes)
    result = validator.validate(graph)
    assert not result.is_valid
    assert "MAX_NODES_EXCEEDED" in [e.code for e in result.errors]


def test_validator_enforces_max_depth(validator):
    # Chain of 10 nodes (exceeding max_depth=8)
    nodes = []
    for i in range(1, 11):
        dep = [f"n{i-1}"] if i > 1 else []
        nodes.append(TaskNode(id=f"n{i}", tool="find_file", args={"query": f"item_{i}"}, depends_on=dep))
    graph = TaskGraph(goal="Depth over 8", nodes=nodes)
    result = validator.validate(graph)
    assert not result.is_valid
    assert "MAX_DEPTH_EXCEEDED" in [e.code for e in result.errors]


def test_validator_validates_condition_dsl(validator):
    # Valid condition
    graph = TaskGraph(
        goal="Conditional search",
        nodes=[
            TaskNode(id="n1", tool="find_file", args={"query": "NLP"}),
            TaskNode(
                id="n2",
                tool="open_file",
                depends_on=["n1"],
                bindings={"path": ValueBinding(node_id="n1", output_path="results[0].path")},
                condition=ConditionDSL(
                    left=ValueBinding(node_id="n1", output_path="is_ambiguous"),
                    operator=ConditionOperator.IS_FALSE,
                ),
            ),
        ],
    )
    result = validator.validate(graph)
    assert result.is_valid, [f"{e.code}: {e.message}" for e in result.errors]


def test_graph_optimizer_deduplicates_read_only(registry):
    optimizer = GraphOptimizer(registry)
    # n1 and n2 are identical find_file calls
    # n3 depends on n2
    graph = TaskGraph(
        goal="Duplicate search test",
        nodes=[
            TaskNode(id="n1", tool="find_file", args={"query": "NLP", "type_hint": "pdf"}),
            TaskNode(id="n2", tool="find_file", args={"query": "NLP", "type_hint": "pdf"}),
            TaskNode(
                id="n3",
                tool="open_file",
                depends_on=["n2"],
                bindings={"path": ValueBinding(node_id="n2", output_path="results[0].path")},
            ),
        ],
    )
    optimized = optimizer.optimize(graph)
    assert len(optimized.nodes) == 2
    remaining_ids = [n.id for n in optimized.nodes]
    assert "n1" in remaining_ids
    assert "n2" not in remaining_ids
    # n3 should now depend on n1 and bind to n1
    n3_node = next(n for n in optimized.nodes if n.id == "n3")
    assert n3_node.depends_on == ["n1"]
    assert n3_node.bindings["path"].node_id == "n1"
