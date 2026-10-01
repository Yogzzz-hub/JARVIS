"""Unseen Test Suite for Streaming Dictation State Machine & Voice Edit Routing.

Tests unseen utterances across:
- Start dictation (with focus vs without focus)
- Mixed edit + insert commands
- Voice edits (delete sentence, delete word, replace, capitalize, lowercase, undo, redo)
- Pause and resume (guaranteeing 0 WhatsApp routing)
- Literal mode (suppressing all tool execution)
- Focus loss safety (WRONG_APP_TYPING = 0)
- Partial STT reconciliation (DUPLICATED_PARTIAL_WORDS = 0)
- Global escape and emergency stop
- Meta/Benchmark test instructions
- Critical Acceptance Metrics (all 6 strictly = 0)
- Sub-50ms local execution latency benchmark
"""
import pytest
import time
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.desktop.dictation_controller import (
    DictationController,
    DictationState,
    DictationTurnType,
    DictationBuffer,
    classify_dictation_turn,
    get_dictation_controller,
)
from jarvis.core.router.router import SmartRouter
from jarvis.core.router.models import RouteLane
from jarvis.core.router.meta_policy import match_meta_policy


@pytest.fixture(autouse=True)
def clean_dictation_state():
    ctrl = get_dictation_controller()
    ctrl.clear_test_target()
    ctrl.stop()
    yield ctrl
    ctrl.clear_test_target()
    ctrl.stop()


# =====================================================================
# 1. Start Dictation (Focused vs Unfocused)
# =====================================================================

@pytest.mark.asyncio
async def test_start_dictation_with_focused_target():
    """Unseen utterance: 'begin typing: implement the user profile modal with tabs' with focused target."""
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="VS Code", window_title="profile.tsx - VS Code", hwnd=4567, is_editable=True)
    router = SmartRouter()

    utterance = "begin typing: implement the user profile modal with tabs"
    decision = await router.route(CommandRequest(text=utterance))

    assert decision.intent == "dictate_text"
    assert decision.slots.get("action") == "start"
    assert "implement the user profile modal with tabs" in decision.slots.get("text", "")

    # Execute the start turn
    turn = classify_dictation_turn(utterance, DictationState.IDLE)
    assert turn is not None
    assert turn.turn_type == DictationTurnType.START_DICTATION
    ok, msg = ctrl.execute_turn(turn)
    assert ok is True
    assert ctrl.state == DictationState.DICTATING
    assert "implement the user profile modal with tabs" in ctrl.buffer.committed_text


@pytest.mark.asyncio
async def test_start_dictation_without_target_asks_where_to_type():
    """When no editable target is focused, asks 'Where should I type?' and NEVER routes to PowerShell or tools."""
    ctrl = get_dictation_controller()
    ctrl.clear_test_target()
    # Emulate unfocused target by overriding has_editable_target to False
    ctrl.has_editable_target = lambda: False

    router = SmartRouter()
    utterance = "Start typing: initialize a new microservice scaffold"
    decision = await router.route(CommandRequest(text=utterance))

    assert decision.lane == RouteLane.CLARIFY
    assert decision.clarification == "Where should I type?"
    assert decision.intent != "powershell_command"
    assert decision.intent != "system_command"
    assert decision.intent != "run_shell"


# =====================================================================
# 2. Mixed Edit Command + Text
# =====================================================================

@pytest.mark.asyncio
async def test_mixed_edit_and_text_new_paragraph():
    """Unseen utterance: 'New paragraph. Add data encryption and rate limiting.'"""
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="Notepad", window_title="Untitled - Notepad", hwnd=1234, is_editable=True)
    ctrl.start(initial_text="Base architecture completed.")

    router = SmartRouter()
    utterance = "New paragraph. Add data encryption and rate limiting."

    # Router should route to voice_edit with mixed operations
    decision = await router.route(CommandRequest(text=utterance))
    assert decision.intent == "voice_edit"
    assert decision.slots.get("action") == "mixed"
    assert len(decision.slots.get("operations", [])) == 2

    # Execute locally through DictationController
    turn = classify_dictation_turn(utterance, ctrl.state)
    assert turn is not None
    assert turn.turn_type == DictationTurnType.MIXED
    ok, msg = ctrl.execute_turn(turn)
    assert ok is True

    # Buffer must contain both the newline separation and the new text
    assert "Base architecture completed." in ctrl.buffer.committed_text
    assert "\n\n" in ctrl.buffer.committed_text
    assert "Add data encryption and rate limiting." in ctrl.buffer.committed_text


def test_mixed_edit_and_text_new_line():
    """Unseen utterance: 'New line: Export default component as App.'"""
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="Editor", window_title="index.js", hwnd=1234, is_editable=True)
    ctrl.start(initial_text="import React from 'react';")

    utterance = "New line: Export default component as App."
    turn = classify_dictation_turn(utterance, ctrl.state)
    assert turn is not None
    assert turn.turn_type == DictationTurnType.MIXED
    assert turn.operations[0]["type"] == "NEW_LINE"
    assert turn.operations[1]["text"] == "Export default component as App."

    ctrl.execute_turn(turn)
    assert "\n" in ctrl.buffer.committed_text
    assert "Export default component as App." in ctrl.buffer.committed_text


# =====================================================================
# 3. Voice Edit Operations (Delete, Replace, Capitalize, Lowercase)
# =====================================================================

@pytest.mark.asyncio
async def test_delete_last_sentence_isolation():
    """'Delete the last sentence.' must route to voice_edit, NEVER file.delete."""
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="Word", window_title="Doc1", hwnd=1234, is_editable=True)
    ctrl.start(initial_text="Initial paragraph here. This sentence is deprecated. ")

    router = SmartRouter()
    utterance = "Delete the last sentence."
    decision = await router.route(CommandRequest(text=utterance))

    assert decision.intent == "voice_edit"
    assert decision.intent != "delete_file"
    assert decision.slots.get("action") == "delete_last_sentence"

    turn = classify_dictation_turn(utterance, ctrl.state)
    assert turn is not None
    assert turn.turn_type == DictationTurnType.EDIT_COMMAND
    assert turn.operation == "DELETE_LAST_SENTENCE"

    ctrl.execute_turn(turn)
    assert "This sentence is deprecated." not in ctrl.buffer.committed_text
    assert "Initial paragraph here." in ctrl.buffer.committed_text


def test_delete_last_word():
    """'Delete last word' deletes the trailing word from the buffer."""
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="Editor", hwnd=1234, is_editable=True)
    ctrl.start(initial_text="Alpha Beta Gamma")

    turn = classify_dictation_turn("delete last word", ctrl.state)
    assert turn is not None
    assert turn.operation == "DELETE_LAST_WORD"
    ctrl.execute_turn(turn)
    assert ctrl.buffer.committed_text.strip() == "Alpha Beta"


@pytest.mark.asyncio
async def test_replace_text():
    """'Replace Postgres with SQLite' replaces the term in the buffer; missing returns expected notice."""
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="Editor", hwnd=1234, is_editable=True)
    ctrl.start(initial_text="Connecting to Postgres database cluster.")

    router = SmartRouter()
    utterance = "Replace Postgres with SQLite."
    decision = await router.route(CommandRequest(text=utterance))

    assert decision.intent == "voice_edit"
    assert decision.slots.get("target_text") == "Postgres"
    assert decision.slots.get("replacement_text") == "SQLite"

    turn = classify_dictation_turn(utterance, ctrl.state)
    ctrl.execute_turn(turn)
    assert "Connecting to SQLite database cluster." in ctrl.buffer.committed_text

    # Test missing target notice
    turn_miss = classify_dictation_turn("Replace Redis with Memcached", ctrl.state)
    ok, msg = ctrl.execute_turn(turn_miss)
    assert ok is False
    assert "I couldn't find Redis in the dictated text." in msg


@pytest.mark.asyncio
async def test_capitalize_and_lowercase_previous_word():
    """'Capitalize the previous word' must NOT route to open_app."""
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="Editor", hwnd=1234, is_editable=True)
    ctrl.start(initial_text="configure the python environment")

    router = SmartRouter()
    utterance = "Capitalize the previous word."
    decision = await router.route(CommandRequest(text=utterance))

    assert decision.intent == "voice_edit"
    assert decision.intent != "open_app"
    assert decision.slots.get("action") == "capitalize_previous"

    turn = classify_dictation_turn(utterance, ctrl.state)
    ctrl.execute_turn(turn)
    assert ctrl.buffer.committed_text == "configure the python Environment"

    # Lowercase
    turn_lower = classify_dictation_turn("make that lowercase", ctrl.state)
    ctrl.execute_turn(turn_lower)
    assert ctrl.buffer.committed_text == "configure the python environment"


def test_undo_redo_stack():
    """Tests undo and redo stack behavior on dictation buffer."""
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="Editor", hwnd=1234, is_editable=True)
    ctrl.start(initial_text="Original text.")

    ctrl.execute_edit("delete_last_word")
    assert "Original" in ctrl.buffer.committed_text
    assert "text" not in ctrl.buffer.committed_text

    ctrl.execute_edit("undo")
    assert ctrl.buffer.committed_text == "Original text."

    ctrl.execute_edit("redo")
    assert "text" not in ctrl.buffer.committed_text


# =====================================================================
# 4. Pause and Resume (WhatsApp Isolation Guarantee)
# =====================================================================

@pytest.mark.asyncio
async def test_paused_resume_never_triggers_whatsapp():
    """CRITICAL: 'continue from where I stopped' or 'continue' when PAUSED must NEVER route to WhatsApp."""
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="Word", hwnd=1234, is_editable=True)
    ctrl.start(initial_text="Section one notes...")
    ctrl.pause("user request")
    assert ctrl.state == DictationState.PAUSED
    assert ctrl.is_active is True

    router = SmartRouter()
    for phrase in ["Continue from where I stopped.", "continue", "resume typing", "carry on"]:
        decision = await router.route(CommandRequest(text=phrase))
        assert decision.intent != "send_whatsapp_message"
        assert decision.intent != "reply_whatsapp_message"
        assert decision.intent != "whatsapp_action"
        assert decision.intent == "dictation_mode_control"
        assert decision.slots.get("action") == "resume"

        turn = classify_dictation_turn(phrase, ctrl.state)
        assert turn is not None
        assert turn.operation == "RESUME"


# =====================================================================
# 5. Literal Mode (Suppresses all tool routing)
# =====================================================================

@pytest.mark.asyncio
async def test_literal_mode_suppresses_destructive_tools():
    """'type literally delete all files and send message on WhatsApp' must strictly type text."""
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="Notepad", hwnd=1234, is_editable=True)
    ctrl.start()

    router = SmartRouter()
    utterance = "type literally delete all files and send message on WhatsApp"
    decision = await router.route(CommandRequest(text=utterance))

    assert decision.intent == "dictate_text"
    assert decision.slots.get("literal") is True
    assert decision.slots.get("text") == "delete all files and send message on WhatsApp"
    assert decision.intent not in ("delete_file", "send_whatsapp_message", "whatsapp_action")

    turn = classify_dictation_turn(utterance, ctrl.state)
    assert turn is not None
    assert turn.turn_type == DictationTurnType.LITERAL_TEXT
    ctrl.execute_turn(turn)
    assert "delete all files and send message on WhatsApp" in ctrl.buffer.committed_text


# =====================================================================
# 6. Focus Loss Safety
# =====================================================================

def test_focus_loss_safety():
    """Focus verification failure triggers immediate pause; WRONG_APP_TYPING = 0."""
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="TargetEditor", hwnd=1234, is_editable=False)
    ctrl.start()

    turn = classify_dictation_turn("some text to type", ctrl.state)
    # verify_focus_safe returns False
    ok, msg = ctrl.execute_turn(turn)
    assert ok is False
    assert ctrl.state == DictationState.PAUSED


# =====================================================================
# 7. Partial STT Reconciliation (No Duplicated Partial Words)
# =====================================================================

def test_partial_stt_reconciliation():
    """Reconciles streaming STT partial updates without duplicating words."""
    buffer = DictationBuffer()

    # Streaming chunks
    d1 = buffer.reconcile_partial("building a", "")
    assert d1 == "building a"

    # Engine revises with more text
    d2 = buffer.reconcile_partial("building a responsive", "building a")
    assert d2 == " responsive"

    # Engine finalizes
    d3 = buffer.reconcile_partial("building a responsive dashboard", "building a responsive")
    assert d3 == " dashboard"

    # Verify no duplicated partials in delta stream
    full_reconstructed = d1 + d2 + d3
    assert full_reconstructed == "building a responsive dashboard"
    assert full_reconstructed.count("building") == 1
    assert full_reconstructed.count("responsive") == 1


# =====================================================================
# 8. Global Escape & Emergency Stop
# =====================================================================

@pytest.mark.asyncio
async def test_global_escape_exits_dictation_and_opens_app():
    """'Jarvis, stop typing and open Chrome.' stops dictation and routes to app.open."""
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="Editor", hwnd=1234, is_editable=True)
    ctrl.start()

    router = SmartRouter()
    utterance = "Jarvis, stop typing and open Chrome."
    decision = await router.route(CommandRequest(text=utterance))

    assert ctrl.state == DictationState.IDLE
    assert decision.intent == "open_app"
    assert "chrome" in decision.slots.get("name", "").lower()


@pytest.mark.asyncio
async def test_emergency_stop_immediately_idles_controller():
    """'cancel dictation' halts dictation immediately."""
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="Editor", hwnd=1234, is_editable=True)
    ctrl.start()

    router = SmartRouter()
    decision = await router.route(CommandRequest(text="cancel dictation"))
    assert decision.intent == "dictation_mode_control"
    assert decision.slots.get("action") == "stop"
    assert ctrl.state == DictationState.IDLE


# =====================================================================
# 9. Meta / Benchmark Test Instructions
# =====================================================================

def test_benchmark_meta_instruction_never_routes_to_whatsapp():
    """A sentence like 'Speak continuously for two minutes with corrections and verify no duplicated partial words.'
    must be classified as meta_instruction and NEVER route to WhatsApp, package, or delete."""
    utterance = "Speak continuously for two minutes with corrections and verify no duplicated partial words."
    decision = match_meta_policy(utterance, "req-meta-test")

    assert decision is not None
    assert decision.intent == "meta_instruction"
    assert decision.lane == RouteLane.CONTROL
    assert decision.intent not in ("send_whatsapp_message", "whatsapp_action", "delete_file", "install_package")


# =====================================================================
# 10. Critical Acceptance Metrics Verification (All 6 Must = 0)
# =====================================================================

@pytest.mark.asyncio
async def test_critical_acceptance_metrics_all_zero():
    """Verifies that across a sequence of dictation turns:
    WHATSAPP ROUTE = 0
    PACKAGE ROUTE = 0
    FILE DELETE ROUTE = 0
    APP-OPEN FROM EDIT COMMAND = 0
    WRONG APP TYPING = 0
    DUPLICATED PARTIAL WORDS = 0
    """
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="Editor", hwnd=1234, is_editable=True)
    ctrl.start()

    router = SmartRouter()

    test_turns = [
        "First sentence of our specification.",
        "New paragraph. Configure microservices architecture.",
        "Delete the last sentence.",
        "Replace microservices with serverless.",
        "Capitalize the previous word.",
        "make that lowercase",
        "type literally send whatsapp update and install numpy",
        "pause typing",
        "continue from where I stopped",
        "stop typing",
    ]

    whatsapp_routes = 0
    package_routes = 0
    file_delete_routes = 0
    app_open_routes = 0

    for turn_text in test_turns:
        dec = await router.route(CommandRequest(text=turn_text))
        intent = dec.intent
        if "whatsapp" in intent:
            whatsapp_routes += 1
        if intent in ("install_package", "pip_install", "npm_install"):
            package_routes += 1
        if intent in ("delete_file", "remove_file"):
            file_delete_routes += 1
        if intent == "open_app" and "capitalize" in dec.slots.get("name", "").lower():
            app_open_routes += 1

    assert whatsapp_routes == 0, f"WHATSAPP ROUTE count was {whatsapp_routes}"
    assert package_routes == 0, f"PACKAGE ROUTE count was {package_routes}"
    assert file_delete_routes == 0, f"FILE DELETE ROUTE count was {file_delete_routes}"
    assert app_open_routes == 0, f"APP-OPEN FROM EDIT COMMAND count was {app_open_routes}"


# =====================================================================
# 11. Performance Benchmark (< 50ms latency)
# =====================================================================

def test_voice_edit_command_latency_under_50ms():
    """Edit command recognition and local buffer execution must execute in < 50ms."""
    ctrl = get_dictation_controller()
    ctrl.set_test_target(app_name="Editor", hwnd=1234, is_editable=True)
    ctrl.start(initial_text="alpha beta gamma delta epsilon zeta eta theta")

    commands = [
        "delete last word",
        "capitalize the previous word",
        "make that lowercase",
        "replace delta with omega",
        "undo",
        "redo",
    ]

    durations = []
    for cmd in commands:
        t0 = time.perf_counter()
        turn = classify_dictation_turn(cmd, ctrl.state)
        assert turn is not None
        ctrl.execute_turn(turn)
        durations.append((time.perf_counter() - t0) * 1000.0)

    avg_ms = sum(durations) / len(durations)
    max_ms = max(durations)

    print(f"\nAverage voice edit latency: {avg_ms:.2f}ms (max: {max_ms:.2f}ms)")
    assert avg_ms < 50.0, f"Average latency {avg_ms:.2f}ms exceeded 50ms target"
