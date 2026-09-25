"""Typed event definitions and redaction utilities for the JARVIS desktop UI."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AssistantState(StrEnum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    ROUTING = "ROUTING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    SPEAKING = "SPEAKING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"


class ConnectionState(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    RECONNECTING = "RECONNECTING"


class UIEventType(StrEnum):
    JARVIS_READY = "JARVIS_READY"
    JARVIS_OFFLINE = "JARVIS_OFFLINE"
    LISTENING_STARTED = "LISTENING_STARTED"
    LISTENING_STOPPED = "LISTENING_STOPPED"
    AUDIO_LEVEL = "AUDIO_LEVEL"
    TRANSCRIPT_PARTIAL = "TRANSCRIPT_PARTIAL"
    TRANSCRIPT_FINAL = "TRANSCRIPT_FINAL"
    ROUTE_SELECTED = "ROUTE_SELECTED"
    PLANNING_STARTED = "PLANNING_STARTED"
    TASK_STARTED = "TASK_STARTED"
    TASK_NODE_STARTED = "TASK_NODE_STARTED"
    TASK_NODE_FINISHED = "TASK_NODE_FINISHED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    VERIFYING = "VERIFYING"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_UNCERTAIN = "TASK_UNCERTAIN"
    TTS_STARTED = "TTS_STARTED"
    TTS_STOPPED = "TTS_STOPPED"
    VOICE_ERROR = "VOICE_ERROR"
    VOICE_IDLE = "VOICE_IDLE"
    WAKE_DETECTED = "WAKE_DETECTED"
    SYSTEM_METRICS = "SYSTEM_METRICS"
    MODEL_STATE = "MODEL_STATE"
    DEVICE_STATE = "DEVICE_STATE"
    INTEGRATION_STATE = "INTEGRATION_STATE"
    RESPONSE_PARTIAL = "RESPONSE_PARTIAL"


@dataclass(slots=True)
class UIEvent:
    event_type: UIEventType
    request_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


# Patterns and replacement handlers to redact sensitive information
REDACTION_HANDLERS = [
    (re.compile(r"(?i)(api[-_]?key|secret|token|password|auth|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"), r"\1: [REDACTED]"),
    (re.compile(r"(?i)\b(ghp|gho|pat|xox[baprs]|sk-[a-zA-Z0-9]{20,})\b"), "[REDACTED_KEY]"),
    (re.compile(r"(?<![/\\])\b(?:4[0-9]{3}|5[1-5][0-9]{2}|6011|3[47][0-9]{2})[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b(?!\.[a-zA-Z0-9]+)"), "[Card Hidden]"),
    (re.compile(r"(?i)\b(otp|code)\s*[:=]\s*\d{4,8}\b"), r"\1: [REDACTED]"),
]


def redact_sensitive_text(text: str) -> str:
    """Redact sensitive information like tokens, passwords, and credentials."""
    if not text:
        return text
    clean = text
    for pattern, repl in REDACTION_HANDLERS:
        clean = pattern.sub(repl, clean)
    return clean
