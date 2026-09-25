"""DictationController — Voice-driven dictation state machine for JARVIS EDGE.

Manages the full dictation lifecycle:
  IDLE → ARMED → DICTATING → EDITING / PAUSED / CODE_MODE → STOPPING → IDLE

Safety invariants:
- Never types into unknown or unfocused window (FocusGuard)
- Never executes dictation text as commands
- Wake word always exits dictation immediately
- Focus loss → immediate pause

Data flow during DICTATING:
  AudioHub → VAD → STT → Stabilizer → DictationController
  → Classifier (COMMAND | TEXT)
  → TEXT path: FocusGuard.check() → format → input_layer.type_text()
  → COMMAND path: Router (normal processing)
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
# Command vs Dictation Classifier
# =====================================================================

# Voice edit commands recognized during dictation
VOICE_EDIT_PATTERNS = {
    "backspace", "delete", "undo", "redo",
    "delete word", "delete last word", "delete sentence", "delete last sentence",
    "select last sentence", "select all",
    "copy that", "cut that", "paste",
}

# Mode change commands
MODE_CHANGE_PATTERNS = {
    "code mode", "coding mode", "start code mode",
    "normal mode", "stop code mode",
    "spelling mode", "start spelling mode", "stop spelling mode",
    "number mode", "start number mode", "stop number mode",
}

# Stop/pause commands
STOP_PATTERNS = {
    "stop typing", "stop dictation", "done typing", "done dictating",
    "finish typing", "end typing", "end dictation",
    "pause typing", "pause dictation",
}

# Punctuation commands (these are TEXT, transformed inline)
PUNCTUATION_COMMANDS = {
    "period", "full stop", "comma", "question mark", "exclamation mark",
    "exclamation point", "colon", "semicolon", "open quote", "close quote",
    "open parenthesis", "close parenthesis", "open bracket", "close bracket",
    "dash", "hyphen", "ellipsis", "ampersand", "at sign", "hashtag",
    "dollar sign", "percent sign", "asterisk", "slash", "backslash",
}

# Structural commands (TEXT, transformed inline)
STRUCTURAL_COMMANDS = {
    "new line", "newline", "new paragraph",
    "tab", "space",
}


def classify_dictation_input(text: str) -> Tuple[ClassificationResult, str]:
    """Classify text during active dictation as TEXT, COMMAND, VOICE_EDIT, etc.

    Args:
        text: The stable prefix or final transcript from STT.

    Returns:
        Tuple of (classification, normalized_text).
    """
    normalized = text.strip().lower()

    # 1. Wake word → always COMMAND (exits dictation)
    if normalized.startswith(("hey jarvis", "jarvis", "ok jarvis")):
        return ClassificationResult.COMMAND, normalized

    # 2. Stop/pause commands
    if normalized in STOP_PATTERNS:
        return ClassificationResult.STOP, normalized

    # 3. Voice edit commands
    # Handle "replace X with Y" pattern
    if normalized.startswith("replace ") and " with " in normalized:
        return ClassificationResult.VOICE_EDIT, normalized
    if normalized.startswith("capitalize ") or normalized.startswith("make ") and "lowercase" in normalized:
        return ClassificationResult.VOICE_EDIT, normalized
    if normalized in VOICE_EDIT_PATTERNS:
        return ClassificationResult.VOICE_EDIT, normalized

    # 4. Mode change commands
    if normalized in MODE_CHANGE_PATTERNS:
        return ClassificationResult.MODE_CHANGE, normalized

    # 5. Everything else is TEXT (including punctuation/structural, handled by formatter)
    return ClassificationResult.TEXT, text


# =====================================================================
# DictationController
# =====================================================================

class DictationController:
    """State machine for voice-driven dictation.

    Manages the full lifecycle from IDLE through DICTATING to cleanup.
    Integrates FocusGuard for safe input delivery.

    Usage:
        controller = DictationController(event_bus=bus)
        controller.start(app_name="Notepad")  # IDLE → ARMED → DICTATING
        controller.on_stable_text("hello world")  # Types into target
        controller.stop()  # DICTATING → STOPPING → IDLE
    """

    def __init__(
        self,
        event_bus: Optional[Any] = None,
        on_state_change: Optional[Callable[[DictationState, DictationState], None]] = None,
    ) -> None:
        self._state = DictationState.IDLE
        self._target = DictationTarget()
        self._focus_guard = FocusGuard(
            on_focus_lost=self._handle_focus_lost,
            on_focus_restored=self._handle_focus_restored,
        )
        self._event_bus = event_bus
        self._on_state_change = on_state_change
        self._diagnostics = DictationDiagnostics()
        self._committed_text = ""  # All text committed in this session
        self._pending_buffer = ""  # Text waiting to be committed (during pause)

    # -----------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------

    @property
    def state(self) -> DictationState:
        return self._state

    @property
    def target(self) -> DictationTarget:
        return self._target

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
    # Lifecycle: Start / Stop / Pause / Resume
    # -----------------------------------------------------------------

    def start(
        self,
        app_name: str = "",
        window_title: str = "",
        mode: str = "normal",
    ) -> Tuple[bool, str]:
        """Start dictation, targeting the specified or current window.

        Args:
            app_name: Target application name (optional).
            window_title: Target window title (optional).
            mode: Dictation mode ('normal', 'code', 'spelling', 'number').

        Returns:
            Tuple of (success, message).
        """
        if self._state != DictationState.IDLE:
            return False, f"Cannot start: already in {self._state.value} state"

        self._set_state(DictationState.ARMED, "start requested")
        self._diagnostics = DictationDiagnostics(started_at=time.time())
        self._committed_text = ""
        self._pending_buffer = ""

        # Resolve target
        try:
            dictation_mode = DictationMode(mode.lower()) if mode else DictationMode.NORMAL
        except ValueError:
            dictation_mode = DictationMode.NORMAL

        # Get current foreground window as target
        hwnd = get_foreground_hwnd()
        if not hwnd:
            self._set_state(DictationState.IDLE, "no foreground window")
            return False, "No foreground window found"

        proc = get_foreground_process_name()
        title = get_window_title(hwnd)

        self._target = DictationTarget(
            app_name=app_name or proc or "Unknown",
            window_title=window_title or title,
            window_hwnd=hwnd,
            focus_verified=True,
            started_at=time.time(),
            mode=dictation_mode,
        )

        # Set focus guard target
        self._focus_guard.set_target(hwnd, proc, title)

        # Verify focus
        if not self._focus_guard.check():
            self._set_state(DictationState.IDLE, "focus verification failed")
            self._focus_guard.clear()
            return False, f"Could not verify focus on {self._target.app_name}"

        self._set_state(DictationState.DICTATING, "focus verified")
        logger.info(
            "Dictation started: app=%s window='%s' mode=%s",
            self._target.app_name, self._target.window_title, dictation_mode.value,
        )
        return True, f"Typing mode active in {self._target.app_name}"

    def stop(self) -> Tuple[bool, str]:
        """Stop dictation and flush any pending buffer.

        Returns:
            Tuple of (success, message).
        """
        if self._state == DictationState.IDLE:
            return True, "Already idle"

        self._set_state(DictationState.STOPPING, "stop requested")

        # Flush pending buffer if focus is still good
        if self._pending_buffer and self._focus_guard.check():
            typed, _ = type_text(self._pending_buffer)
            self._target.total_committed += typed
            self._diagnostics.total_characters += typed
            self._pending_buffer = ""

        total = self._target.total_committed
        app = self._target.app_name
        self._diagnostics.ended_at = time.time()

        # Cleanup
        self._focus_guard.clear()
        self._target = DictationTarget()
        self._set_state(DictationState.IDLE, "stopped")

        return True, f"Typing done. {total} characters typed in {app}."

    def pause(self, reason: str = "user request") -> None:
        """Pause dictation, preserving buffer."""
        if self._state in (DictationState.DICTATING, DictationState.CODE_MODE, DictationState.EDITING):
            self._set_state(DictationState.PAUSED, reason)

    def resume(self) -> Tuple[bool, str]:
        """Resume paused dictation.

        Returns:
            Tuple of (success, message).
        """
        if self._state != DictationState.PAUSED:
            return False, f"Cannot resume: in {self._state.value} state"

        # Re-verify focus
        if not self._focus_guard.check():
            # Try to refocus
            if not self._focus_guard.attempt_refocus():
                return False, "Cannot resume: target window not focused"

        self._set_state(DictationState.DICTATING, "resumed")

        # Type any pending buffer
        if self._pending_buffer:
            typed, _ = type_text(self._pending_buffer)
            self._target.total_committed += typed
            self._diagnostics.total_characters += typed
            self._pending_buffer = ""

        return True, f"Resumed typing in {self._target.app_name}"

    def cancel(self) -> Tuple[bool, str]:
        """Cancel dictation, discarding any pending buffer."""
        self._pending_buffer = ""
        return self.stop()

    # -----------------------------------------------------------------
    # Text Processing
    # -----------------------------------------------------------------

    def on_stable_text(self, text: str) -> Tuple[ClassificationResult, str]:
        """Process stable text from STT during active dictation.

        This is the main entry point called by the VoicePipeline when
        the DictationController is active.

        Args:
            text: Stable/final text from the STT stabilizer.

        Returns:
            Tuple of (classification, response_message).
        """
        if not self.is_active:
            return ClassificationResult.COMMAND, "Not in dictation mode"

        # Classify the input
        classification, normalized = classify_dictation_input(text)

        if classification == ClassificationResult.STOP:
            self.stop()
            return classification, "Dictation stopped"

        if classification == ClassificationResult.COMMAND:
            # Will be routed to the normal router
            return classification, text

        if classification == ClassificationResult.MODE_CHANGE:
            self._handle_mode_change(normalized)
            return classification, f"Mode changed to {self._target.mode.value}"

        if classification == ClassificationResult.VOICE_EDIT:
            return classification, text

        # TEXT — commit to target
        if self._state == DictationState.PAUSED:
            self._pending_buffer += text
            return classification, "Buffered (paused)"

        # Focus check before commit
        self._diagnostics.focus_checks += 1
        if not self._focus_guard.check():
            self._diagnostics.focus_failures += 1
            self._pending_buffer += text
            self.pause("focus lost during commit")
            return ClassificationResult.TEXT, "Focus lost, paused"

        # Format and type
        formatted = self._format_text(text)
        typed, method = type_text(formatted)
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

        return classification, formatted

    def on_delta_text(self, delta: str) -> bool:
        """Process incremental delta text for live word-by-word typing.

        Called by the STT stabilizer when a new stable word is confirmed.
        This is the low-latency path — no formatting, direct commit.

        Args:
            delta: New stable characters to type (typically a word + space).

        Returns:
            True if the delta was committed, False if paused/blocked.
        """
        if self._state not in (DictationState.DICTATING, DictationState.CODE_MODE):
            if self._state == DictationState.PAUSED:
                self._pending_buffer += delta
            return False

        # Focus check
        if not self._focus_guard.check():
            self._pending_buffer += delta
            self.pause("focus lost during delta commit")
            return False

        # Direct commit — no formatting for deltas (already formatted at source)
        typed = type_unicode(delta)
        self._target.total_committed += typed
        self._target.last_commit_at = time.time()
        self._committed_text += delta
        self._diagnostics.commits += 1
        self._diagnostics.total_characters += typed
        return True

    # -----------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------

    def _format_text(self, text: str) -> str:
        """Apply mode-specific formatting to dictation text.

        Delegates to the appropriate formatter based on current mode.
        """
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
        """Apply natural language formatting (punctuation, capitalization)."""
        # Convert spoken punctuation to characters
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
        """Apply code-specific formatting."""
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
        # Convert "underscore" to "_"
        result = re.sub(r"\bunderscore\b", "_", result, flags=re.IGNORECASE)
        return result

    def _format_spelling(self, text: str) -> str:
        """Convert spelled letters to characters."""
        # "A B C" → "abc"
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
        """Convert spoken number words to digits."""
        # Import the existing words_to_number from dictation.py
        try:
            from jarvis.tools.productivity.dictation import words_to_number
            return words_to_number(text)
        except ImportError:
            return text

    def _handle_mode_change(self, command: str) -> None:
        """Handle mode change commands."""
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
        """Called by FocusGuard when focus is lost."""
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
        """Called by FocusGuard when focus is restored."""
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
        """Return comprehensive diagnostics for the current/last session."""
        return {
            "state": self._state.value,
            "target": {
                "app_name": self._target.app_name,
                "window_title": self._target.window_title,
                "mode": self._target.mode.value,
                "total_committed": self._target.total_committed,
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