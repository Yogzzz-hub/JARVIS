from __future__ import annotations

import hashlib
import json
import time
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from jarvis.security.paths import canonicalize_path
from jarvis.tools.base import RiskLevel

class TicketStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"

def compute_action_fingerprint(
    tool_name: str,
    args: dict[str, Any],
    graph_id: str = "",
    node_id: str = "",
) -> str:
    """Computes a canonical SHA-256 fingerprint for an intended action.
    Security-critical path arguments are canonicalized so equivalent paths
    produce identical fingerprints, and altered paths produce distinct fingerprints.
    """
    canonical_args: dict[str, Any] = {}
    path_keys = {"path", "source", "destination", "dest", "target", "file_path", "folder_path", "old_path", "new_path"}

    for k, v in sorted(args.items()):
        if k.lower() in ("confirmation_ticket", "ticket_id"):
            continue
        if k.lower() in path_keys and isinstance(v, str):
            canonical_args[k] = str(canonicalize_path(v)).lower()
        else:
            canonical_args[k] = v

    payload = {
        "tool": tool_name.strip().lower(),
        "args": canonical_args,
        "graph_id": graph_id,
        "node_id": node_id,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

class ConfirmationTicket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    request_id: str
    graph_id: str
    action_fingerprint: str
    scope: str
    risk: RiskLevel
    human_summary: str
    issued_at: float
    expires_at: float
    status: TicketStatus = TicketStatus.PENDING

    def is_valid_for(self, action_fingerprint: str, current_time: float | None = None) -> tuple[bool, str]:
        now = current_time if current_time is not None else time.time()
        if self.status == TicketStatus.CONSUMED:
            return False, "Confirmation ticket has already been consumed"
        if self.status == TicketStatus.DENIED:
            return False, "Action confirmation was explicitly denied by user"
        if self.status != TicketStatus.APPROVED:
            return False, f"Ticket is not approved (status: {self.status})"
        if now > self.expires_at:
            return False, f"Confirmation ticket expired ({now - self.expires_at:.1f}s ago)"
        if self.action_fingerprint != action_fingerprint:
            return False, "Action arguments or target materially changed after confirmation"
        return True, ""
