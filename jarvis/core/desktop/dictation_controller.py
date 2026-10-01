"""DictationController — Voice-driven dictation state machine for JARVIS EDGE.

Manages the full dictation lifecycle:
  IDLE → ARMED → DICTATING → EDITING / PAUSED / CODE_MODE → STOPPING → IDLE

Safety invariants:
- Never types into unknown or unfocused window (FocusGuard)
- Never executes dictation text as commands
- Wake word always exits dictation immediately
- Focus loss → immediate pause
- Scoped buffer editing: edits only alter the JARVIS-owned dictated range.
"""
from __future__ import annotations

import enum
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from jarvis.core.desktop.focus_guard import FocusGuard, FocusState
from jarvis.tools.system.input_layer import (
    type_text,
    type_unicode,
    send_key,
    send_combo,
    get_foreground_hwnd,
    get_window_title,
    get_foreground_process_name,
    verify_focus,
    VK,
)

logger = logging.getLogger("jarvis.desktop.dictation_controller")


# =====================================================================
# Enums & Models
# =====================================================================

class DictationState(str, enum.Enum):
    """Dictation controller states."""
    IDLE = "IDLE"               # No dictation active
    ARMED = "ARMED"             # Acquiring target focus
    DICTATING = "DICTATING"     # Active typing from voice
    EDITING = "EDITING"         # Voice edit command in progress
    CODE_MODE = "CODE_MODE"     # Code dictation mode
    PAUSED = "PAUSED"           # Paused due to focus loss or user command
    STOPPING = "STOPPING"       # Flushing buffer, cleaning up


class DictationMode(str, enum.Enum):
    """Active formatting mode for dictation."""
    NORMAL = "normal"
    CODE = "code"
    SPELLING = "spelling"
    NUMBER = "number"


class ClassificationResult(str, enum.Enum):
    """Result of command vs dictation classification."""
    TEXT = "TEXT"           # Type as dictated text
    COMMAND = "COMMAND"    # Route to command processor
    VOICE_EDIT = "VOICE_EDIT"  # Voice editing command (within dictation)
    MODE_CHANGE = "MODE_CHANGE"  # Change dictation mode
    STOP = "STOP"          # Stop dictation


class DictationTurnType(str, enum.Enum):
    """Classification of a single turn during dictation mode."""
    TEXT = "TEXT"
    EDIT_COMMAND = "EDIT_COMMAND"
    DICTATION_CONTROL = "DICTATION_CONTROL"
    GLOBAL_EMERGENCY_COMMAND = "GLOBAL_EMERGENCY_COMMAND"
    MIXED = "MIXED"
    LITERAL_TEXT = "LITERAL_TEXT"
    START_DICTATION = "START_DICTATION"


@dataclass
class DictationTurn:
    """Parsed representation of a dictation turn."""
    turn_type: DictationTurnType
    text: str = ""
    operation: str = ""
    slots: Dict[str, Any] = field(default_factory=dict)
    operations: List[Dict[str, Any]] = field(default_factory=list)
    escape_command: str = ""


@dataclass
class DictationBuffer:
    """Maintains text range, committed history, and undo stack for dictation."""
    target_window_id: int = 0
    target_control_id: str = ""
    dictation_start_position: int = 0
    committed_text: str = ""
    recent_committed_spans: List[str] = field(default_factory=list)
    pending_partial: str = ""
    selection: Tuple[int, int] = (0, 0)
    undo_stack: List[str] = field(default_factory=list)
    redo_stack: List[str] = field(default_factory=list)

    def append(self, text: str) -> None:
        if not text:
            return
        self.undo_stack.append(self.committed_text)
        self.committed_text += text
        self.recent_committed_spans.append(text)
        if len(self.recent_committed_spans) > 30:
            self.recent_committed_spans.pop(0)

    def delete_last_word(self) -> Tuple[bool, str]:
        if not self.committed_text:
            return False, ""
        self.undo_stack.append(self.committed_text)
        parts = self.committed_text.rstrip().rsplit(" ", 1)
        if len(parts) > 1:
            deleted = self.committed_text.rstrip()[len(parts[0]):].strip()
            self.committed_text = parts[0]
        else:
            deleted = self.committed_text
            self.committed_text = ""
        return True, deleted

    def delete_last_sentence(self) -> Tuple[bool, str]:
        if not self.committed_text:
            return False, ""
        self.undo_stack.append(self.committed_text)
        # Split on sentence terminals
        sentences = re.split(r"(?<=[.!?\n])\s+", self.committed_text.strip())
        if len(sentences) > 1:
            deleted = sentences[-1]
            self.committed_text = " ".join(sentences[:-1])
        else:
            deleted = self.committed_text
            self.committed_text = ""
        return True, deleted

    def replace_text(self, old_text: str, new_text: str) -> Tuple[bool, str]:
        if not old_text:
            return False, "No target text specified."
        pattern = re.compile(re.escape(old_text), re.IGNORECASE)
        matches = list(pattern.finditer(self.committed_text))
        if not matches:
            return False, f"I couldn't find {old_text} in the dictated text."
        self.undo_stack.append(self.committed_text)
        # Replace the nearest (most recent) match
        last_match = matches[-1]
        start, end = last_match.span()
        self.committed_text = self.committed_text[:start] + new_text + self.committed_text[end:]
        return True, f"Replaced '{old_text}' with '{new_text}'."

    def capitalize_previous_word(self) -> Tuple[bool, str]:
        if not self.committed_text:
            return False, ""
        words = self.committed_text.rstrip().split(" ")
        if not words:
            return False, ""
        self.undo_stack.append(self.committed_text)
        target = words[-1]
        capitalized = target.capitalize()
        words[-1] = capitalized
        self.committed_text = " ".join(words)
        return True, capitalized

    def lowercase_previous_word(self) -> Tuple[bool, str]:
        if not self.committed_text:
            return False, ""
        words = self.committed_text.rstrip().split(" ")
        if not words:
            return False, ""
        self.undo_stack.append(self.committed_text)
        target = words[-1]
        lowered = target.lower()
        words[-1] = lowered
        self.committed_text = " ".join(words)
        return True, lowered

    def undo(self) -> Tuple[bool, str]:
        if not self.undo_stack:
            return False, "Nothing to undo."
        self.redo_stack.append(self.committed_text)
        self.committed_text = self.undo_stack.pop()
        return True, "Undo performed."

    def redo(self) -> Tuple[bool, str]:
        if not self.redo_stack:
            return False, "Nothing to redo."
        self.undo_stack.append(self.committed_text)
        self.committed_text = self.redo_stack.pop()
        return True, "Redo performed."

    def reconcile_partial(self, raw_partial: str, stable_prefix: str) -> str:
        prev = self.pending_partial or ""
        common_len = 0
        min_len = min(len(prev), len(raw_partial))
        while common_len < min_len and prev[common_len] == raw_partial[common_len]:
            common_len += 1
        self.pending_partial = raw_partial
        delta = raw_partial[common_len:]
        return delta


@dataclass
class DictationTarget:
    """Tracks the target for active dictation."""
    app_name: str = ""
    window_title: str = ""
    window_hwnd: int = 0
    control_id: str = ""
    control_name: str = ""
    focus_verified: bool = False
    started_at: float = 0.0
    total_committed: int = 0
    last_commit_at: float = 0.0
    mode: DictationMode = DictationMode.NORMAL


@dataclass
class DictationDiagnostics:
    """Accumulated diagnostics for a dictation session."""
    state_transitions: List[Tuple[str, str, float]] = field(default_factory=list)
    commits: int = 0
    total_characters: int = 0
    focus_checks: int = 0
    focus_failures: int = 0
    commands_classified: int = 0
    texts_classified: int = 0
    started_at: float = 0.0
    ended_at: float = 0.0


# =====================================================================
# Semantic Classifier & Interpreter
# =====================================================================

VOICE_EDIT_PATTERNS = {
    "backspace", "delete", "undo", "redo",
    "delete word", "delete last word", "delete sentence", "delete last sentence",
    "select last sentence", "select all",
    "copy that", "cut that", "paste",
}

MODE_CHANGE_PATTERNS = {
    "code mode", "coding mode", "start code mode",
    "normal mode", "stop code mode",
    "spelling mode", "start spelling mode", "stop spelling mode",
    "number mode", "start number mode", "stop number mode",
}

STOP_PATTERNS = {
    "stop typing", "stop dictation", "done typing", "done dictating",
    "finish typing", "end typing", "end dictation",
    "pause typing", "pause dictation",
}


def classify_dictation_turn(text: str, state: DictationState) -> Optional[DictationTurn]:
    """Classifies an utterance locally when dictation is active or requested.

    Returns DictationTurn with semantic operation, or None if utterance should pass to global router.
    """
    if not text:
        return None

    cleaned = text.strip()
    lowered = cleaned.lower().rstrip(".!,?")

    # 1. Literal Mode: "type literally <text>", "write literally <text>"
    m_lit = re.match(r"^(?:type|write)\s+literally\s+(?P<txt>.+)$", cleaned, re.IGNORECASE)
    if m_lit:
        return DictationTurn(
            turn_type=DictationTurnType.LITERAL_TEXT,
            text=m_lit.group("txt").strip(),
        )

    # 2. Global Emergency / Command Escape
    m_escape = re.match(r"^(?:(?:hey\s+)?jarvis,?\s+)?(?:stop\s+(?:typing|dictation|dictating)\s+(?:and|then)\s+)(?P<cmd>.+)$", cleaned, re.IGNORECASE)
    if m_escape:
        return DictationTurn(
            turn_type=DictationTurnType.GLOBAL_EMERGENCY_COMMAND,
            escape_command=m_escape.group("cmd").strip(),
        )

    if re.match(r"^(?:(?:hey\s+)?jarvis,?\s+)?(?:emergency stop|cancel dictation)$", lowered):
        return DictationTurn(
            turn_type=DictationTurnType.GLOBAL_EMERGENCY_COMMAND,
            escape_command="cancel",
        )

    # 3. State-Dependent: PAUSED -> RESUME
    if state == DictationState.PAUSED:
        if re.match(r"^(?:continue|resume|carry on|keep going|continue typing|resume typing|continue from where i stopped|go on)$", lowered):
            return DictationTurn(
                turn_type=DictationTurnType.DICTATION_CONTROL,
                operation="RESUME",
            )

    # 4. Dictation Control (Stop / Pause)
    if state in (DictationState.DICTATING, DictationState.EDITING, DictationState.CODE_MODE, DictationState.PAUSED):
        if re.match(r"^(?:stop typing|stop dictation|done typing|done dictating|finish typing|end typing|end dictation|exit dictation)$", lowered):
            return DictationTurn(
                turn_type=DictationTurnType.DICTATION_CONTROL,
                operation="STOP_DICTATION",
            )
        if re.match(r"^(?:pause typing|pause dictation|pause|hold on|take a break)$", lowered):
            return DictationTurn(
                turn_type=DictationTurnType.DICTATION_CONTROL,
                operation="PAUSE",
            )

    # 5. Mixed Edit Command + Text (only during active dictation)
    if state in (DictationState.DICTATING, DictationState.EDITING, DictationState.CODE_MODE):
        m_mix = re.match(
            r"^(?P<edit>new paragraph|next paragraph|paragraph|new line|newline|next line|line break)"
            r"\s*[,.:;—\-]?\s+(?P<rest>[A-Za-z0-9].+)$",
            cleaned,
            re.IGNORECASE,
        )
        if m_mix:
            edit_word = m_mix.group("edit").lower()
            op_type = "NEW_PARAGRAPH" if "paragraph" in edit_word else "NEW_LINE"
            rest_text = m_mix.group("rest").strip()
            return DictationTurn(
                turn_type=DictationTurnType.MIXED,
                operations=[
                    {"type": op_type},
                    {"type": "INSERT_TEXT", "text": rest_text},
                ],
            )

    # 6. Voice Edit Commands (during active dictation)
    if state in (DictationState.DICTATING, DictationState.EDITING, DictationState.CODE_MODE):
        # Replace X with Y
        m_rep = re.match(r"^replace\s+(?P<old>.+?)\s+with\s+(?P<new>.+?)[.!?]?$", cleaned, re.IGNORECASE)
        if m_rep:
            return DictationTurn(
                turn_type=DictationTurnType.EDIT_COMMAND,
                operation="REPLACE_TEXT",
                slots={
                    "target_text": m_rep.group("old").strip(),
                    "replacement_text": m_rep.group("new").strip(),
                },
            )

        # Capitalize previous word
        if re.match(r"^(?:capitali[sz]e)\s+(?:the\s+)?(?:previous\s+word|last\s+word|that|it)$", lowered):
            return DictationTurn(
                turn_type=DictationTurnType.EDIT_COMMAND,
                operation="CAPITALIZE_PREVIOUS",
            )

        # Lowercase previous word
        if re.match(r"^(?:(?:make\s+(?:the\s+previous\s+word|that|it)\s+lowercase)|(?:lowercase\s+(?:the\s+)?(?:previous\s+word|last\s+word|that|it)))$", lowered):
            return DictationTurn(
                turn_type=DictationTurnType.EDIT_COMMAND,
                operation="LOWERCASE_PREVIOUS",
            )

        # Delete sentence
        if re.match(r"^(?:delete|remove)\s+(?:the\s+)?(?:last|previous)\s+sentence$", lowered):
            return DictationTurn(
                turn_type=DictationTurnType.EDIT_COMMAND,
                operation="DELETE_LAST_SENTENCE",
            )

        # Delete word
        if re.match(r"^(?:delete|remove|scratch)\s+(?:(?:the\s+)?(?:last|previous)\s+word|that)$", lowered):
            return DictationTurn(
                turn_type=DictationTurnType.EDIT_COMMAND,
                operation="DELETE_LAST_WORD",
            )

        # Standard edit commands
        if lowered in ("backspace", "delete"):
            return DictationTurn(turn_type=DictationTurnType.EDIT_COMMAND, operation="BACKSPACE")
        if lowered in ("undo", "undo that"):
            return DictationTurn(turn_type=DictationTurnType.EDIT_COMMAND, operation="UNDO")
        if lowered in ("redo", "redo that"):
            return DictationTurn(turn_type=DictationTurnType.EDIT_COMMAND, operation="REDO")
        if lowered == "select all":
            return DictationTurn(turn_type=DictationTurnType.EDIT_COMMAND, operation="SELECT_ALL")
        if lowered in ("copy that", "copy"):
            return DictationTurn(turn_type=DictationTurnType.EDIT_COMMAND, operation="COPY")
        if lowered in ("cut that", "cut"):
            return DictationTurn(turn_type=DictationTurnType.EDIT_COMMAND, operation="CUT")
        if lowered in ("paste", "paste that"):
            return DictationTurn(turn_type=DictationTurnType.EDIT_COMMAND, operation="PASTE")
        if lowered in ("new line", "newline", "next line"):
            return DictationTurn(turn_type=DictationTurnType.EDIT_COMMAND, operation="NEW_LINE")
        if lowered in ("new paragraph", "next paragraph", "paragraph"):
            return DictationTurn(turn_type=DictationTurnType.EDIT_COMMAND, operation="NEW_PARAGRAPH")

    # 7. Start Dictation (when state == IDLE)
    if state == DictationState.IDLE:
        m_start_colon = re.match(r"^(?:start typing|start dictation|begin typing|dictate|type)\s*[:,\-—]\s*(?P<txt>.+)$", cleaned, re.IGNORECASE)
        if m_start_colon:
            return DictationTurn(
                turn_type=DictationTurnType.START_DICTATION,
                text=m_start_colon.group("txt").strip(),
            )

        m_start_app = re.match(r"^(?:start typing|begin typing|type mode)(?:\s+(?:here|in this (?:box|field|text ?box)|"
                               r"(?:in|into|on)\s+(?P<app>[\w\s]+?)))?$", lowered)
        if m_start_app:
            return DictationTurn(
                turn_type=DictationTurnType.START_DICTATION,
                slots={"app": m_start_app.group("app").strip() if m_start_app.group("app") else ""},
            )

        m_type_lit = re.match(r"^(?:type literally)\s+(?P<txt>.+)$", cleaned, re.IGNORECASE)
        if m_type_lit:
            return DictationTurn(
                turn_type=DictationTurnType.START_DICTATION,
                text=m_type_lit.group("txt").strip(),
            )

    # 8. If dictation is active and not caught by commands, it is LITERAL TEXT to type!
    if state in (DictationState.DICTATING, DictationState.EDITING, DictationState.CODE_MODE):
        return DictationTurn(
            turn_type=DictationTurnType.TEXT,
            text=cleaned,
        )

    return None


def classify_dictation_input(text: str) -> Tuple[ClassificationResult, str]:
    """Backwards-compatible classification helper."""
    normalized = text.strip().lower()
    if normalized.startswith(("hey jarvis", "jarvis", "ok jarvis")):
        return ClassificationResult.COMMAND, normalized
    if normalized in STOP_PATTERNS:
        return ClassificationResult.STOP, normalized
    if normalized.startswith("replace ") and " with " in normalized:
        return ClassificationResult.VOICE_EDIT, normalized
    if normalized.startswith("capitalize ") or (normalized.startswith("make ") and "lowercase" in normalized):
        return ClassificationResult.VOICE_EDIT, normalized
    if normalized in VOICE_EDIT_PATTERNS:
        return ClassificationResult.VOICE_EDIT, normalized
    if normalized in MODE_CHANGE_PATTERNS:
        return ClassificationResult.MODE_CHANGE, normalized
    return ClassificationResult.TEXT, text


# =====================================================================
# DictationController
# =====================================================================

class DictationController:
    """State machine for voice-driven dictation with FocusGuard and DictationBuffer."""

    def __init__(
        self,
        event_bus: Optional[Any] = None,
        on_state_change: Optional[Callable[[DictationState, DictationState], None]] = None,
    ) -> None:
        self._state = DictationState.IDLE
        self._target = DictationTarget()
        self._buffer = DictationBuffer()
        self._focus_guard = FocusGuard(
            on_focus_lost=self._handle_focus_lost,
            on_focus_restored=self._handle_focus_restored,
        )
        self._event_bus = event_bus
        self._on_state_change = on_state_change
        self._diagnostics = DictationDiagnostics()
        self._committed_text = ""
        self._pending_buffer = ""
        self._test_target: Optional[DictationTarget] = None

    # -----------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------

    @property
    def state(self) -> DictationState:
        return self._state

    @property
    def target(self) -> DictationTarget:
        return self._test_target or self._target

    @property
    def buffer(self) -> DictationBuffer:
        return self._buffer

    @property
    def is_active(self) -> bool:
        return self._state in (
            DictationState.DICTATING,
            DictationState.EDITING,
            DictationState.CODE_MODE,
            DictationState.PAUSED,
        )

    @property
    def mode(self) -> DictationMode:
        return self._target.mode

    @property
    def diagnostics(self) -> DictationDiagnostics:
        return self._diagnostics

    # -----------------------------------------------------------------
    # Target & Focus Safety
    # -----------------------------------------------------------------

    def set_test_target(
        self,
        app_name: str = "Notepad",
        window_title: str = "Untitled - Notepad",
        hwnd: int = 12345,
        is_editable: bool = True,
    ) -> None:
        """Sets a deterministic target for testing without live OS window dependence."""
        self._test_target = DictationTarget(
            app_name=app_name,
            window_title=window_title,
            window_hwnd=hwnd,
            focus_verified=is_editable,
            started_at=time.time(),
        )
        self._focus_guard.set_target(hwnd, app_name, window_title)

    def clear_test_target(self) -> None:
        self._test_target = None
        self._focus_guard.clear()

    def has_editable_target(self) -> bool:
        """Checks if a verified editable target is focused."""
        if self._test_target is not None:
            return self._test_target.focus_verified
        hwnd = get_foreground_hwnd()
        if not hwnd:
            return False
        proc = get_foreground_process_name().lower()
        if not proc or proc in ("explorer.exe", "shellexperiencehost.exe", "searchhost.exe"):
            title = get_window_title(hwnd).lower()
            if "desktop" in title or not title:
                return False
        return True

    def _verify_focus_safe(self) -> bool:
        if self._test_target is not None:
            return self._test_target.focus_verified
        if not self._focus_guard.check():
            self.pause("focus lost")
            return False
        return True

    # -----------------------------------------------------------------
    # State Transitions
    # -----------------------------------------------------------------

    def _set_state(self, new_state: DictationState, reason: str = "") -> None:
        old_state = self._state
        if old_state == new_state:
            return
        self._state = new_state
        self._diagnostics.state_transitions.append(
            (old_state.value, new_state.value, time.time())
        )
        logger.info(
            "DictationController: %s → %s (reason: %s)",
            old_state.value, new_state.value, reason,
        )
        if self._event_bus:
            try:
                self._event_bus.emit("dictation.state_change", {
                    "from": old_state.value,
                    "to": new_state.value,
                    "target": self._target.app_name,
                    "trigger": reason,
                })
            except Exception:
                pass
        if self._on_state_change:
            try:
                self._on_state_change(old_state, new_state)
            except Exception:
                pass

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    def start(
        self,
        app_name: str = "",
        window_title: str = "",
        mode: str = "normal",
        initial_text: str = "",
    ) -> Tuple[bool, str]:
        if self._state not in (DictationState.IDLE, DictationState.PAUSED):
            return False, f"Cannot start: already in {self._state.value} state"

        self._set_state(DictationState.ARMED, "start requested")
        self._diagnostics = DictationDiagnostics(started_at=time.time())
        self._committed_text = ""
        self._pending_buffer = ""
        self._buffer = DictationBuffer()

        try:
            dictation_mode = DictationMode(mode.lower()) if mode else DictationMode.NORMAL
        except ValueError:
            dictation_mode = DictationMode.NORMAL

        if self._test_target is not None:
            self._target = self._test_target
            self._target.mode = dictation_mode
            self._set_state(DictationState.DICTATING, "test target verified")
            if initial_text:
                self.on_stable_text(initial_text)
            return True, f"Typing mode active in {self._target.app_name}"

        hwnd = get_foreground_hwnd()
        if not hwnd and not app_name:
            self._set_state(DictationState.IDLE, "no foreground window")
            return False, "Where should I type?"

        proc = get_foreground_process_name()
        title = get_window_title(hwnd) if hwnd else ""

        self._target = DictationTarget(
            app_name=app_name or proc or "Active Window",
            window_title=window_title or title,
            window_hwnd=hwnd,
            focus_verified=bool(hwnd),
            started_at=time.time(),
            mode=dictation_mode,
        )

        if hwnd:
            self._focus_guard.set_target(hwnd, proc, title)
            if not self._focus_guard.check():
                self._set_state(DictationState.IDLE, "focus verification failed")
                self._focus_guard.clear()
                return False, "Where should I type?"

        self._set_state(DictationState.DICTATING, "focus verified")
        if initial_text:
            self.on_stable_text(initial_text)
        return True, f"Typing mode active in {self._target.app_name}"

    def stop(self) -> Tuple[bool, str]:
        if self._state == DictationState.IDLE:
            return True, "Already idle"

        self._set_state(DictationState.STOPPING, "stop requested")
        if self._pending_buffer and self._verify_focus_safe():
            typed, _ = type_text(self._pending_buffer)
            self._buffer.append(self._pending_buffer)
            self._target.total_committed += typed
            self._diagnostics.total_characters += typed
            self._pending_buffer = ""

        total = self._target.total_committed
        app = self._target.app_name or "active window"
        self._diagnostics.ended_at = time.time()
        self._focus_guard.clear()
        self._target = DictationTarget()
        self._set_state(DictationState.IDLE, "stopped")
        return True, f"Typing done. {total} characters typed in {app}."

    def pause(self, reason: str = "user request") -> None:
        if self._state in (DictationState.DICTATING, DictationState.CODE_MODE, DictationState.EDITING):
            self._set_state(DictationState.PAUSED, reason)

    def resume(self) -> Tuple[bool, str]:
        if self._state != DictationState.PAUSED:
            return False, f"Cannot resume: in {self._state.value} state"

        if not self._verify_focus_safe():
            if not self._focus_guard.attempt_refocus():
                return False, "Cannot resume: target window not focused"

        self._set_state(DictationState.DICTATING, "resumed")
        if self._pending_buffer:
            typed, _ = type_text(self._pending_buffer)
            self._buffer.append(self._pending_buffer)
            self._target.total_committed += typed
            self._diagnostics.total_characters += typed
            self._pending_buffer = ""

        return True, f"Resumed typing in {self._target.app_name}"

    def cancel(self) -> Tuple[bool, str]:
        self._pending_buffer = ""
        return self.stop()

    # -----------------------------------------------------------------
    # Turn Execution & Voice Editing
    # -----------------------------------------------------------------

    def execute_turn(self, turn: DictationTurn) -> Tuple[bool, str]:
        """Executes a classified dictation turn."""
        if turn.turn_type == DictationTurnType.LITERAL_TEXT:
            if not self._verify_focus_safe():
                return False, "Focus lost, paused"
            formatted = turn.text
            typed, _ = type_text(formatted)
            self._buffer.append(formatted)
            self._target.total_committed += typed
            return True, f"Typed: {formatted}"

        if turn.turn_type == DictationTurnType.TEXT:
            if not self._verify_focus_safe():
                self.pause("focus lost")
                return False, "Focus lost, paused"
            _, msg = self.on_stable_text(turn.text)
            return True, msg

        if turn.turn_type == DictationTurnType.EDIT_COMMAND:
            return self.execute_edit(turn.operation, turn.slots.get("target_text"), turn.slots.get("replacement_text"))

        if turn.turn_type == DictationTurnType.MIXED:
            # Apply all operations in sequence
            res_messages = []
            for op in turn.operations:
                op_type = op.get("type", "")
                if op_type == "INSERT_TEXT":
                    txt = op.get("text", "")
                    _, m = self.on_stable_text(txt)
                    res_messages.append(m)
                else:
                    ok, msg = self.execute_edit(op_type)
                    res_messages.append(msg)
            return True, " ".join(res_messages)

        if turn.turn_type == DictationTurnType.DICTATION_CONTROL:
            op = turn.operation.upper()
            if op == "RESUME":
                return self.resume()
            elif op == "PAUSE":
                self.pause("user request")
                return True, "Dictation paused."
            elif op == "STOP_DICTATION":
                return self.stop()

        if turn.turn_type == DictationTurnType.START_DICTATION:
            if not self.has_editable_target() and not turn.slots.get("app"):
                return False, "Where should I type?"
            return self.start(app_name=turn.slots.get("app", ""), initial_text=turn.text)

        return False, "Unhandled dictation turn."

    def execute_edit(self, action: str, target: Optional[str] = None, replacement: Optional[str] = None) -> Tuple[bool, str]:
        """Executes a voice edit action on the DictationBuffer and input layer."""
        action_clean = action.lower().strip().replace(" ", "_")
        self._set_state(DictationState.EDITING, f"edit: {action_clean}")

        if not self._verify_focus_safe():
            self._set_state(DictationState.PAUSED, "focus lost before edit")
            return False, "Focus lost, paused"

        if action_clean in ("new_paragraph",):
            for _ in range(2):
                send_combo([VK.SHIFT], VK.RETURN)
            self._buffer.append("\n\n")
            self._set_state(DictationState.DICTATING, "edit complete")
            return True, "New paragraph."

        if action_clean in ("new_line", "newline"):
            send_combo([VK.SHIFT], VK.RETURN)
            self._buffer.append("\n")
            self._set_state(DictationState.DICTATING, "edit complete")
            return True, "New line."

        if action_clean in ("delete_last_word", "delete_word"):
            send_combo([VK.CONTROL], VK.BACK)
            ok, deleted = self._buffer.delete_last_word()
            self._set_state(DictationState.DICTATING, "edit complete")
            return True, f"Deleted word: {deleted}" if deleted else "Last word deleted."

        if action_clean in ("delete_last_sentence", "delete_sentence"):
            send_combo([VK.SHIFT], VK.HOME)
            send_key(VK.BACK)
            ok, deleted = self._buffer.delete_last_sentence()
            self._set_state(DictationState.DICTATING, "edit complete")
            return True, f"Deleted sentence: {deleted}" if deleted else "Last sentence deleted."

        if action_clean in ("backspace",):
            send_key(VK.BACK)
            if self._buffer.committed_text:
                self._buffer.committed_text = self._buffer.committed_text[:-1]
            self._set_state(DictationState.DICTATING, "edit complete")
            return True, "Character deleted via backspace."

        if action_clean in ("replace_text", "replace"):
            ok, msg = self._buffer.replace_text(target or "", replacement or "")
            self._set_state(DictationState.DICTATING, "edit complete")
            return ok, msg

        if action_clean in ("capitalize_previous", "capitalize_previous_word", "capitalize_that", "capitalize"):
            ok, word = self._buffer.capitalize_previous_word()
            send_combo([VK.CONTROL], VK.BACK)
            if word:
                type_unicode(word + " ")
            self._set_state(DictationState.DICTATING, "edit complete")
            return True, "Capitalized."

        if action_clean in ("lowercase_previous", "lowercase_previous_word", "make_that_lowercase", "lowercase"):
            ok, word = self._buffer.lowercase_previous_word()
            send_combo([VK.CONTROL], VK.BACK)
            if word:
                type_unicode(word + " ")
            self._set_state(DictationState.DICTATING, "edit complete")
            return True, "Lowercased."

        if action_clean == "undo":
            send_combo([VK.CONTROL], ord("Z"))
            ok, msg = self._buffer.undo()
            self._set_state(DictationState.DICTATING, "edit complete")
            return True, msg

        if action_clean == "redo":
            send_combo([VK.CONTROL], ord("Y"))
            ok, msg = self._buffer.redo()
            self._set_state(DictationState.DICTATING, "edit complete")
            return True, msg

        if action_clean == "select_all":
            send_combo([VK.CONTROL], ord("A"))
            self._set_state(DictationState.DICTATING, "edit complete")
            return True, "Selected all."

        if action_clean in ("copy_that", "copy"):
            send_combo([VK.CONTROL], ord("C"))
            self._set_state(DictationState.DICTATING, "edit complete")
            return True, "Copied to clipboard."

        if action_clean in ("cut_that", "cut"):
            send_combo([VK.CONTROL], ord("X"))
            self._set_state(DictationState.DICTATING, "edit complete")
            return True, "Cut to clipboard."

        if action_clean == "paste":
            send_combo([VK.CONTROL], ord("V"))
            self._set_state(DictationState.DICTATING, "edit complete")
            return True, "Pasted from clipboard."

        self._set_state(DictationState.DICTATING, "unrecognized edit")
        return False, f"Unrecognized voice edit action: {action}"

    # -----------------------------------------------------------------
    # Text Streaming
    # -----------------------------------------------------------------

    def on_stable_text(self, text: str) -> Tuple[ClassificationResult, str]:
        if not self.is_active:
            return ClassificationResult.COMMAND, "Not in dictation mode"

        if self._state == DictationState.PAUSED:
            self._pending_buffer += text
            return ClassificationResult.TEXT, "Buffered (paused)"

        if not self._verify_focus_safe():
            self._pending_buffer += text
            self.pause("focus lost during commit")
            return ClassificationResult.TEXT, "Focus lost, paused"

        formatted = self._format_text(text)
        typed, method = type_text(formatted)
        self._buffer.append(formatted)
        self._target.total_committed += typed
        self._target.last_commit_at = time.time()
        self._committed_text += formatted
        self._diagnostics.commits += 1
        self._diagnostics.total_characters += typed
        self._diagnostics.texts_classified += 1

        if self._event_bus:
            try:
                self._event_bus.emit("dictation.commit", {
                    "text_length": typed,
                    "method": method,
                    "target": self._target.app_name,
                    "focus_verified": True,
                })
            except Exception:
                pass

        return ClassificationResult.TEXT, f"Typed: {formatted}"

    def on_delta_text(self, delta: str) -> bool:
        if self._state not in (DictationState.DICTATING, DictationState.CODE_MODE):
            if self._state == DictationState.PAUSED:
                self._pending_buffer += delta
            return False

        if not self._verify_focus_safe():
            self._pending_buffer += delta
            self.pause("focus lost during delta commit")
            return False

        typed = type_unicode(delta)
        self._buffer.append(delta)
        self._target.total_committed += typed
        self._target.last_commit_at = time.time()
        self._committed_text += delta
        self._diagnostics.commits += 1
        self._diagnostics.total_characters += typed
        return True

    # -----------------------------------------------------------------
    # Formatters
    # -----------------------------------------------------------------

    def _format_text(self, text: str) -> str:
        mode = self._target.mode
        if mode == DictationMode.NORMAL:
            return self._format_normal(text)
        elif mode == DictationMode.CODE:
            return self._format_code(text)
        elif mode == DictationMode.SPELLING:
            return self._format_spelling(text)
        elif mode == DictationMode.NUMBER:
            return self._format_number(text)
        return text

    def _format_normal(self, text: str) -> str:
        replacements = {
            "period": ".", "full stop": ".", "comma": ",",
            "question mark": "?", "exclamation mark": "!", "exclamation point": "!",
            "colon": ":", "semicolon": ";",
            "open quote": '"', "close quote": '"',
            "open parenthesis": "(", "close parenthesis": ")",
            "dash": "—", "hyphen": "-", "ellipsis": "...",
            "new line": "\n", "newline": "\n", "new paragraph": "\n\n",
        }
        result = text
        for spoken, char in replacements.items():
            result = re.sub(rf"\b{re.escape(spoken)}\b", char, result, flags=re.IGNORECASE)
        return result

    def _format_code(self, text: str) -> str:
        replacements = {
            "open paren": "(", "close paren": ")",
            "open bracket": "[", "close bracket": "]",
            "open brace": "{", "close brace": "}",
            "equals": "=", "double equals": "==",
            "not equals": "!=", "arrow": "->",
            "fat arrow": "=>", "plus": "+", "minus": "-",
            "times": "*", "divide": "/",
            "semicolon": ";", "colon": ":",
            "dot": ".", "comma": ",",
            "new line": "\n", "indent": "    ",
            "tab": "\t",
        }
        result = text
        for spoken, char in replacements.items():
            result = re.sub(rf"\b{re.escape(spoken)}\b", char, result, flags=re.IGNORECASE)
        result = re.sub(r"\bunderscore\b", "_", result, flags=re.IGNORECASE)
        return result

    def _format_spelling(self, text: str) -> str:
        words = text.strip().split()
        result = []
        for w in words:
            if len(w) == 1 and w.isalpha():
                result.append(w.lower())
            elif w.lower() == "space":
                result.append(" ")
            elif w.lower() == "dot":
                result.append(".")
            elif w.lower() == "dash":
                result.append("-")
            elif w.lower() == "underscore":
                result.append("_")
            elif w.lower() == "at":
                result.append("@")
            else:
                result.append(w)
        return "".join(result)

    def _format_number(self, text: str) -> str:
        try:
            from jarvis.tools.productivity.dictation import words_to_number
            return words_to_number(text)
        except ImportError:
            return text

    def _handle_mode_change(self, command: str) -> None:
        if "code" in command and "stop" not in command:
            self._target.mode = DictationMode.CODE
            self._set_state(DictationState.CODE_MODE, "code mode activated")
        elif "spelling" in command and "stop" not in command:
            self._target.mode = DictationMode.SPELLING
        elif "number" in command and "stop" not in command:
            self._target.mode = DictationMode.NUMBER
        else:
            self._target.mode = DictationMode.NORMAL
            if self._state == DictationState.CODE_MODE:
                self._set_state(DictationState.DICTATING, "normal mode restored")

    def _handle_focus_lost(self, snapshot) -> None:
        if self._state in (DictationState.DICTATING, DictationState.CODE_MODE, DictationState.EDITING):
            self.pause("focus lost")
            if self._event_bus:
                try:
                    self._event_bus.emit("dictation.focus_lost", {
                        "target": self._target.app_name,
                        "current_foreground": snapshot.process_name,
                        "action": "PAUSE",
                    })
                except Exception:
                    pass

    def _handle_focus_restored(self, snapshot) -> None:
        if self._state == DictationState.PAUSED:
            self.resume()
            if self._event_bus:
                try:
                    self._event_bus.emit("dictation.focus_restored", {
                        "target": self._target.app_name,
                    })
                except Exception:
                    pass

    def get_diagnostics(self) -> Dict[str, Any]:
        return {
            "state": self._state.value,
            "target": {
                "app_name": self._target.app_name,
                "window_title": self._target.window_title,
                "mode": self._target.mode.value,
                "total_committed": self._target.total_committed,
            },
            "buffer": {
                "committed_length": len(self._buffer.committed_text),
                "spans_count": len(self._buffer.recent_committed_spans),
                "undo_depth": len(self._buffer.undo_stack),
            },
            "session": {
                "commits": self._diagnostics.commits,
                "total_characters": self._diagnostics.total_characters,
                "focus_checks": self._diagnostics.focus_checks,
                "focus_failures": self._diagnostics.focus_failures,
                "commands_classified": self._diagnostics.commands_classified,
                "texts_classified": self._diagnostics.texts_classified,
                "duration_s": (self._diagnostics.ended_at or time.time()) - self._diagnostics.started_at if self._diagnostics.started_at else 0,
            },
            "focus_guard": self._focus_guard.diagnostics(),
        }


# =====================================================================
# Canonical Singleton Access
# =====================================================================

_GLOBAL_DICTATION_CONTROLLER: Optional[DictationController] = None


def get_dictation_controller() -> DictationController:
    """Returns the singleton DictationController instance."""
    global _GLOBAL_DICTATION_CONTROLLER
    if _GLOBAL_DICTATION_CONTROLLER is None:
        _GLOBAL_DICTATION_CONTROLLER = DictationController()
    return _GLOBAL_DICTATION_CONTROLLER