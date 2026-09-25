import pytest
from jarvis.core.stt.prefix_consensus import PrefixConsensus, TranscriptView
from jarvis.memory.search.ranking import reciprocal_rank_fusion
from jarvis.core.planner.topology import Step, validate_topology


# =====================================================================
# 1. PrefixConsensus Tests (Research Section 14)
# =====================================================================

def test_prefix_consensus_init():
    with pytest.raises(ValueError, match="At least two"):
        PrefixConsensus(agreement=1)
    pc = PrefixConsensus(agreement=2)
    assert pc.agreement == 2
    assert pc.view.stable == ""
    assert pc.view.final is False


def test_prefix_consensus_start():
    pc = PrefixConsensus(agreement=2)
    with pytest.raises(ValueError, match="turn ID is required"):
        pc.start("")
    pc.start("turn_101")
    assert pc.turn_id == "turn_101"
    assert pc.view.turn_id == "turn_101"


def test_prefix_consensus_agreement_and_stability():
    pc = PrefixConsensus(agreement=2)
    pc.start("turn_1")

    # First observation - len(history) is 1, not yet reached agreement count 2
    v1 = pc.update("turn_1", 1, "open chrome and search")
    assert v1.stable == ""
    assert v1.unstable == "open chrome and search"

    # Repeated or out-of-order sequence ignored
    v_dup = pc.update("turn_1", 1, "open chrome and search")
    assert v_dup.stable == ""

    # Second observation matching prefix "open chrome"
    v2 = pc.update("turn_1", 2, "open chrome and find python docs")
    assert v2.stable == "open chrome and"
    assert v2.unstable == "find python docs"
    assert v2.revision >= 1

    # Third observation continuing
    v3 = pc.update("turn_1", 3, "open chrome and find python documentation")
    assert v3.stable == "open chrome and find python"
    assert v3.unstable == "documentation"


def test_prefix_consensus_contradiction_invalidation():
    pc = PrefixConsensus(agreement=2)
    pc.start("turn_2")

    pc.update("turn_2", 1, "open chrome browser")
    pc.update("turn_2", 2, "open chrome browser please")
    assert pc.view.stable == "open chrome browser"

    # User corrected themselves / speech revised: "open firefox instead"
    # Doesn't match prior stable tokens -> history cleared
    v_rev = pc.update("turn_2", 3, "open firefox instead")
    # History was cleared, so stable is temporarily reset until 2 new matching observations
    assert v_rev.stable == ""
    assert v_rev.unstable == "open firefox instead"


def test_prefix_consensus_finish():
    pc = PrefixConsensus(agreement=2)
    pc.start("turn_3")
    pc.update("turn_3", 1, "open telegram")
    pc.update("turn_3", 2, "open telegram")

    # Authoritative final transcript
    fin = pc.finish("turn_3", "open telegram actually don't")
    assert fin.final is True
    assert fin.stable == "open telegram actually don't"
    assert fin.unstable == ""

    # Late updates on finalized turn are ignored
    late = pc.update("turn_3", 3, "something else")
    assert late.final is True
    assert late.stable == "open telegram actually don't"

    # Wrong turn finish raises ValueError
    with pytest.raises(ValueError, match="Wrong turn"):
        pc.finish("wrong_turn", "text")

    # Second finish on finalized turn raises ValueError
    with pytest.raises(ValueError, match="already finalized"):
        pc.finish("turn_3", "duplicate finish")


# =====================================================================
# 2. Reciprocal Rank Fusion Tests (Research Section 14)
# =====================================================================

def test_rrf_validation():
    with pytest.raises(ValueError, match="k must be positive"):
        reciprocal_rank_fusion([["doc1"]], k=0)


def test_rrf_scoring_and_deduplication():
    # Two rankings:
    # R1: docA, docB, docC
    # R2: docB, docA, docD
    r1 = ["docA", "docB", "docC", "docA"]  # duplicate within rank should be handled cleanly
    r2 = ["docB", "docA", "docD"]

    fused = reciprocal_rank_fusion([r1, r2], k=60)
    # docA rank in r1 is 1 (score 1/61), in r2 is 2 (score 1/62) -> sum = 1/61 + 1/62
    # docB rank in r1 is 2 (score 1/62), in r2 is 1 (score 1/61) -> sum = 1/61 + 1/62
    # Ties broken alphabetically: docA before docB
    assert len(fused) == 4
    doc_ids = [item[0] for item in fused]
    assert doc_ids[:2] == ["docA", "docB"]
    assert doc_ids[2] in ("docC", "docD")
    assert fused[0][1] == pytest.approx(1.0 / 61.0 + 1.0 / 62.0)


# =====================================================================
# 3. Topology Validation Tests (Research Section 14)
# =====================================================================

def test_validate_topology_valid_dag():
    allowed = {"read_file", "process_text", "write_output"}
    steps = [
        Step(id="s1", tool="read_file"),
        Step(id="s2", tool="process_text", depends_on=("s1",)),
        Step(id="s3", tool="write_output", depends_on=("s2",)),
    ]
    order = validate_topology(steps, allowed_tools=allowed, max_nodes=32)
    assert order == ["s1", "s2", "s3"]


def test_validate_topology_branching_dag():
    allowed = {"tool_a", "tool_b", "tool_c", "tool_d"}
    steps = [
        Step(id="s1", tool="tool_a"),
        Step(id="s2", tool="tool_b", depends_on=("s1",)),
        Step(id="s3", tool="tool_c", depends_on=("s1",)),
        Step(id="s4", tool="tool_d", depends_on=("s2", "s3")),
    ]
    order = validate_topology(steps, allowed_tools=allowed)
    assert len(order) == 4
    assert order[0] == "s1"
    assert order[-1] == "s4"
    assert "s2" in order[1:3] and "s3" in order[1:3]


def test_validate_topology_errors():
    allowed = {"tool_a", "tool_b"}

    # Empty steps
    with pytest.raises(ValueError, match="Invalid plan size"):
        validate_topology([], allowed)

    # Exceeding max nodes
    with pytest.raises(ValueError, match="Invalid plan size"):
        validate_topology([Step(id=f"s{i}", tool="tool_a") for i in range(10)], allowed, max_nodes=5)

    # Duplicate IDs
    with pytest.raises(ValueError, match="Missing or duplicate"):
        validate_topology([Step(id="s1", tool="tool_a"), Step(id="s1", tool="tool_b")], allowed)

    # Empty ID
    with pytest.raises(ValueError, match="Missing or duplicate"):
        validate_topology([Step(id="", tool="tool_a")], allowed)

    # Unknown tool
    with pytest.raises(ValueError, match="Unknown tool"):
        validate_topology([Step(id="s1", tool="dangerous_shell")], allowed)

    # Duplicate dependency
    with pytest.raises(ValueError, match="Duplicate dependency"):
        validate_topology([Step(id="s1", tool="tool_a"), Step(id="s2", tool="tool_b", depends_on=("s1", "s1"))], allowed)

    # Self dependency
    with pytest.raises(ValueError, match="Invalid dependency"):
        validate_topology([Step(id="s1", tool="tool_a", depends_on=("s1",))], allowed)

    # Missing parent dependency
    with pytest.raises(ValueError, match="Invalid dependency"):
        validate_topology([Step(id="s1", tool="tool_a", depends_on=("s999",))], allowed)

    # Cyclic plan
    with pytest.raises(ValueError, match="Cyclic plan"):
        validate_topology([
            Step(id="s1", tool="tool_a", depends_on=("s2",)),
            Step(id="s2", tool="tool_b", depends_on=("s1",)),
        ], allowed)
