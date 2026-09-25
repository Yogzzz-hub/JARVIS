"""Untouched Contextual Holdout Generalization Test Suite (Specs 93, 94, 95).

Tests novel, completely unseen entities, phrasings, and domains NOT present in prompt examples:
- Software: PostgreSQL, FastAPI, Tailwind CSS, DuckDB, Redis, FFmpeg
- Applications: Audacity, OBS Studio, Blender, Inkscape
- AI Models: DeepSeek Coder, Phi-3, Mistral Nemo, Llama 3.3
- Contacts: Priya, Vikram Sharma, Ananya
- Novel Files: quarterly_tax_report_2025.xlsx, quantum_computing_survey.pdf, deep_learning_benchmark.csv
- Strict constraint: Wrong Contextual Consequential Actions = 0.
"""

import pytest
from pathlib import Path
from jarvis.core.memory.working import BoundedWorkingMemory
from jarvis.core.context.resolver import ReferenceResolver
from jarvis.core.context.followup_detector import FollowupDetector
from jarvis.core.context.entity_extractor import EntityExtractor
from jarvis.core.context.models import (
    ApplicationResourceRef,
    ContactResourceRef,
    DraftResourceRef,
    EntityRef,
    EntityType,
    FileResourceRef,
    FollowupType,
    PendingClarification,
    PendingConfirmation,
    ReferenceConfidence,
    ResultSet,
    TopicRef,
)


@pytest.fixture
def wm():
    return BoundedWorkingMemory()


@pytest.fixture
def resolver(wm):
    return ReferenceResolver(working_memory=wm)


# ==============================================================================
# HOLDOUT 1: KNOWLEDGE -> ACTION ON UNSEEN SOFTWARE ENTITIES (Spec 95)
# ==============================================================================

def test_holdout_postgresql_knowledge_to_install(wm, resolver):
    """Novel Entity: PostgreSQL. User asks explanation -> user says 'Install it.'"""
    entities = EntityExtractor.extract_from_user_query("What is PostgreSQL used for?")
    assert len(entities) >= 1
    assert any("postgres" in e.canonical_name.lower() for e in entities)
    pg_entity = entities[0]
    wm.push_topic(pg_entity.canonical_name, entity_type=EntityType.SOFTWARE)
    wm.record_assistant_answer("PostgreSQL is an advanced open-source relational database.", entities=entities)

    f_res = FollowupDetector.detect("Install it.")
    assert f_res.followup_type in (FollowupType.PRONOUN_REFERENCE, FollowupType.ACTION_ON_TOPIC)

    resolution = resolver.resolve_for_slot("it", expected_type="software", utterance="Install it.")
    assert resolution.confidence == ReferenceConfidence.HIGH
    assert "postgres" in resolution.target.lower()
    assert resolution.target_type in ("PACKAGE", "SOFTWARE")


def test_holdout_fastapi_knowledge_to_version_check(wm, resolver):
    """Novel Entity: FastAPI. User asks -> 'Check its version.'"""
    entities = EntityExtractor.extract_from_user_query("Explain FastAPI framework.")
    assert len(entities) >= 1
    wm.push_topic(entities[0].canonical_name, entity_type=EntityType.SOFTWARE)

    res = resolver.resolve_for_slot("it", expected_type="software", utterance="Check its version.")
    assert res.confidence == ReferenceConfidence.HIGH
    assert "fastapi" in res.target.lower()


def test_holdout_duckdb_knowledge_to_install(wm, resolver):
    """Novel Entity: DuckDB. Ask explanation -> 'Install it.'"""
    entities = EntityExtractor.extract_from_user_query("Tell me about DuckDB.")
    assert len(entities) >= 1
    wm.push_topic(entities[0].canonical_name, entity_type=EntityType.SOFTWARE)

    res = resolver.resolve_for_slot("it", expected_type="package", utterance="Install it.")
    assert res.confidence == ReferenceConfidence.HIGH
    assert "duckdb" in res.target.lower()


# ==============================================================================
# HOLDOUT 2: KNOWLEDGE -> ACTION ON UNSEEN APPLICATION ENTITIES (Spec 95)
# ==============================================================================

def test_holdout_obs_studio_knowledge_to_open(wm, resolver):
    """Novel App: OBS Studio. Explain -> 'Open it.'"""
    wm.push_topic("OBS Studio", entity_type=EntityType.APPLICATION)
    wm.add_entity(EntityRef(entity_id="obs", canonical_name="OBS Studio", display_name="OBS Studio", entity_type=EntityType.APPLICATION))

    res = resolver.resolve_for_slot("it", expected_type="application", utterance="Open it.")
    assert res.confidence == ReferenceConfidence.HIGH
    assert res.target == "OBS Studio"


def test_holdout_blender_check_installed_then_where(wm, resolver):
    """Novel App: Blender. 'Is it installed?' -> 'Where is it installed?'"""
    wm.push_topic("Blender", entity_type=EntityType.APPLICATION)
    wm.add_entity(EntityRef(entity_id="blender", canonical_name="Blender", display_name="Blender 3D", entity_type=EntityType.APPLICATION))

    res1 = resolver.resolve_for_slot("it", expected_type="application", utterance="Is it installed?")
    assert res1.target in ("Blender", "Blender 3D")

    res2 = resolver.resolve_for_slot("it", expected_type="application", utterance="Where is it installed?")
    assert res2.target in ("Blender", "Blender 3D")


# ==============================================================================
# HOLDOUT 3: UNSEEN AI MODEL CONNECTIONS (Spec 84, 95)
# ==============================================================================

def test_holdout_deepseek_coder_can_this_run_locally(wm, resolver):
    """Novel Model: DeepSeek Coder. 'What is DeepSeek Coder?' -> 'Can this run locally?'"""
    wm.push_topic("DeepSeek Coder", entity_type=EntityType.MODEL)
    wm.add_entity(EntityRef(entity_id="deepseek", canonical_name="DeepSeek Coder", display_name="DeepSeek Coder 33B", entity_type=EntityType.MODEL))

    res = resolver.resolve_for_slot("this", expected_type="model", utterance="Can this run locally?")
    assert res.confidence == ReferenceConfidence.HIGH
    assert "DeepSeek" in res.target


def test_holdout_mistral_nemo_download(wm, resolver):
    """Novel Model: Mistral Nemo. 'Explain Mistral Nemo.' -> 'Download it.'"""
    wm.push_topic("Mistral Nemo", entity_type=EntityType.MODEL)
    wm.add_entity(EntityRef(entity_id="nemo", canonical_name="Mistral Nemo", display_name="Mistral Nemo 12B", entity_type=EntityType.MODEL))

    res = resolver.resolve_for_slot("it", expected_type="model", utterance="Download it.")
    assert res.confidence == ReferenceConfidence.HIGH
    assert "Mistral" in res.target or "Nemo" in res.target


# ==============================================================================
# HOLDOUT 4: UNSEEN FILE AND FOLDER CONTINUITY PIPELINE (Spec 66, 88)
# ==============================================================================

def test_holdout_novel_files_pipeline(wm, resolver):
    """
    Search returns:
    1. quarterly_tax_report_2025.xlsx
    2. quantum_computing_survey.pdf
    3. deep_learning_benchmark.csv
    -> 'Open the third one.' -> 'Where is it?' -> 'Open its folder.' -> 'Send it to my phone.'
    """
    f1 = "D:/Work/Finances/quarterly_tax_report_2025.xlsx"
    f2 = "D:/Work/Research/quantum_computing_survey.pdf"
    f3 = "D:/Work/Benchmarks/deep_learning_benchmark.csv"
    wm.record_search_results("Find my data files", [f1, f2, f3])

    # 1. "Open the third one."
    r1 = resolver.resolve_for_slot("third one", expected_type="file", utterance="Open the third one.")
    assert r1.confidence == ReferenceConfidence.HIGH
    assert Path(r1.target) == Path(f3)

    # File opened
    wm.record_file_opened(f3)

    # 2. "Where is it?"
    r2 = resolver.resolve_for_slot("it", expected_type="file", utterance="Where is it?")
    assert Path(r2.target) == Path(f3)

    # 3. "Open its folder."
    r3 = resolver.resolve_for_slot("its folder", expected_type="folder", utterance="Open its folder.")
    assert "Benchmarks" in r3.target or "benchmarks" in r3.target.lower()

    # 4. "Send it to my phone." (two references resolved independently)
    file_ref = resolver.resolve_for_slot("it", expected_type="file", utterance="Send it to my phone.")
    device_ref = resolver.resolve_for_slot("my phone", expected_type="device", utterance="Send it to my phone.")
    assert Path(file_ref.target) == Path(f3)
    assert device_ref.target == "phone"
    assert device_ref.target_type == "DEVICE"


# ==============================================================================
# HOLDOUT 5: UNSEEN AMBIGUITY PRECISION (ZERO GUESSING) (Spec 40, 69)
# ==============================================================================

def test_holdout_novel_software_ambiguity_must_clarify(wm, resolver):
    """'What are PostgreSQL and Redis?' -> 'Install it.' -> MUST clarify with names."""
    e_pg = EntityRef(entity_id="pg", canonical_name="PostgreSQL", display_name="PostgreSQL", entity_type=EntityType.SOFTWARE, salience=0.92)
    e_red = EntityRef(entity_id="redis", canonical_name="Redis", display_name="Redis", entity_type=EntityType.SOFTWARE, salience=0.91)
    wm.add_entity(e_pg)
    wm.add_entity(e_red)

    res = resolver.resolve_for_slot("it", expected_type="software", utterance="Install it.")
    assert res.confidence == ReferenceConfidence.AMBIGUOUS
    assert res.target is None
    assert res.clarification_prompt is not None
    assert "PostgreSQL" in res.clarification_prompt
    assert "Redis" in res.clarification_prompt


def test_holdout_compare_then_install_second(wm, resolver):
    """'Compare Blender and Inkscape.' -> 'Install the second one.' -> Resolves Inkscape."""
    e_b = EntityRef(entity_id="blender", canonical_name="Blender", display_name="Blender", entity_type=EntityType.SOFTWARE)
    e_i = EntityRef(entity_id="inkscape", canonical_name="Inkscape", display_name="Inkscape", entity_type=EntityType.SOFTWARE)
    wm.add_entity(e_b)
    wm.add_entity(e_i)
    wm.set_result_set(ResultSet(result_set_id="design_tools", query="Blender vs Inkscape", resources=[e_b, e_i]))

    res = resolver.resolve_for_slot("second one", expected_type="software", utterance="Install the second one.")
    assert res.confidence == ReferenceConfidence.HIGH
    assert res.target == "Inkscape"


# ==============================================================================
# HOLDOUT 6: CROSS-DOMAIN CONTINUITY & PURGING NOISE (Spec 70, 71)
# ==============================================================================

def test_holdout_cross_domain_noise_type_filtering(wm, resolver):
    """
    Turn 1: User reads email from Priya.
    Turn 2: User sets volume to 80.
    Turn 3: User opens tax_report.xlsx.
    Turn 4: User discusses Tailwind CSS (Software).
    Turn 5: User says 'Install it.'
    Expected: Tailwind CSS (NOT tax_report, Priya, or volume).
    """
    priya = ContactResourceRef(resource_id="c_priya", name="Priya")
    wm.set_current_contact(priya)

    wm.record_file_opened("C:/Users/ashok/Documents/tax_report.xlsx")

    wm.push_topic("Tailwind CSS", entity_type=EntityType.SOFTWARE)
    wm.add_entity(EntityRef(entity_id="tailwind", canonical_name="Tailwind CSS", display_name="Tailwind CSS", entity_type=EntityType.SOFTWARE, salience=0.98))

    res = resolver.resolve_for_slot("it", expected_type="software", utterance="Install it.")
    assert res.confidence == ReferenceConfidence.HIGH
    assert res.target == "Tailwind CSS"
    assert "tax_report" not in res.target
    assert "Priya" not in res.target


# ==============================================================================
# HOLDOUT 7: ZERO WRONG CONSEQUENTIAL ACTIONS INVARIANT (Spec 41, 94)
# ==============================================================================

def test_holdout_consequential_action_safety_threshold(wm, resolver):
    """
    Consequential action: 'Delete it.' with multiple ambiguous candidates.
    Invariant: Must NEVER execute or pick a guess; must be AMBIGUOUS / require clarification.
    """
    f_a = "C:/tmp/draft_notes.txt"
    f_b = "C:/tmp/final_contract.txt"
    wm.record_search_results("Find txt files", [f_a, f_b])

    # Consequential resolution for delete
    res = resolver.resolve_for_slot("it", expected_type="file", utterance="Delete it.", is_consequential=True)
    assert not res.is_reliable_for_action()
    assert res.confidence in (ReferenceConfidence.AMBIGUOUS, ReferenceConfidence.LOW)
