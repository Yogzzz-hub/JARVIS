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
    text: str = Field(default="", max_length=10000, description="Spoken text to format and type")
    target_app: Optional[str] = Field(default=None, max_length=256, description="Optional target app name or window title")
    action: Optional[str] = Field(default=None, description="Dictation action (e.g. start, insert)")
    auto_punctuate: bool = True
    streaming: bool = False


class DictateOutput(Contract):
    formatted_text: str
    target_app: str
    characters: int
    status: str
    action_taken: str = "formatted"


class VoiceEditInput(Contract):
    action: str = Field(description="Voice edit action: backspace, delete_word, delete_sentence, undo, redo, select_sentence, replace, capitalize, lowercase, copy, cut, paste, mixed")
    target_text: Optional[str] = Field(default=None, description="Text to replace or target")
    replacement_text: Optional[str] = Field(default=None, description="Replacement text")
    operations: Optional[list[dict[str, Any]]] = Field(default=None, description="Operations for mixed edit + insert")


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

        try:
            from jarvis.core.desktop.dictation_controller import get_dictation_controller
            get_dictation_controller().start(window_title=target_title or "")
        except Exception:
            pass

        # Target: a named window ("dictate in claude" -> the window whose title mentions Claude), else the active one
        try:
            import win32gui
            hwnd = 0
            if target_title and self.focus_app(target_title, wait_s=5.0):  # waits for an app that was just opened
                hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                self.remembered_target_hwnd = hwnd
                self.refocus_target()
            else:
                hwnd = win32gui.GetForegroundWindow()
                self.remembered_target_hwnd = hwnd
            self.remembered_target_title = win32gui.GetWindowText(hwnd) or target_title or "active window"
        except Exception:
            self.remembered_target_title = target_title or "active window"

        logger.info(f"Dictation mode started targeting: {self.remembered_target_title}")
        return self.remembered_target_title

    @staticmethod
    def _find_window(name: str) -> int:
        """Topmost visible window whose title contains ``name`` (case-insensitive); 0 when none."""
        try:
            import win32gui
        except Exception:
            return 0
        wanted = (name or "").lower().strip()
        found: list[int] = []

        def _cb(hwnd, _):
            if found or not win32gui.IsWindowVisible(hwnd):
                return
            title = (win32gui.GetWindowText(hwnd) or "").lower()
            if wanted and wanted in title and "jarvis" not in title:
                found.append(hwnd)
        try:
            win32gui.EnumWindows(_cb, None)
        except Exception:
            pass
        return found[0] if found else 0

    def focus_app(self, name: str, wait_s: float = 5.0) -> bool:
        """Bring the window whose title contains ``name`` to the front, waiting for a just-launched app to appear."""
        deadline = time.monotonic() + max(0.0, wait_s)
        while True:
            hwnd = self._find_window(name)
            if hwnd:
                try:
                    import win32gui, win32con
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.15)
                    return True
                except Exception:
                    return False
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.25)

    def stop(self) -> str:
        self.active_dictation_mode = False
        try:
            from jarvis.core.desktop.dictation_controller import get_dictation_controller
            get_dictation_controller().stop()
        except Exception:
            pass
        target = self.remembered_target_title
        logger.info(f"Dictation mode stopped for: {target}")
        return target

    def is_active(self) -> bool:
        try:
            from jarvis.core.desktop.dictation_controller import get_dictation_controller
            ctrl = get_dictation_controller()
            return ctrl.is_active or self.active_dictation_mode
        except Exception:
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


# Spoken edit commands while dictating (everything else is typed literally).
_DICTATION_EDITS = [
    (r"(?:send|send it|submit|press enter|enter|post it)", "submit"),
    (r"(?:new line|next line|newline|line break)", "newline"),
    (r"(?:new paragraph|next paragraph)", "newparagraph"),
    (r"(?:delete that|delete last word|delete the last word|scratch that)", "delete_last_word"),
    (r"(?:delete (?:the )?last sentence|delete sentence)", "delete_last_sentence"),
    (r"(?:backspace)", "backspace"),
    (r"(?:undo(?: that)?)", "undo"), (r"(?:redo(?: that)?)", "redo"),
    (r"(?:select all)", "select_all"), (r"(?:copy (?:that|all|it))", "copy_that"),
    (r"(?:cut (?:that|it))", "cut_that"), (r"(?:paste(?: it| that| here)?)", "paste"),
    (r"(?:capitali[sz]e that)", "capitalize_that"), (r"(?:make that lowercase|lowercase that)", "make_that_lowercase"),
]


def handle_dictation_utterance(text: str) -> tuple[bool, str]:
    """Voice input while dictation is on: type it into the remembered window, or run a spoken edit command."""
    mgr = get_dictation_manager()
    from jarvis.core.desktop.dictation_controller import (
        get_dictation_controller,
        classify_dictation_turn,
        DictationTurnType,
        DictationTurn,
    )
    ctrl = get_dictation_controller()

    if mgr.is_exit_command(text):
        target = mgr.stop()
        ctrl.stop()
        return False, f"Stopped typing into {target or 'the window'}."

    if ctrl.is_active:
        turn = classify_dictation_turn(text, ctrl.state)
        if turn is None:
            turn = DictationTurn(turn_type=DictationTurnType.TEXT, text=text)
        if turn.turn_type == DictationTurnType.GLOBAL_EMERGENCY_COMMAND:
            ctrl.stop()
            mgr.stop()
            return False, "Dictation cancelled."
        if turn.turn_type == DictationTurnType.DICTATION_CONTROL and turn.operation == "STOP_DICTATION":
            _, msg = ctrl.stop()
            mgr.stop()
            return False, msg
        ok, msg = ctrl.execute_turn(turn)
        return ctrl.is_active, msg

    # Legacy / session manager fallback (direct keystrokes and type_unicode)
    cleaned = text.strip().lower().rstrip(".!,?")
    for pattern, action in _DICTATION_EDITS:
        if re.fullmatch(pattern, cleaned):
            mgr.refocus_target()
            if action == "submit":
                _send_key(VK_RETURN)
                mgr.last_typed_text = ""
                return True, "Sent."
            if action in ("newline", "newparagraph"):
                for _ in range(1 if action == "newline" else 2):
                    _send_combo([VK_SHIFT], VK_RETURN)
                return True, "New line."
            if action == "select_all":
                _send_combo([VK_CONTROL], ord("A"))
                return True, "Selected all."
            ok, _, msg = mgr.execute_edit_action(action)
            return True, msg
    mgr.refocus_target()
    formatted = format_dictation(text)
    spacer = " " if mgr.last_typed_text and not mgr.last_typed_text.endswith((" ", "\n")) else ""
    _type_unicode(spacer + formatted)
    mgr.last_typed_text = (mgr.last_typed_text + spacer + formatted)[-2000:]
    return True, f"Typed: {formatted}"


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
        from jarvis.core.desktop.dictation_controller import get_dictation_controller
        formatted = format_dictation(arguments.text) if arguments.text else ""
        ctrl = get_dictation_controller()
        was_active = ctrl.is_active
        if not was_active:
            ctrl.start(app_name=arguments.target_app or "", initial_text=formatted)
            ctrl.stop()
        else:
            if formatted:
                ctrl.on_stable_text(formatted)
        return {
            "formatted_text": formatted or ctrl.buffer.committed_text or arguments.text,
            "target_app": ctrl.target.app_name or arguments.target_app or "active window",
            "characters": len(formatted or ctrl.buffer.committed_text or arguments.text),
            "status": "inserted",
            "action_taken": "typed",
        }


class VoiceEditTool(Tool):
    definition = ToolDefinition(
        name="voice_edit",
        description="Performs voice-driven editing on active text: backspace, delete word, delete sentence, undo, redo, select, replace X with Y, capitalize, lowercase, copy, cut, paste, mixed.",
        input_model=VoiceEditInput,
        output_model=VoiceEditOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("productivity", "dictation", "edit", "voice"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: VoiceEditInput) -> dict[str, Any]:
        from jarvis.core.desktop.dictation_controller import get_dictation_controller, DictationTurn, DictationTurnType
        ctrl = get_dictation_controller()
        if arguments.action == "mixed" and arguments.operations:
            turn = DictationTurn(
                turn_type=DictationTurnType.MIXED,
                operations=arguments.operations,
            )
            success, msg = ctrl.execute_turn(turn)
        else:
            success, msg = ctrl.execute_edit(
                action=arguments.action,
                target=arguments.target_text,
                replacement=arguments.replacement_text,
            )
        return {
            "status": "SUCCESS" if success else "FAILED",
            "action": arguments.action,
            "result_text": ctrl.buffer.committed_text,
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
        from jarvis.core.desktop.dictation_controller import get_dictation_controller, DictationState
        ctrl = get_dictation_controller()
        action = arguments.action.lower().strip()

        if action in ("start", "enable", "on", "begin", "resume", "play"):
            if ctrl.state == DictationState.PAUSED:
                success, msg = ctrl.resume()
            else:
                success, msg = ctrl.start(app_name=arguments.target_app or "")
            target = ctrl.target.app_name or "active window"
            return {
                "active": ctrl.is_active,
                "target_app": target,
                "message": msg,
            }
        elif action in ("stop", "disable", "off", "end", "pause", "exit"):
            if action == "pause":
                ctrl.pause("tool command")
                return {
                    "active": False,
                    "target_app": ctrl.target.app_name,
                    "message": "Dictation paused.",
                }
            success, msg = ctrl.stop()
            return {
                "active": False,
                "target_app": ctrl.target.app_name,
                "message": msg,
            }
        elif action == "toggle":
            if ctrl.is_active:
                success, msg = ctrl.stop()
                active = False
            else:
                success, msg = ctrl.start(app_name=arguments.target_app or "")
                active = True
            return {"active": active, "target_app": ctrl.target.app_name, "message": msg}
        else:
            return {
                "active": ctrl.is_active,
                "target_app": ctrl.target.app_name,
                "message": f"Dictation mode is {'ACTIVE' if ctrl.is_active else 'INACTIVE'}.",
            }
