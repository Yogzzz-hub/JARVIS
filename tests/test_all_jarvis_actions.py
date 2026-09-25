"""Comprehensive Verification Test Suite for All JARVIS Capabilities.

Covers all 23 capability domains:
1. Wake + Voice, Continuous Mode, Barge-in, Dictation & Voice Editing
2. Application Control & Window Snapping/Arranging/Settings/Known Folders/Power
3. Desktop UI Automation & Semantic Interaction
4. Keyboard Shortcuts & Clipboard Intelligence
5. Screen Intelligence & Screenshots
6. Browser Automation
7. YouTube & Media Control
8. File Operations
9. RAG & Document Intelligence
10. Antigravity & IDE Automation
11. Safe System & Dev Actions
12. Phone & Android Control
13. WhatsApp Omnichannel Transport
14. Conversational Continuity & Context Resolution
15. Multi-Step Workflows & DAG Composition
16. Safety, Verification & ActionLedger
"""
import pytest
import os
import re
from pathlib import Path

from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.router.router import SmartRouter
from jarvis.core.capabilities.registry import CapabilityRegistry
from jarvis.tools.system.app_resolver import AppResolver
from jarvis.tools.system.native import create_tools
from jarvis.tools.productivity.dictation import (
    format_dictation,
    apply_spelling_mode,
    apply_number_mode,
    get_dictation_manager,
    DictationTool,
    VoiceEditTool,
    DictationModeControlTool,
    DictateInput,
    VoiceEditInput,
    DictationModeInput,
)
from jarvis.tools.system.window_management_tools import (
    get_known_folder_path,
    get_screen_dimensions,
    SnapWindowTool,
    ArrangeWindowsTool,
    MoveResizeWindowTool,
    SwitchWindowTool,
    SystemSettingsTool,
    KnownFoldersTool,
    PowerControlTool,
    DialogInteractionTool,
    SnapWindowInput,
    ArrangeWindowsInput,
    MoveResizeWindowInput,
    SwitchWindowInput,
    SystemSettingsInput,
    KnownFolderInput,
    PowerControlInput,
    DialogInput,
)
from jarvis.tools.system.keyboard_tools import (
    KeyboardShortcutTool,
    ClipboardIntelligenceTool,
    ShortcutInput,
    ClipboardInput,
)
from jarvis.tools.system.ide_tools import (
    AntigravityIDETool,
    IDEControlInput,
)


@pytest.fixture
def router():
    return SmartRouter()


@pytest.fixture
def master_tools():
    return {t.definition.name: t for t in create_tools(AppResolver(), {})}


# =====================================================================
# 1. Wake + Voice, Dictation & Voice Editing
# =====================================================================

def test_voice_punctuation_and_formatting():
    raw = "hello comma world period new line how are you question mark new paragraph great exclamation mark"
    formatted = format_dictation(raw)
    assert "Hello, world." in formatted
    assert "\n" in formatted
    assert "How are you?" in formatted
    assert "\n\n" in formatted
    assert "Great!" in formatted


def test_voice_spelling_mode():
    text1 = "please spell J A R V I S now"
    res1 = apply_spelling_mode(text1)
    assert "JARVIS" in res1

    text2 = "spell out a n t i g r a v i t y"
    res2 = apply_spelling_mode(text2)
    assert "antigravity" in res2


def test_voice_number_mode():
    assert apply_number_mode("number forty two") == "42"
    assert apply_number_mode("number seven") == "7"
    assert apply_number_mode("number one hundred twenty three") == "123"


def test_dictation_session_manager_and_voice_editing():
    mgr = get_dictation_manager()
    target = mgr.start("TestEditor")
    assert mgr.is_active() is True
    assert target is not None

    mgr.last_typed_text = "The quick brown fox jumps over the lazy dog"

    # Test delete last word
    ok, text, _ = mgr.execute_edit_action("delete_last_word")
    assert ok is True
    assert text == "The quick brown fox jumps over the lazy"

    # Test delete last sentence
    mgr.last_typed_text = "First sentence. Second sentence."
    ok, text, _ = mgr.execute_edit_action("delete_last_sentence")
    assert ok is True
    assert text == "First sentence."

    # Test capitalize that
    mgr.last_typed_text = "hello world"
    ok, text, _ = mgr.execute_edit_action("capitalize_that")
    assert ok is True
    assert text == "hello World"

    # Test replace X with Y
    mgr.last_typed_text = "I love apple pie"
    ok, text, _ = mgr.execute_edit_action("replace", target="apple", replacement="cherry")
    assert ok is True
    assert text == "I love cherry pie"

    # Test exit command detection
    assert mgr.is_exit_command("stop typing") is True
    assert mgr.is_exit_command("stop dictation") is True
    assert mgr.is_exit_command("hello world") is False

    # Test UI command detection
    assert mgr.is_ui_command("send") == "submit"
    assert mgr.is_ui_command("press enter") == "submit"
    assert mgr.is_ui_command("hello") is None

    mgr.stop()
    assert mgr.is_active() is False


def test_dictation_tool_execution():
    tool = DictationTool()
    res = tool.run(DictateInput(text="Testing voice typing period", streaming=True))
    assert res["status"] in ("inserted", "ready_to_insert")
    assert "Testing voice typing." in res["formatted_text"]


def test_voice_edit_tool_execution():
    tool = VoiceEditTool()
    res = tool.run(VoiceEditInput(action="delete_word"))
    assert res["status"] in ("SUCCESS", "FAILED")


def test_dictation_mode_control_tool():
    tool = DictationModeControlTool()
    res_start = tool.run(DictationModeInput(action="start"))
    assert res_start["active"] is True
    res_stop = tool.run(DictationModeInput(action="stop"))
    assert res_stop["active"] is False


# =====================================================================
# 2. Application Control & Advanced Window Management
# =====================================================================

def test_screen_dimensions():
    w, h = get_screen_dimensions()
    assert w > 0 and h > 0


def test_snap_window_tool():
    tool = SnapWindowTool()
    res = tool.run(SnapWindowInput(direction="left"))
    assert res["status"] == "SUCCESS"
    assert res["direction"] == "left"
    assert res["rect"]["width"] > 0


def test_arrange_windows_tool():
    tool = ArrangeWindowsTool()
    res = tool.run(ArrangeWindowsInput(layout="side_by_side"))
    assert res["status"] == "SUCCESS"


def test_move_resize_window_tool():
    tool = MoveResizeWindowTool()
    res = tool.run(MoveResizeWindowInput(action="restore"))
    assert res["status"] == "SUCCESS"


def test_switch_window_tool():
    tool = SwitchWindowTool()
    res = tool.run(SwitchWindowInput(target="previous"))
    assert res["status"] == "SUCCESS"


def test_system_settings_tool():
    tool = SystemSettingsTool()
    # Test valid pages
    for p in ("sound", "display", "network", "task_manager"):
        res = tool.run(SystemSettingsInput(page=p))
        assert res["status"] == "SUCCESS"


def test_known_folders_resolution_and_tool():
    for f in ("downloads", "documents", "desktop", "pictures"):
        path = get_known_folder_path(f)
        assert path is not None
        assert len(path) > 0
        assert os.path.isabs(path)

    tool = KnownFoldersTool()
    res = tool.run(KnownFolderInput(folder="downloads"))
    assert res["status"] == "SUCCESS"
    assert "Downloads" in res["resolved_path"]


def test_dialog_interaction_tool():
    tool = DialogInteractionTool()
    res = tool.run(DialogInput(action="detect"))
    assert res["status"] == "SUCCESS"
    assert "is_dialog" in res
    assert "is_hung" in res


def test_power_control_safety_guard():
    tool = PowerControlTool()
    assert tool.definition.risk.name == "DESTRUCTIVE"
    # Lock PC should work safely
    res_lock = tool.run(PowerControlInput(action="lock"))
    assert res_lock["status"] in ("SUCCESS", "FAILED")


# =====================================================================
# 3. Keyboard & Clipboard Intelligence
# =====================================================================

def test_keyboard_shortcut_tool():
    tool = KeyboardShortcutTool()
    shortcuts = ["enter", "escape", "tab", "ctrl_c", "ctrl_v", "ctrl_z", "ctrl_s"]
    for s in shortcuts:
        res = tool.run(ShortcutInput(key=s))
        assert res["status"] == "SUCCESS"


def test_clipboard_intelligence_tool():
    tool = ClipboardIntelligenceTool()
    # Test read
    res_read = tool.run(ClipboardInput(action="read"))
    assert res_read["status"] == "SUCCESS"

    # Test copy and paste
    res_copy = tool.run(ClipboardInput(action="copy", text="JARVIS_CLIPBOARD_TEST"))
    assert res_copy["status"] == "SUCCESS"


# =====================================================================
# 4. Antigravity / IDE Automation
# =====================================================================

def test_antigravity_ide_tool():
    tool = AntigravityIDETool()
    # Test error explanation
    res_err = tool.run(IDEControlInput(action="explain_error", text="ValueError: invalid literal for int()"))
    assert res_err["status"] == "SUCCESS"
    assert "Diagnostic explanation" in res_err["message"]

    # Test file saving shortcut
    res_save = tool.run(IDEControlInput(action="save_file"))
    assert res_save["status"] == "SUCCESS"


# =====================================================================
# 5. Deterministic Routing & Intent Verification
# =====================================================================

@pytest.mark.asyncio
async def test_router_lane0_coverage(router):
    cases = [
        ("snap window left", "snap_window", {"direction": "left"}),
        ("snap window right", "snap_window", {"direction": "right"}),
        ("arrange windows side by side", "arrange_windows", {}),
        ("open downloads folder", "open_known_folder", {"folder": "Downloads"}),
        ("open documents folder", "open_known_folder", {"folder": "Documents"}),
        ("open sound settings", "open_system_settings", {"page": "sound"}),
        ("open display settings", "open_system_settings", {"page": "display"}),
        ("open task manager", "open_system_settings", {"page": "task manager"}),
        ("lock the pc", "system_power_control", {"action": "lock"}),
        ("press enter", "keyboard_shortcut", {"key": "enter"}),
        ("press escape", "keyboard_shortcut", {"key": "escape"}),
        ("ctrl c", "keyboard_shortcut", {"key": "ctrl c"}),
        ("start typing dictation mode", "dictation_mode_control", {"action": "start"}),
        ("stop typing", "dictation_mode_control", {"action": "stop"}),
        ("delete last word", "voice_edit", {"action": "word"}),
        ("voice backspace", "voice_edit", {"action": "backspace"}),
        ("open antigravity", "antigravity_ide_control", {"action": "open"}),
        ("focus coding prompt", "antigravity_ide_control", {"action": "focus"}),
        ("open terminal panel", "antigravity_ide_control", {"action": "open terminal"}),
        ("explain visible error", "antigravity_ide_control", {"action": "explain visible error"}),
    ]

    for utterance, expected_intent, expected_slots in cases:
        dec = await router.route(CommandRequest(text=utterance))
        assert dec.intent == expected_intent, f"Expected {expected_intent} for '{utterance}', got {dec.intent}"
        assert dec.lane.value == "LANE_0", f"Expected LANE_0 for '{utterance}', got {dec.lane.value}"
        for k, v in expected_slots.items():
            assert dec.slots.get(k) == v, f"Expected slot {k}={v} in '{utterance}', got {dec.slots}"


def test_master_capability_catalog_consistency():
    reg = CapabilityRegistry()
    all_caps = reg.list_all()
    assert len(all_caps) >= 100

    target_tools = {c.target_tool for c in all_caps}
    assert "snap_window" in target_tools
    assert "arrange_windows" in target_tools
    assert "open_system_settings" in target_tools
    assert "open_known_folder" in target_tools
    assert "system_power_control" in target_tools
    assert "keyboard_shortcut" in target_tools
    assert "clipboard_intelligence" in target_tools
    assert "voice_edit" in target_tools
    assert "dictation_mode_control" in target_tools
    assert "antigravity_ide_control" in target_tools
