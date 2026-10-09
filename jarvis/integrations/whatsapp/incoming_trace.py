"""Temporary opt-in metadata-only incoming boundary trace."""
from __future__ import annotations

import json
import os
from contextvars import ContextVar
from datetime import datetime, timezone

trace_generation: ContextVar[str] = ContextVar("whatsapp_trace_generation", default="")
_ALLOWED = frozenset({
    "stage", "event_type", "message_id", "chat_jid", "from_me", "message_type",
    "timestamp", "generation", "normalization_result", "python_receive_result",
    "sqlite_result", "reason",
})


def trace_incoming(**fields: object) -> None:
    path = os.environ.get("JARVIS_WHATSAPP_TRACE_PYTHON")
    if not path:
        return
    record = {"at": datetime.now(timezone.utc).isoformat(), "generation": trace_generation.get()}
    record.update({key: value for key, value in fields.items() if key in _ALLOWED and value is not None})
    try:
        fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            os.write(fd, (json.dumps(record, ensure_ascii=False, default=str) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        pass  # tracing must never block ingestion
