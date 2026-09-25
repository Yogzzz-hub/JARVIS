"""Comprehensive Conversational Continuity Test Suite (Jarvis Edge Specs 65-72, 24-27, 42-44)."""

import pytest
from jarvis.core.memory.working import BoundedWorkingMemory
from jarvis.core.context.resolver import ReferenceResolver
from jarvis.core.context.followup_detector import FollowupDetector
from jarvis.core.context.entity_extractor import EntityExtractor
from jarvis.core.context.models import (
    ApplicationResourceRef,
    BrowserPageRef,
    ContactResourceRef,
    DraftResourceRef,
    EntityRef,
    EntityType,
    FileResourceRef,
    FolderResourceRef,
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
# 1. TOPIC REFERENCE CONTINUITY TEST SUITE (Section 65)
# ==============================================================================

def test_topic_reference_what_is_ollama_then_install_it(wm, resolver):
    """USER: 'What is Ollama?' -> 'Install it.' (Sections 1, 65)."""
    # 1. Turn 1: User asks "What is Ollama?"
    entities = EntityExtractor.extract_from_user_query("What is Ollama used for?")
    assert len(entities) >= 1
    assert entities[0].canonical_name.casefold() == "ollama"
    wm.push_topic("Ollama", entity_type=EntityType.SOFTWARE)
    wm.record_assistant_answer("Ollama is a local model runtime that lets you run LLMs locally.", entities=entities)

    assert wm.active_topic is not None
    assert wm.active_topic.canonical_name == "Ollama"

    # 2. Turn 2: User says "Install it."
    f_res = FollowupDetector.detect("Install it.")
    assert f_res.followup_type in (FollowupType.PRONOUN_REFERENCE, FollowupType.ACTION_ON_TOPIC)

    resolution = resolver.resolve_for_slot("it", expected_type="software", utterance="Install it.")
    assert resolution.confidence == ReferenceConfidence.HIGH
    assert resolution.target == "Ollama"
    assert "active_topic" in resolution.evidence or "type_compatible" in resolution.evidence


def test_topic_reference_what_is_docker_is_it_installed_open_it(wm, resolver):
    """USER: 'What is Docker?' -> 'Is it installed?' -> 'Open it.' (Section 65)."""
    wm.push_topic("Docker", entity_type=EntityType.SOFTWARE)
    wm.add_entity(EntityRef(entity_id="docker", canonical_name="Docker", display_name="Docker Desktop", entity_type=EntityType.SOFTWARE))

    # Turn 2: "Is it installed?"
    res1 = resolver.resolve_for_slot("it", expected_type="software", utterance="Is it installed?")
    assert res1.target == "Docker"

    # Turn 3: "Open it."
    res2 = resolver.resolve_for_slot("it", expected_type="application", utterance="Open it.")
    assert res2.target in ("Docker", "Docker Desktop")


def test_topic_reference_explain_vs_code_where_is_it_installed(wm, resolver):
    """USER: 'Explain VS Code.' -> 'Where is it installed?' (Section 65)."""
    entities = EntityExtractor.extract_from_user_query("Explain VS Code.")
    wm.push_topic("VS Code", entity_type=EntityType.SOFTWARE)
    wm.add_entity(EntityRef(entity_id="vscode", canonical_name="Visual Studio Code", display_name="VS Code", aliases=["vscode", "vs code"], entity_type=EntityType.APPLICATION))

    res = resolver.resolve_for_slot("it", expected_type="application", utterance="Where is it installed?")
    assert res.target in ("VS Code", "Visual Studio Code")


def test_topic_reference_compare_two_then_install_first(wm, resolver):
    """USER: 'Compare Ollama and LM Studio.' -> 'Install the first one.' (Section 65)."""
    e1 = EntityRef(entity_id="ollama", canonical_name="Ollama", display_name="Ollama", entity_type=EntityType.SOFTWARE)
    e2 = EntityRef(entity_id="lm_studio", canonical_name="LM Studio", display_name="LM Studio", entity_type=EntityType.SOFTWARE)
    wm.add_entity(e1)
    wm.add_entity(e2)
    wm.set_result_set(ResultSet(result_set_id="rs1", query="Compare Ollama and LM Studio", resources=[e1, e2]))

    res = resolver.resolve_for_slot("first one", expected_type="software", utterance="Install the first one.")
    assert res.confidence == ReferenceConfidence.HIGH
    assert res.target == "Ollama"


def test_topic_reference_what_is_qwen_can_ollama_run_it(wm, resolver):
    """USER: 'What is Qwen?' -> 'Can Ollama run it?' (Section 65, 84)."""
    wm.push_topic("Qwen", entity_type=EntityType.MODEL)
    wm.add_entity(EntityRef(entity_id="qwen", canonical_name="Qwen", display_name="Qwen 2.5", entity_type=EntityType.MODEL))

    res = resolver.resolve_for_slot("it", expected_type="model", utterance="Can Ollama run it?")
    assert res.target == "Qwen"


# ==============================================================================
# 2. FILE CONTINUITY TEST SUITE (Section 66)
# ==============================================================================

def test_file_continuity_list_pdfs_open_second_what_is_it_about_folder(wm, resolver):
    """
    USER: 'List my PDFs.' -> 'Open the second one.' -> 'Where is it?'
          -> 'What's it about?' -> 'Open its folder.'
    """
    # 1. Jarvis returns 3 PDFs in ResultSet
    pdf1 = "C:/Users/ashok/Documents/ML_Notes.pdf"
    pdf2 = "C:/Users/ashok/Documents/Assignment.pdf"
    pdf3 = "C:/Users/ashok/Documents/Research.pdf"
    wm.record_search_results("List my PDFs", [pdf1, pdf2, pdf3])

    # 2. "Open the second one."
    res_ord = resolver.resolve_for_slot("second one", expected_type="file", utterance="Open the second one.")
    assert res_ord.confidence == ReferenceConfidence.HIGH
    assert res_ord.target == pdf2

    # Jarvis opens Assignment.pdf
    from pathlib import Path
    wm.record_file_opened(pdf2)
    assert Path(wm.get_current_file()) == Path(pdf2)

    # 3. "Where is it?"
    res_path = resolver.resolve_for_slot("it", expected_type="file", utterance="Where is it?")
    assert Path(res_path.target) == Path(pdf2)

    # 4. "What's it about?"
    res_rag = resolver.resolve_for_slot("it", expected_type="document", utterance="What's it about?")
    assert Path(res_rag.target) == Path(pdf2)

    # 5. "Open its folder."
    res_folder = resolver.resolve_for_slot("its folder", expected_type="folder", utterance="Open its folder.")
    assert "Documents" in res_folder.target or "documents" in res_folder.target.lower()


def test_file_continuity_slot_refinement(wm):
    """USER: 'Find files about CNN.' -> 'Only PDFs.' -> 'Only from this week.' (Section 26)."""
    # Turn 1
    f_res = FollowupDetector.detect("Only PDFs.")
    assert f_res.followup_type == FollowupType.REFINEMENT
    assert "pdf" in f_res.target_hint.lower()

    # Turn 2
    f_res2 = FollowupDetector.detect("Only from this week.")
    assert f_res2.followup_type == FollowupType.REFINEMENT
    assert "week" in (f_res2.target_hint or "")


def test_file_search_failure_then_try_downloads(wm, resolver):
    """USER: 'Find assignment.' -> failure -> 'Try Downloads.' (Section 25)."""
    wm.record_action_failure(target="assignment", reason="FILE_NOT_FOUND")

    f_res = FollowupDetector.detect("Try Downloads.")
    assert f_res.followup_type in (FollowupType.REFINEMENT, FollowupType.CONTINUATION, FollowupType.ACTION_AFTER_FAILURE)
    assert f_res.target_hint.lower() == "downloads"

    # Last failure is preserved
    last_fail = wm.get_last_failure()
    assert last_fail is not None
    assert last_fail["target"] == "assignment"


# ==============================================================================
# 3. BROWSER CONTINUITY TEST SUITE (Section 67)
# ==============================================================================

def test_browser_continuity_youtube_and_playback(wm, resolver):
    """'Search YouTube for study music.' -> 'Open second.' -> 'Pause it.' (Section 67)."""
    b1 = BrowserPageRef(resource_id="yt1", url="https://youtube.com/watch?v=1", title="Study Beats 1", position=1)
    b2 = BrowserPageRef(resource_id="yt2", url="https://youtube.com/watch?v=2", title="Study Beats 2", position=2)
    wm.set_result_set(ResultSet(result_set_id="yt_search", query="study music", resources=[b1, b2]))

    # Turn 2: "Open second."
    res = resolver.resolve_for_slot("second", expected_type="browser_page", utterance="Open the second one.")
    assert res.target == "https://youtube.com/watch?v=2"

    wm.record_browser_page(b2)
    assert wm.get_current_browser_resource().url == "https://youtube.com/watch?v=2"

    # Turn 3: "Pause it."
    res_pause = resolver.resolve_for_slot("it", expected_type="media", utterance="Pause it.")
    assert res_pause.target == "https://youtube.com/watch?v=2" or res_pause.target == "Study Beats 2"


# ==============================================================================
# 4. WHATSAPP CONTINUITY TEST SUITE (Section 68)
# ==============================================================================

def test_whatsapp_continuity_contact_draft_and_send(wm, resolver):
    """'Show messages from Arun.' -> 'What does he want?' -> 'Draft reply.' -> 'Send it.' (Section 68)."""
    arun = ContactResourceRef(resource_id="c_arun", name="Arun", phone="+1234567890")
    wm.set_current_contact(arun)

    # 1. "What does he want?" -> resolves Arun
    res_contact = resolver.resolve_for_slot("he", expected_type="contact", utterance="What does he want?")
    assert res_contact.target == "Arun"

    # 2. "Draft a reply saying tomorrow."
    draft = DraftResourceRef(resource_id="d1", recipient="Arun", text="See you tomorrow.")
    wm.set_pending_draft(draft)
    assert wm.get_pending_draft().text == "See you tomorrow."

    # 3. "Send it." -> resolves current draft for message slot, and contact for recipient
    res_draft = resolver.resolve_for_slot("it", expected_type="draft", utterance="Send it.")
    assert res_draft.target == "See you tomorrow." or res_draft.referent.resource_id == "d1"

    res_recip = resolver.resolve_for_slot("him", expected_type="contact", utterance="Send it to him.")
    assert res_recip.target == "Arun"


# ==============================================================================
# 5. AMBIGUITY TEST SUITE (Section 69, 74)
# ==============================================================================

def test_ambiguity_two_software_options_triggers_clarification(wm, resolver):
    """'What are Ollama and LM Studio?' -> 'Install it.' -> CLARIFY (Section 40, 69)."""
    wm.add_entity(EntityRef(entity_id="ollama", canonical_name="Ollama", display_name="Ollama", entity_type=EntityType.SOFTWARE, salience=0.9))
    wm.add_entity(EntityRef(entity_id="lm_studio", canonical_name="LM Studio", display_name="LM Studio", entity_type=EntityType.SOFTWARE, salience=0.88))

    res = resolver.resolve_for_slot("it", expected_type="software", utterance="Install it.")
    assert res.confidence == ReferenceConfidence.AMBIGUOUS
    assert res.clarification_prompt is not None
    # Good prompt uses candidate names (Section 74)
    assert "Ollama" in res.clarification_prompt
    assert "LM Studio" in res.clarification_prompt


def test_ambiguity_five_pdfs_triggers_clarification_without_selection(wm, resolver):
    """'List five PDFs.' -> 'Open it.' -> CLARIFY (Section 69)."""
    pdfs = [f"C:/Users/ashok/Documents/file_{i}.pdf" for i in range(1, 6)]
    wm.record_search_results("List five PDFs", pdfs)

    res = resolver.resolve_for_slot("it", expected_type="file", utterance="Open it.")
    # With 5 files in recent search and no current/selected file, it should clarify or indicate ambiguity
    assert res.confidence in (ReferenceConfidence.AMBIGUOUS, ReferenceConfidence.LOW) or res.clarification_prompt is not None


# ==============================================================================
# 6. CONTEXT POLLUTION & TYPE COMPATIBILITY TEST (Section 70, 71)
# ==============================================================================

def test_context_pollution_type_compatibility_wins_over_recency(wm, resolver):
    """
    Open Chrome (app) -> Find PDFs (file) -> Show phone (device)
    -> Explain Ollama (software) -> Check Calendar (event 1s ago).
    USER: 'Install it.'
    Expected: Ollama (Software ↔ install compatibility, not calendar/phone/pdf/chrome).
    (Sections 70, 71).
    """
    import time

    # Step 1: Open Chrome
    wm.record_app_focused("Google Chrome")

    # Step 2: Find PDFs
    wm.record_search_results("Find PDFs", ["C:/docs/ml.pdf"])

    # Step 3: Device
    wm.add_entity(EntityRef(entity_id="phone", canonical_name="Pixel 8", display_name="Phone", entity_type=EntityType.DEVICE))

    # Step 4: Explain Ollama (Software entity)
    wm.push_topic("Ollama", entity_type=EntityType.SOFTWARE)
    wm.add_entity(EntityRef(entity_id="ollama", canonical_name="Ollama", display_name="Ollama", entity_type=EntityType.SOFTWARE, salience=0.95))

    # Step 5: Check Calendar (1 second ago)
    wm.add_entity(EntityRef(entity_id="cal_event", canonical_name="Standup Meeting", display_name="Standup", entity_type=EntityType.UNKNOWN, salience=0.99))

    # USER: "Install it."
    res = resolver.resolve_for_slot("it", expected_type="software", utterance="Install it.")
    assert res.confidence == ReferenceConfidence.HIGH
    assert res.target == "Ollama"
    assert res.target != "Standup Meeting"
    assert res.target != "Pixel 8"
    assert res.target != "Google Chrome"


# ==============================================================================
# 7. FAILURE FOLLOW-UP & FAST RECOVERY TEST (Section 24, 46)
# ==============================================================================

def test_failure_followup_open_vlc_fails_then_install_it(wm, resolver):
    """USER: 'Open VLC' -> fails (APP_NOT_FOUND) -> 'Install it.' -> resolves VLC (Section 24)."""
    wm.record_action_failure(target="VLC", reason="APP_NOT_FOUND")

    res = resolver.resolve_for_slot("it", expected_type="software", utterance="Install it.")
    assert res.confidence == ReferenceConfidence.HIGH
    assert res.target == "VLC"


def test_why_query_explains_last_failure(wm):
    """USER: 'Open Photoshop' -> fails -> 'Why?' -> explained from ActionOutcome (Section 46)."""
    wm.record_action_failure(target="Photoshop", reason="APP_NOT_FOUND")

    f_res = FollowupDetector.detect("Why?")
    assert f_res.followup_type == FollowupType.WHY_QUERY

    last_fail = wm.get_last_failure()
    assert last_fail is not None
    assert last_fail["target"] == "Photoshop"
    assert last_fail["reason"] == "APP_NOT_FOUND"


# ==============================================================================
# 8. TOPIC STACK & TOPIC SWITCH (Section 19, 20)
# ==============================================================================

def test_topic_stack_restore_previous_topic(wm, resolver):
    """
    Topic A = Ollama -> Topic B = PDF -> 'Go back to Ollama.' -> 'Install it.'
    (Section 19, 20).
    """
    wm.push_topic("Ollama", entity_type=EntityType.SOFTWARE)
    wm.add_entity(EntityRef(entity_id="ollama", canonical_name="Ollama", display_name="Ollama", entity_type=EntityType.SOFTWARE))

    # User discusses PDF
    wm.push_topic("CNN PDF", entity_type=EntityType.TOPIC)
    assert wm.active_topic.canonical_name == "CNN PDF"

    # User says: "Go back to Ollama."
    f_res = FollowupDetector.detect("Go back to Ollama.")
    assert f_res.followup_type == FollowupType.TOPIC_SWITCH
    assert f_res.target_hint.casefold() == "ollama"

    # Restore Ollama topic
    wm.push_topic(f_res.target_hint, entity_type=EntityType.SOFTWARE)
    assert wm.active_topic.canonical_name.casefold() == "ollama"

    # User says: "Install it."
    res = resolver.resolve_for_slot("it", expected_type="software", utterance="Install it.")
    assert res.confidence == ReferenceConfidence.HIGH
    assert res.target.casefold() == "ollama"


# ==============================================================================
# 9. CLARIFICATION & CONFIRMATION PRESERVE TASK STATE (Sections 42-44)
# ==============================================================================

def test_pending_confirmation_resumed_not_reparsed(wm):
    """'Delete file' -> WAITING_CONFIRMATION -> 'Yes' resumes exact ticket (Section 43, 44)."""
    conf = PendingConfirmation(
        ticket_id="ticket_xyz123",
        action="delete_file",
        human_summary="Delete file C:/temp/test.txt",
        prepared_slots={"path": "C:/temp/test.txt"},
        risk_level="HIGH",
    )
    wm.set_pending_confirmation(conf)

    assert wm.get_pending_confirmation() is not None
    assert wm.get_pending_confirmation().ticket_id == "ticket_xyz123"

    f_res = FollowupDetector.detect("Yes")
    assert f_res.followup_type == FollowupType.CONFIRMATION

    # Clear pending on completion
    wm.clear_pending_confirmation()
    assert wm.get_pending_confirmation() is None


def test_pending_clarification_preserves_task_state(wm):
    """'Send it to Arun' -> clarify which Arun -> original intent and slots preserved (Section 42)."""
    clar = PendingClarification(
        original_intent="send_message",
        candidate_names=["Arun Kumar", "Arun Studio"],
        missing_slot="recipient",
        context_snapshot={"resource": "CNN.pdf"},
    )
    wm.set_pending_clarification(clar)

    active_clar = wm.get_pending_clarification()
    assert active_clar is not None
    assert active_clar.original_intent == "send_message"
    assert "Arun Kumar" in active_clar.candidate_names

    wm.clear_pending_clarification()
    assert wm.get_pending_clarification() is None
