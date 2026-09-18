"""Comprehensive unit and integration test suite for JARVIS EDGE Phase 12."""

import asyncio
import tempfile
import time
from pathlib import Path
import pytest

from jarvis.core.memory.models import (
    EpisodeRecord,
    MemoryCandidate,
    MemoryConfidence,
    MemoryItem,
    MemoryLayer,
    MemoryProvenance,
    MemoryQuery,
    MemorySourceType,
    MemoryStatus,
)
from jarvis.core.memory.privacy import (
    contains_sensitive_secret,
    filter_memory_candidate,
    is_trusted_memory_source,
)
from jarvis.core.memory.store import SQLiteMemoryStore
from jarvis.core.memory.working import BoundedWorkingMemory

from jarvis.core.context.models import (
    ContextPacket,
    OperationalMode,
    ProjectContext,
    ReferenceConfidence,
    ReferenceResolution,
)
from jarvis.core.context.resolver import ReferenceResolver
from jarvis.core.context.assembler import ContextAssembler

from jarvis.core.workflows.models import (
    ApprovedWorkflow,
    WorkflowCandidate,
    WorkflowGraphTemplate,
    WorkflowNodeTemplate,
    WorkflowSlot,
    WorkflowStatus,
)
from jarvis.core.workflows.normalizer import WorkflowNormalizer
from jarvis.core.workflows.learner import WorkflowLearner
from jarvis.core.workflows.library import WorkflowLibrary

from jarvis.core.router.adaptive import (
    AdaptiveRoutingPolicy,
    IMMUTABLE_SECURITY_PARAMETERS,
)
from jarvis.core.resources.governor import (
    ModelProfile,
    ModelRole,
    ResourceGovernor,
    SystemPriority,
)
from jarvis.core.prefetch.engine import PrefetchEngine
from jarvis.core.specialists.models import (
    MergedResult,
    SourceTrust,
    SpecialistFact,
    SpecialistResult,
    SpecialistType,
)
from jarvis.core.specialists.coordinator import (
    ResultMerger,
    SpecialistCoordinator,
)
from jarvis.core.knowledge.models import AccessPolicy, KnowledgeCollection
from jarvis.core.knowledge.engine import KnowledgeEngine
from jarvis.core.optimization.engine import OptimizationEngine, OptimizationProposal


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield Path(db_path)
    try:
        Path(db_path).unlink(missing_ok=True)
    except Exception:
        pass


# =====================================================================
# 1. MEMORY SUBSYSTEM TESTS
# =====================================================================

def test_memory_secret_filtering():
    """Verify that passwords, OTPs, and API keys are rejected from durable memory."""
    secrets = [
        "sk-proj-1234567890abcdefghijklmnop",
        "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
        "SecretPassword!123",
        "839201",  # 6-digit OTP
        "AIzaSyD-1234567890abcdefghijklmnopq",
    ]
    for s in secrets:
        assert contains_sensitive_secret(s) is True
        cand = MemoryCandidate(
            candidate_id="c1",
            layer=MemoryLayer.SEMANTIC,
            kind="token",
            key="api_key",
            value=s,
            source_type=MemorySourceType.USER_EXPLICIT,
        )
        approved, reason = filter_memory_candidate(cand)
        assert approved is False
        assert "secret" in reason.lower()


def test_memory_untrusted_source_rejection():
    """Verify that external content (emails, webpages) cannot become durable user memory."""
    cand = MemoryCandidate(
        candidate_id="c2",
        layer=MemoryLayer.PREFERENCE,
        kind="browser",
        key="preferred_browser",
        value="Chrome",
        source_type=MemorySourceType.UNTRUSTED_EXTERNAL_CONTENT,
        source_reference="email_from_spammer.html",
    )
    approved, reason = filter_memory_candidate(cand)
    assert approved is False
    assert "untrusted" in reason.lower()


def test_memory_store_structured_and_fts(temp_db):
    """Verify structured exact lookup and FTS5 search in SQLite store."""
    store = SQLiteMemoryStore(temp_db)

    item1 = MemoryItem(
        memory_id="mem_1",
        layer=MemoryLayer.SEMANTIC,
        kind="folder_alias",
        key="study_folder",
        value="C:\\College\\NLP_Notes",
        provenance=MemoryProvenance(source_type=MemorySourceType.USER_EXPLICIT),
        confidence=MemoryConfidence.EXPLICIT,
    )
    store.store(item1)

    # 1. Exact lookup
    exact = store.get_exact("study_folder")
    assert exact is not None
    assert exact.value == "C:\\College\\NLP_Notes"

    # 2. FTS lexical search
    results = store.search_fts("NLP_Notes")
    assert len(results) >= 1
    assert results[0].item.memory_id == "mem_1"


def test_memory_superseding_conflict(temp_db):
    """Verify that new explicit preference supersedes older one without silent destruction."""
    store = SQLiteMemoryStore(temp_db)

    # Old preference
    item_old = MemoryItem(
        memory_id="pref_old",
        layer=MemoryLayer.PREFERENCE,
        kind="preferred_browser",
        key="default_browser",
        value="Chrome",
        provenance=MemoryProvenance(source_type=MemorySourceType.USER_EXPLICIT),
        confidence=MemoryConfidence.EXPLICIT,
    )
    store.store(item_old)

    # New preference supersedes old
    item_new = MemoryItem(
        memory_id="pref_new",
        layer=MemoryLayer.PREFERENCE,
        kind="preferred_browser",
        key="default_browser",
        value="Edge",
        provenance=MemoryProvenance(source_type=MemorySourceType.USER_CORRECTION),
        confidence=MemoryConfidence.VERIFIED,
    )
    store.store(item_new)

    # Current lookup returns new value
    current = store.get_exact("default_browser")
    assert current is not None
    assert current.value == "Edge"
    assert current.provenance.supersedes_id == "pref_old"

    # Old item remains recorded as SUPERSEDED for provenance
    old_fetched = store.get_by_id("pref_old")
    assert old_fetched is not None
    assert old_fetched.status == MemoryStatus.SUPERSEDED


def test_memory_ttl_decay(temp_db):
    """Verify TTL expiry enforcement."""
    store = SQLiteMemoryStore(temp_db)

    item = MemoryItem(
        memory_id="temp_mem",
        layer=MemoryLayer.SESSION,
        kind="temp_state",
        key="current_meeting",
        value="Sprint Review",
        provenance=MemoryProvenance(source_type=MemorySourceType.VERIFIED_ACTION),
        expires_at=time.time() - 10.0,  # Expired in past
    )
    store.store(item)

    # Exact lookup filters expired
    assert store.get_exact("current_meeting") is None

    # Cleanup job marks expired
    expired_count = store.cleanup_expired()
    assert expired_count >= 1
    assert store.get_by_id("temp_mem").status == MemoryStatus.EXPIRED


# =====================================================================
# 2. WORKING MEMORY & CONTEXT RESOLUTION TESTS
# =====================================================================

def test_working_memory_recency():
    """Verify working memory maintains bounded recent files and folders."""
    wm = BoundedWorkingMemory(max_items=5)
    for i in range(10):
        wm.record_file_opened(f"C:\\Files\\file_{i}.txt")

    assert wm.get_last_opened_file().endswith("file_9.txt")
    assert len(wm.get_recent_files()) == 5
    assert wm.get_last_selected_folder().endswith("Files")


def test_reference_resolution_pronoun():
    """Verify resolution of conversational pronouns ('open it again')."""
    wm = BoundedWorkingMemory()
    test_file = str(Path(__file__).resolve())
    wm.record_file_opened(test_file)

    resolver = ReferenceResolver(wm)
    res = resolver.resolve("open it again")

    assert res.confidence == ReferenceConfidence.HIGH
    assert res.referent == test_file
    assert res.referent_type == "FILE"


def test_reference_resolution_ordinal():
    """Verify ordinal reference resolution ('the second one')."""
    wm = BoundedWorkingMemory()
    wm.record_search_results([
        {"path": "C:\\Docs\\Report_1.pdf"},
        {"path": "C:\\Docs\\Report_2.pdf"},
        {"path": "C:\\Docs\\Report_3.pdf"},
    ])

    resolver = ReferenceResolver(wm)
    res = resolver.resolve("open the second one")

    assert res.confidence == ReferenceConfidence.HIGH
    assert res.referent == "C:\\Docs\\Report_2.pdf"


def test_reference_resolution_ambiguous():
    """Verify ambiguity detection on multiple candidate files without recency."""
    wm = BoundedWorkingMemory()
    wm.record_search_results([
        {"path": "C:\\Docs\\DocA.pdf"},
        {"path": "C:\\Docs\\DocB.pdf"},
    ])

    resolver = ReferenceResolver(wm)
    res = resolver.resolve("open it")

    assert res.confidence == ReferenceConfidence.AMBIGUOUS
    assert res.referent is None
    assert res.clarification_prompt is not None


def test_context_assembler_token_budget(temp_db):
    """Verify ContextAssembler adheres to strict token budget."""
    store = SQLiteMemoryStore(temp_db)
    wm = BoundedWorkingMemory()
    assembler = ContextAssembler(wm, store)

    packet = assembler.assemble("open the notes", is_deterministic_hint=False)
    assert packet.token_estimate <= 512
    assert "working_context" in packet.explanation or packet.token_estimate > 0


# =====================================================================
# 3. WORKFLOW LEARNING & LIBRARY TESTS
# =====================================================================

def test_workflow_normalization():
    """Verify graph normalization replaces concrete paths with typed slots."""
    nodes = [
        {"tool": "find_file", "args": {"query": "test.pdf"}, "risk": "READ_ONLY"},
        {"tool": "copy_file", "args": {"src": "C:\\Temp\\test.pdf", "dst": "C:\\Dest\\Folder"}, "risk": "EXTERNAL_EFFECT", "depends_on": [0]},
    ]
    template, slots = WorkflowNormalizer.normalize_graph(nodes)

    assert len(template.nodes) == 2
    assert len(slots) >= 1
    assert template.shape_hash != ""


def test_workflow_learning_threshold():
    """Verify that workflow candidate is proposed ONLY after reaching 3-run threshold."""
    learner = WorkflowLearner(threshold=3)
    nodes = [
        {"tool": "find_file", "args": {"query": "notes.pdf"}, "risk": "READ_ONLY"},
        {"tool": "create_dir", "args": {"path": "C:\\Notes\\NLP"}, "risk": "EXTERNAL_EFFECT"},
    ]

    # Run 1: No candidate proposal
    c1 = learner.observe_execution("prepare notes", nodes, "ep_1")
    assert c1 is None

    # Run 2: No candidate proposal
    c2 = learner.observe_execution("prepare notes", nodes, "ep_2")
    assert c2 is None

    # Run 3: Candidate proposal triggered!
    c3 = learner.observe_execution("prepare notes", nodes, "ep_3")
    assert c3 is not None
    assert c3.occurrence_count == 3
    assert "Prepare Notes" in c3.name_suggestion


def test_workflow_approval_and_execution_binding(temp_db):
    """Verify explicit workflow approval and parameter binding."""
    lib = WorkflowLibrary(temp_db)
    learner = WorkflowLearner(threshold=1)
    nodes = [
        {"tool": "find_file", "args": {"query": "nlp.pdf"}, "risk": "READ_ONLY"},
        {"tool": "copy_file", "args": {"src": "C:\\Input\\nlp.pdf", "dst": "C:\\Output\\nlp.pdf"}, "risk": "EXTERNAL_EFFECT"},
    ]
    cand = learner.observe_execution("study setup", nodes, "ep_1")

    # Explicit approval
    wf = lib.approve_candidate(cand, custom_name="Study Setup Workflow")
    assert wf.status == WorkflowStatus.APPROVED

    # Fast-path match
    matched = lib.find_matching_workflow("run study setup workflow")
    assert matched is not None
    assert matched.workflow_id == wf.workflow_id

    # Parameter binding
    bound_nodes, valid, err = lib.bind_parameters(matched, {"src_1": "C:\\NewInput\\nlp.pdf"})
    assert valid is True
    assert bound_nodes[1]["args"]["src"] == "C:\\NewInput\\nlp.pdf"


def test_workflow_quarantine_on_repeated_failures(temp_db):
    """Verify that repeated workflow failures trigger automatic quarantine."""
    lib = WorkflowLibrary(temp_db)
    learner = WorkflowLearner(threshold=1)
    cand = learner.observe_execution("failing job", [{"tool": "broken_tool", "args": {}}], "ep_fail")
    wf = lib.approve_candidate(cand)

    # 3 consecutive failures
    lib.record_run_result(wf.workflow_id, success=False)
    lib.record_run_result(wf.workflow_id, success=False)
    lib.record_run_result(wf.workflow_id, success=False)

    # Must be quarantined
    updated = lib.find_matching_workflow("failing job")
    assert updated is None  # Quarantined workflows are omitted from active match


# =====================================================================
# 4. ADAPTIVE ROUTER & RESOURCE GOVERNOR TESTS
# =====================================================================

def test_adaptive_router_immutable_security():
    """Verify that security parameters cannot be modified by optimizer."""
    adaptive = AdaptiveRoutingPolicy()
    for param in IMMUTABLE_SECURITY_PARAMETERS:
        valid, reason = adaptive.propose_threshold_tuning(param, 0.0, "attack")
        assert valid is False
        assert "REJECTED_BY_IMMUTABLE_SECURITY_POLICY" in reason


def test_resource_governor_eviction_under_pressure():
    """Verify idle models are evicted under memory pressure while STT is protected."""
    gov = ResourceGovernor(ram_pressure_threshold_pct=80.0, vram_pressure_threshold_mb=2048.0)

    stt_evicted = False
    vlm_evicted = False

    def evict_stt():
        nonlocal stt_evicted
        stt_evicted = True

    def evict_vlm():
        nonlocal vlm_evicted
        vlm_evicted = True

    gov.register_model(ModelProfile(model_id="whisper_base", role=ModelRole.STT, is_resident=True, evict_hook=evict_stt))
    gov.register_model(ModelProfile(model_id="qwen3_vl", role=ModelRole.VISION, is_resident=True, vram_mb=1200.0, evict_hook=evict_vlm))

    # Trigger high pressure
    evicted_ids = gov.evaluate_pressure_and_evict(current_ram_pct=85.0, current_vram_mb=3000.0)

    assert "qwen3_vl" in evicted_ids
    assert vlm_evicted is True
    # Active STT must NOT be evicted
    assert "whisper_base" not in evicted_ids
    assert stt_evicted is False


# =====================================================================
# 5. PREFETCH ENGINE TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_prefetch_read_only_invariant():
    """Verify speculation is strictly limited to READ_ONLY actions."""
    prefetch = PrefetchEngine()

    # Read-only speculation: ALLOWED
    async def fake_search():
        return ["file1.pdf"]

    ok, reason = await prefetch.schedule_prefetch("p1", "find_file", "notes", fake_search)
    assert ok is True

    # State-changing speculation: STRICTLY DISALLOWED
    async def fake_delete():
        return "deleted"

    ok_del, reason_del = await prefetch.schedule_prefetch("p2", "delete_file", "target", fake_delete)
    assert ok_del is False
    assert "SPECULATION_REJECTED" in reason_del


# =====================================================================
# 6. SPECIALIST COORDINATOR TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_specialist_parallel_fanout_and_merge():
    """Verify parallel execution of specialists and result merging."""
    coord = SpecialistCoordinator()

    async def file_task():
        return SpecialistResult(
            specialist=SpecialistType.FILE,
            status="SUCCESS",
            facts=[SpecialistFact("f1", SpecialistType.FILE, "Local file found: NLP.pdf", resource_ref="C:\\NLP.pdf")],
            resource_refs=["C:\\NLP.pdf"],
        )

    async def google_task():
        return SpecialistResult(
            specialist=SpecialistType.GOOGLE,
            status="SUCCESS",
            facts=[SpecialistFact("f2", SpecialistType.GOOGLE, "Meeting found: NLP Exam", trust=SourceTrust.AUTHENTICATED_PROVIDER_DATA)],
            resource_refs=["cal_event_123"],
        )

    tasks = [
        (SpecialistType.FILE, file_task),
        (SpecialistType.GOOGLE, google_task),
    ]

    merged = await coord.execute_parallel(tasks)
    assert merged.status == "SUCCESS"
    assert len(merged.facts) == 2
    assert "C:\\NLP.pdf" in merged.resource_refs
    assert "cal_event_123" in merged.resource_refs


@pytest.mark.asyncio
async def test_specialist_failure_isolation():
    """Verify one specialist failing does not crash or cancel others (PARTIAL result)."""
    coord = SpecialistCoordinator()

    async def success_task():
        return SpecialistResult(
            specialist=SpecialistType.FILE,
            status="SUCCESS",
            facts=[SpecialistFact("f1", SpecialistType.FILE, "Found local document")],
        )

    async def failing_task():
        raise RuntimeError("Cloud network timeout")

    tasks = [
        (SpecialistType.FILE, success_task),
        (SpecialistType.GOOGLE, failing_task),
    ]

    merged = await coord.execute_parallel(tasks)
    assert merged.status == "PARTIAL"
    assert len(merged.facts) == 1
    assert len(merged.discrepancies) == 1


# =====================================================================
# 7. KNOWLEDGE ENGINE & RAG TESTS
# =====================================================================

def test_knowledge_engine_rag_collection_and_search(temp_db):
    """Verify explicit RAG collection creation, document chunking, and search."""
    ke = KnowledgeEngine(temp_db)
    col = ke.create_collection("RIT Gate Docs", ["C:\\Projects\\RITGate"])

    doc_text = (
        "# System Architecture\n\n"
        "The RIT Gate system uses dual-channel ultrasonic sensors.\n\n"
        "# Calibration Rules\n\n"
        "Frequency must be set to 40kHz with temperature compensation.\n"
    )
    indexed_chunks = ke.index_document_text(col.collection_id, "C:\\Projects\\RITGate\\spec.md", doc_text)
    assert indexed_chunks >= 1

    # Search
    hits = ke.search("ultrasonic sensors", collection_name="RIT Gate Docs")
    assert len(hits) >= 1
    assert "ultrasonic" in hits[0].snippet.lower()
    assert hits[0].trust == "DATA_ONLY"


# =====================================================================
# 8. OPTIMIZATION ENGINE TESTS
# =====================================================================

def test_optimization_engine_offline_benchmark():
    """Verify proposal evaluation offline before applying."""
    adaptive = AdaptiveRoutingPolicy(fuzzy_score_cutoff=75.0)
    opt = OptimizationEngine(adaptive_router=adaptive)

    ok, reason, prop = opt.create_proposal("fuzzy_score_cutoff", 80.0, "Benchmark shows higher precision")
    assert ok is True

    # Offline benchmark evaluator
    def mock_evaluator(param, val):
        return {"accuracy_delta": 0.02, "wrong_actions": 0}

    bench_ok, _ = opt.benchmark_proposal_offline(prop.proposal_id, mock_evaluator)
    assert bench_ok is True
    assert prop.status == "BENCHMARKED"

    # Apply
    apply_ok, _ = opt.apply_proposal(prop.proposal_id)
    assert apply_ok is True
    assert adaptive.fuzzy_score_cutoff == 80.0
