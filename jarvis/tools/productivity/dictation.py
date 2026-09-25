from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Optional, Tuple
from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition
from jarvis.tools.system.input_layer import (
    send_key as _send_key,
    send_combo as _send_combo,
    type_unicode as _type_unicode,
    VK,
)

logger = logging.getLogger("jarvis.productivity.dictation")

# Backwards-compatible VK aliases used throughout this file
VK_BACK = VK.BACK
VK_TAB = VK.TAB
VK_RETURN = VK.RETURN
VK_SHIFT = VK.SHIFT
VK_CONTROL = VK.CONTROL
VK_MENU = VK.MENU
VK_ESCAPE = VK.ESCAPE
VK_HOME = VK.HOME
VK_END = VK.END
VK_LEFT = VK.LEFT
VK_UP = VK.UP
VK_RIGHT = VK.RIGHT
VK_DOWN = VK.DOWN
VK_DELETE = VK.DELETE


# =====================================================================
# Contracts
# =====================================================================

class DictateInput(Contract):
    text: str = Field(min_length=1, max_length=10000, description="Spoken text to format and type")
    target_app: Optional[str] = Field(default=None, max_length=256, description="Optional target app name or window title")
    auto_punctuate: bool = True
    streaming: bool = False


class DictateOutput(Contract):
    formatted_text: str
    target_app: str
    characters: int
    status: str
    action_taken: str = "formatted"


class VoiceEditInput(Contract):
    action: str = Field(description="Voice edit action: backspace, delete_word, delete_sentence, undo, redo, select_sentence, replace, capitalize, lowercase, copy, cut, paste")
    target_text: Optional[str] = Field(default=None, description="Text to replace or target")
    replacement_text: Optional[str] = Field(default=None, description="Replacement text")


class VoiceEditOutput(Contract):
    status: str
    action: str
    result_text: str
    message: str


class DictationModeInput(Contract):
    action: str = Field(default="start", description="Action: start, stop, status, toggle")
    target_app: Optional[str] = Field(default=None, description="Optional target application")


class DictationModeOutput(Contract):
    active: bool
    target_app: str
    message: str


# =====================================================================
# Formatting, Spelling Mode & Number Mode
# =====================================================================

def words_to_number(s: str) -> str:
    """Converts a phrase containing English spoken number words to numeric digits."""
    units = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
        "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
        "nineteen": 19,
    }
    tens = {
        "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    }
    scales = {"hundred": 100, "thousand": 1000, "million": 1000000}

    words = s.lower().replace("-", " ").split()
    total = 0
    current = 0
    has_num = False

    for w in words:
        if w in units:
            current += units[w]
            has_num = True
        elif w in tens:
            current += tens[w]
            has_num = True
        elif w in scales:
            if current == 0:
                current = 1
            current *= scales[w]
            if scales[w] >= 1000:
                total += current
                current = 0
            has_num = True
        elif w.isdigit():
            current += int(w)
            has_num = True
        else:
            return s

    total += current
    return str(total) if has_num else s


def apply_spelling_mode(text: str) -> str:
    """Detects and formats spelling mode, e.g.:
    'spell J A R V I S' -> 'JARVIS'
    'spell out h e l l o' -> 'hello'
    'spell c a t' -> 'cat'
    """
    def _replace_spelling(m: re.Match) -> str:
        letters_raw = m.group(1).strip()
        parts = letters_raw.split()
        if all(len(p) <= 2 for p in parts):
            return "".join(parts)
        return letters_raw

    pattern = r"\b(?:spell out|spell)\s+((?:[a-zA-Z]\s+){1,}[a-zA-Z]\b)"
    res = re.sub(pattern, _replace_spelling, text, flags=re.IGNORECASE)
    return res


def apply_number_mode(text: str) -> str:
    """Converts spoken number phrases into digits, e.g.:
    'number forty two' -> '42'
    'number seven' -> '7'
    'number one hundred twenty three' -> '123'
    """
    def _eval_num(m: re.Match) -> str:
        phrase = m.group(1).strip()
        converted = words_to_number(phrase)
        return converted

    pattern = r"\b(?:number|digits?)\s+([a-zA-Z0-9\s\-]+?)(?=[.,!?;]|$)"
    res = re.sub(pattern, _eval_num, text, flags=re.IGNORECASE)
    return res


def format_dictation(raw_text: str, auto_punctuate: bool = True) -> str:
    """Formats voice dictation into punctuated prose with support for
    punctuation, new lines, new paragraphs, spelling mode, and number mode.
    """
    text = raw_text.strip()
    if not auto_punctuate:
        return text

    # 1. Spelling mode conversion
    text = apply_spelling_mode(text)

    # 2. Number mode conversion
    text = apply_number_mode(text)

    # 3. Punctuation and formatting symbols
    replacements = [
        (r"\b(?:period|full stop|dot)\b", "."),
        (r"\bcomma\b", ","),
        (r"\bquestion mark\b", "?"),
        (r"\b(?:exclamation mark|exclamation point)\b", "!"),
        (r"\bcolon\b", ":"),
        (r"\bsemicolon\b", ";"),
        (r"\b(?:new line|newline)\b", "\n"),
        (r"\b(?:new paragraph|new para)\b", "\n\n"),
        (r"\b(?:dash|hyphen)\b", "-"),
        (r"\bunderscore\b", "_"),
        (r"\b(?:open paren|open parenthesis)\b", "("),
        (r"\b(?:close paren|close parenthesis)\b", ")"),
        (r"\b(?:open quote|start quote)\b", '"'),
        (r"\b(?:close quote|end quote)\b", '"'),
        (r"\b(?:at sign|at symbol)\b", "@"),
        (r"\b(?:hashtag|pound sign)\b", "#"),
        (r"\bdollar sign\b", "$"),
        (r"\bpercent sign\b", "%"),
        (r"\bampersand\b", "&"),
        (r"\basterisk\b", "*"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    # 4. Clean up whitespace around punctuation
    text = re.sub(r"\s+([.,!?:;])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)

    # 5. Capitalize after sentence-ending punctuation and newlines
    text = re.sub(r"(^[a-z]|[.!?]\s+[a-z]|\n[a-z])", lambda m: m.group(0).upper(), text)
    return text


# =====================================================================
# Dictation Session Manager
# =====================================================================

class DictationSessionManager:
    """Manages continuous dictation mode, target tracking, live typing delta,
    focus change detection, and command vs dictation classification.
    """

    def __init__(self) -> None:
        self.active_dictation_mode: bool = False
        self.remembered_target_hwnd: Optional[int] = None
        self.remembered_target_title: str = ""
        self.last_typed_text: str = ""
        self.last_stable_prefix: str = ""
        self.buffer_history: list[str] = []

    def start(self, target_title: Optional[str] = None) -> str:
        self.active_dictation_mode = True
        self.buffer_history.clear()
        self.last_typed_text = ""
        self.last_stable_prefix = ""

        # Capture active window
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            self.remembered_target_hwnd = hwnd
            self.remembered_target_title = target_title or win32gui.GetWindowText(hwnd)
        except Exception:
            self.remembered_target_title = target_title or "active_window"

        logger.info(f"Dictation mode started targeting: {self.remembered_target_title}")
        return self.remembered_target_title

    def stop(self) -> str:
        self.active_dictation_mode = False
        target = self.remembered_target_title
        logger.info(f"Dictation mode stopped for: {target}")
        return target

    def is_active(self) -> bool:
        return self.active_dictation_mode

    def verify_target_focus(self) -> bool:
        """Verifies if the remembered dictation target is currently in foreground."""
        if not self.remembered_target_hwnd:
            return True
        try:
            import win32gui
            current = win32gui.GetForegroundWindow()
            return current == self.remembered_target_hwnd
        except Exception:
            return True

    def refocus_target(self) -> bool:
        """Restores focus to the remembered dictation target."""
        if not self.remembered_target_hwnd:
            return False
        try:
            import win32gui, win32con
            win32gui.ShowWindow(self.remembered_target_hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.remembered_target_hwnd)
            time.sleep(0.05)
            return True
        except Exception:
            return False

    def is_exit_command(self, text: str) -> bool:
        """Checks if utterance is an explicit command to exit dictation."""
        cleaned = text.strip().lower().rstrip(".!,?")
        return cleaned in (
            "stop typing",
            "stop dictation",
            "exit dictation",
            "stop typing mode",
            "done typing",
            "finish dictation",
            "cancel dictation",
        )

    def is_ui_command(self, text: str) -> Optional[str]:
        """Classifies if utterance should be executed as a UI command instead of literal text."""
        cleaned = text.strip().lower().rstrip(".!,?")
        if cleaned in ("send", "submit", "press enter", "post", "enter"):
            return "submit"
        if cleaned in ("new line", "newline"):
            return "newline"
        if cleaned in ("new paragraph", "paragraph"):
            return "newparagraph"
        return None

    def execute_edit_action(self, action: str, target: Optional[str] = None, replacement: Optional[str] = None) -> Tuple[bool, str, str]:
        """Executes a voice edit action (backspace, undo, redo, delete word, replace, capitalize, etc.)."""
        action = action.lower().strip().replace(" ", "_")
        act_text = self.last_typed_text

        # Re-focus target before sending keystrokes
        self.refocus_target()

        if action == "backspace":
            _send_key(VK_BACK)
            if act_text:
                act_text = act_text[:-1]
            self.last_typed_text = act_text
            return True, act_text, "Character deleted via backspace."

        elif action in ("delete_last_word", "delete_word"):
            _send_combo([VK_CONTROL], VK_BACK)
            parts = act_text.rstrip().rsplit(" ", 1)
            act_text = parts[0] if len(parts) > 1 else ""
            self.last_typed_text = act_text
            return True, act_text, "Last word deleted."

        elif action in ("delete_last_sentence", "delete_sentence"):
            _send_combo([VK_SHIFT], VK_HOME)
            _send_key(VK_BACK)
            sentences = re.split(r"(?<=[.!?])\s+", act_text.strip())
            act_text = " ".join(sentences[:-1]) if len(sentences) > 1 else ""
            self.last_typed_text = act_text
            return True, act_text, "Last sentence deleted."

        elif action == "undo":
            _send_combo([VK_CONTROL], ord("Z"))
            return True, act_text, "Undo performed."

        elif action == "redo":
            _send_combo([VK_CONTROL], ord("Y"))
            return True, act_text, "Redo performed."

        elif action in ("select_last_sentence", "select_sentence"):
            _send_combo([VK_SHIFT], VK_HOME)
            return True, act_text, "Last sentence selected."

        elif action == "capitalize_that":
            words = act_text.rstrip().split(" ")
            if words:
                words[-1] = words[-1].capitalize()
                act_text = " ".join(words)
            _send_combo([VK_CONTROL], VK_BACK)
            if words:
                _type_unicode(words[-1] + " ")
            self.last_typed_text = act_text
            return True, act_text, "Capitalized."

        elif action == "make_that_lowercase":
            words = act_text.rstrip().split(" ")
            if words:
                words[-1] = words[-1].lower()
                act_text = " ".join(words)
            _send_combo([VK_CONTROL], VK_BACK)
            if words:
                _type_unicode(words[-1] + " ")
            self.last_typed_text = act_text
            return True, act_text, "Lowercased."

        elif action == "copy_that":
            _send_combo([VK_CONTROL], ord("C"))
            return True, act_text, "Copied to clipboard."

        elif action == "cut_that":
            _send_combo([VK_CONTROL], ord("X"))
            return True, act_text, "Cut to clipboard."

        elif action == "paste":
            _send_combo([VK_CONTROL], ord("V"))
            return True, act_text, "Pasted from clipboard."

        elif action == "replace":
            if target and replacement:
                if target in act_text:
                    act_text = act_text.replace(target, replacement, 1)
                    self.last_typed_text = act_text
                    return True, act_text, f"Replaced '{target}' with '{replacement}'."
                return False, act_text, f"Target '{target}' not found in active text buffer."

        return False, act_text, f"Unrecognized voice edit action: {action}"

    def type_streaming_delta(self, new_text: str, is_final: bool = False) -> str:
        """Live word-by-word streaming typing.
        Computes delta against last_stable_prefix, emits backspaces for any revised
        prefix, and types new text.
        """
        self.refocus_target()
        formatted = format_dictation(new_text)

        # Compute common prefix with last stable prefix
        prev = self.last_stable_prefix
        common_len = 0
        min_len = min(len(prev), len(formatted))
        while common_len < min_len and prev[common_len] == formatted[common_len]:
            common_len += 1

        backspaces_needed = len(prev) - common_len
        new_chars = formatted[common_len:]

        if backspaces_needed > 0:
            for _ in range(backspaces_needed):
                _send_key(VK_BACK)
        if new_chars:
            _type_unicode(new_chars)

        self.last_stable_prefix = formatted if not is_final else ""
        self.last_typed_text = formatted
        return formatted


_GLOBAL_DICTATION_MANAGER: Optional[DictationSessionManager] = None


def get_dictation_manager() -> DictationSessionManager:
    global _GLOBAL_DICTATION_MANAGER
    if _GLOBAL_DICTATION_MANAGER is None:
        _GLOBAL_DICTATION_MANAGER = DictationSessionManager()
    return _GLOBAL_DICTATION_MANAGER


# =====================================================================
# Tool Implementations
# =====================================================================

class DictationTool(Tool):
    definition = ToolDefinition(
        name="dictate_text",
        description="Formats and inserts spoken dictation into an active or chosen application without interpreting commands.",
        input_model=DictateInput,
        output_model=DictateOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("productivity", "dictation", "typing", "f03"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: DictateInput) -> dict[str, Any]:
        mgr = get_dictation_manager()
        formatted = format_dictation(arguments.text, arguments.auto_punctuate)
        target = arguments.target_app or mgr.remembered_target_title or "active_window"

        if not arguments.streaming:
            mgr.refocus_target()
            _type_unicode(formatted)

        mgr.last_typed_text = formatted

        return {
            "formatted_text": formatted,
            "target_app": target,
            "characters": len(formatted),
            "status": "inserted",
            "action_taken": "typed",
        }


class VoiceEditTool(Tool):
    definition = ToolDefinition(
        name="voice_edit",
        description="Performs voice-driven editing on active text: backspace, delete word, delete sentence, undo, redo, select, replace X with Y, capitalize, lowercase, copy, cut, paste.",
        input_model=VoiceEditInput,
        output_model=VoiceEditOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("productivity", "dictation", "edit", "voice"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: VoiceEditInput) -> dict[str, Any]:
        mgr = get_dictation_manager()
        success, res_text, msg = mgr.execute_edit_action(
            action=arguments.action,
            target=arguments.target_text,
            replacement=arguments.replacement_text,
        )
        return {
            "status": "SUCCESS" if success else "FAILED",
            "action": arguments.action,
            "result_text": res_text,
            "message": msg,
        }


class DictationModeControlTool(Tool):
    definition = ToolDefinition(
        name="dictation_mode_control",
        description="Explicitly activates or stops dictation mode for continuous voice typing into any active editable field.",
        input_model=DictationModeInput,
        output_model=DictationModeOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("productivity", "dictation", "mode"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: DictationModeInput) -> dict[str, Any]:
        mgr = get_dictation_manager()
        action = arguments.action.lower().strip()

        if action in ("start", "enable", "on"):
            target = mgr.start(arguments.target_app)
            return {
                "active": True,
                "target_app": target,
                "message": f"Dictation mode activated. Dictating into '{target}'. Say 'stop typing' when done.",
            }
        elif action in ("stop", "disable", "off"):
            target = mgr.stop()
            return {
                "active": False,
                "target_app": target,
                "message": f"Dictation mode stopped for '{target}'.",
            }
        elif action == "toggle":
            if mgr.is_active():
                target = mgr.stop()
                active = False
                msg = f"Dictation mode stopped for '{target}'."
            else:
                target = mgr.start(arguments.target_app)
                active = True
                msg = f"Dictation mode activated for '{target}'."
            return {"active": active, "target_app": target, "message": msg}
        else:
            return {
                "active": mgr.is_active(),
                "target_app": mgr.remembered_target_title,
                "message": f"Dictation mode is {'ACTIVE' if mgr.is_active() else 'INACTIVE'}.",
            }
