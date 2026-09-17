from __future__ import annotations

import time
import uuid
from typing import Any
from pathlib import Path

from jarvis.security.confirmation.models import (
    ConfirmationTicket,
    TicketStatus,
    compute_action_fingerprint,
)
from jarvis.tools.base import RiskLevel

def generate_human_summary(tool_name: str, args: dict[str, Any], risk: RiskLevel) -> str:
    """Generates a clear, deterministic human-readable summary of an action.
    Never relies on LLM prose or exposes raw JSON syntax.
    """
    tn = tool_name.lower()
    if tn in ("move_file", "move"):
        src = Path(args.get("source", args.get("path", ""))).name or args.get("source", "")
        dst = Path(args.get("destination", args.get("dest", ""))).name or args.get("destination", "")
        return f"Move '{src}' to '{dst}'"

    if tn in ("copy_file", "copy"):
        src = Path(args.get("source", args.get("path", ""))).name or args.get("source", "")
        dst = Path(args.get("destination", args.get("dest", ""))).name or args.get("destination", "")
        return f"Copy '{src}' to '{dst}'"

    if tn in ("delete_file", "delete", "remove_file", "remove"):
        target = args.get("path", args.get("target", ""))
        # Multi-item deletion preview
        items = args.get("items", [])
        if isinstance(items, list) and len(items) > 1:
            previews = [Path(p).name for p in items[:3]]
            remaining = len(items) - len(previews)
            items_str = ", ".join(previews)
            if remaining > 0:
                items_str += f", and {remaining} more"
            return f"Delete {len(items)} files: {items_str}"
        name = Path(target).name or str(target)
        return f"Permanently delete '{name}'"

    if tn in ("create_folder", "mkdir"):
        name = Path(args.get("path", "")).name or args.get("path", "")
        return f"Create folder '{name}'"

    if tn in ("send_email", "email"):
        to = args.get("to", "recipient")
        subj = args.get("subject", "")
        return f"Send email to '{to}' with subject '{subj}'"

    if tn in ("send_message", "message"):
        recipient = args.get("recipient", args.get("to", "contact"))
        return f"Send message to '{recipient}'"

    # Default structured fallback
    target_info = args.get("path") or args.get("target") or args.get("name") or ""
    if target_info:
        return f"Execute '{tool_name}' on '{target_info}'"
    return f"Execute {risk.name.lower()} action '{tool_name}'"

def generate_graph_summary(actions: list[tuple[str, dict[str, Any], RiskLevel]]) -> str:
    """Generates a cohesive, single human summary for a multi-step task graph.
    Filters to only consequential (non-read-only) actions.
    """
    consequential = [
        generate_human_summary(tool, args, risk)
        for tool, args, risk in actions
        if risk != RiskLevel.READ_ONLY
    ]
    if not consequential:
        return "Execute planned workflow"
    if len(consequential) == 1:
        return f"Jarvis wants to {consequential[0][0].lower() + consequential[0][1:]}. Do you want to continue?"
    
    joined = "; then ".join(consequential)
    return f"Jarvis wants to {joined[0].lower() + joined[1:]}. Do you want to continue?"

class ConfirmationManager:
    """Manages issuance, cryptographic binding, expiration, and consumption
    of ConfirmationTickets.
    """

    def __init__(self, default_timeout_s: float = 30.0) -> None:
        self.default_timeout_s = default_timeout_s
        self._tickets: dict[str, ConfirmationTicket] = {}

    def issue_ticket(
        self,
        request_id: str,
        graph_id: str,
        node_id: str,
        tool_name: str,
        args: dict[str, Any],
        risk: RiskLevel,
        timeout_s: float | None = None,
    ) -> ConfirmationTicket:
        now = time.time()
        expiry = now + (timeout_s if timeout_s is not None else self.default_timeout_s)
        fp = compute_action_fingerprint(tool_name, args, graph_id=graph_id, node_id=node_id)
        summary = generate_human_summary(tool_name, args, risk)
        ticket_id = f"tkt_{uuid.uuid4().hex[:12]}"

        ticket = ConfirmationTicket(
            ticket_id=ticket_id,
            request_id=request_id,
            graph_id=graph_id,
            action_fingerprint=fp,
            scope=f"node:{node_id}" if node_id else f"graph:{graph_id}",
            risk=risk,
            human_summary=summary,
            issued_at=now,
            expires_at=expiry,
            status=TicketStatus.PENDING,
        )
        self._tickets[ticket_id] = ticket
        return ticket

    def approve_ticket(self, ticket_id: str) -> bool:
        ticket = self._tickets.get(ticket_id)
        if not ticket or ticket.status != TicketStatus.PENDING:
            return False
        if time.time() > ticket.expires_at:
            ticket.status = TicketStatus.EXPIRED
            return False
        ticket.status = TicketStatus.APPROVED
        return True

    def deny_ticket(self, ticket_id: str) -> bool:
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return False
        ticket.status = TicketStatus.DENIED
        return True

    def consume_ticket(self, ticket_id: str, current_fingerprint: str) -> tuple[bool, str]:
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return False, f"Ticket '{ticket_id}' not found"

        valid, reason = ticket.is_valid_for(current_fingerprint)
        if not valid:
            return False, reason

        ticket.status = TicketStatus.CONSUMED
        return True, "Ticket consumed successfully"

    def get_ticket(self, ticket_id: str) -> ConfirmationTicket | None:
        return self._tickets.get(ticket_id)
