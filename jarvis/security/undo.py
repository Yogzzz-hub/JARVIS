from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from jarvis.security.paths import canonicalize_path

class ActionReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    tool: str
    summary: str
    status: str
    verification: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    undo_available: bool = False
    undo_token: str | None = None

class UndoRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    undo_id: str
    action_id: str
    tool: str
    inverse_tool: str
    inverse_args: dict[str, Any]
    created_at: float = Field(default_factory=time.time)

class UndoManager:
    """Manages verified undo records and issues action receipts.
    Guarantees that rollback is only registered for strictly reversible actions
    with known and validated inverse operations.
    """

    def __init__(self) -> None:
        self._undo_store: dict[str, UndoRecord] = {}

    def compute_inverse(self, tool_name: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
        tn = tool_name.lower()
        if tn in ("move_file", "move"):
            src = args.get("source") or args.get("path")
            dst = args.get("destination") or args.get("dest")
            if src and dst:
                return "move_file", {"source": dst, "destination": src}

        if tn in ("rename_file", "rename"):
            src = args.get("source") or args.get("old_path")
            dst = args.get("destination") or args.get("new_path")
            if src and dst:
                return "rename_file", {"source": dst, "destination": src}

        if tn in ("create_folder", "mkdir"):
            path = args.get("path")
            if path:
                return "delete_folder", {"path": path}

        return None

    def create_receipt(
        self,
        action_id: str,
        tool_name: str,
        args: dict[str, Any],
        summary: str,
        status: str,
        verification: dict[str, Any],
        rollback_supported: bool = False,
    ) -> ActionReceipt:
        undo_available = False
        undo_token = None

        if rollback_supported:
            inv = self.compute_inverse(tool_name, args)
            if inv is not None:
                inv_tool, inv_args = inv
                undo_id = f"undo_{uuid.uuid4().hex[:12]}"
                rec = UndoRecord(
                    undo_id=undo_id,
                    action_id=action_id,
                    tool=tool_name,
                    inverse_tool=inv_tool,
                    inverse_args=inv_args,
                )
                self._undo_store[undo_id] = rec
                undo_available = True
                undo_token = undo_id

        return ActionReceipt(
            action_id=action_id,
            tool=tool_name,
            summary=summary,
            status=status,
            verification=verification,
            undo_available=undo_available,
            undo_token=undo_token,
        )

    def validate_undo(self, undo_token: str) -> tuple[bool, str, UndoRecord | None]:
        rec = self._undo_store.get(undo_token)
        if not rec:
            return False, "Undo token not found or expired", None

        # Check that inverse operation preconditions hold
        inv_tool = rec.inverse_tool
        inv_args = rec.inverse_args

        if inv_tool in ("move_file", "rename_file"):
            src = canonicalize_path(inv_args["source"])
            dst = canonicalize_path(inv_args["destination"])
            if not src.exists():
                return False, f"Cannot undo: file '{src}' no longer exists at moved location", None
            if dst.exists():
                return False, f"Cannot undo: original location '{dst}' is occupied by another file", None

        if inv_tool == "delete_folder":
            folder = canonicalize_path(inv_args["path"])
            if folder.exists():
                # Only safe to delete if folder is empty (prevent deleting user data added subsequently)
                contents = list(folder.iterdir())
                if contents:
                    return False, f"Cannot undo folder creation: folder '{folder}' is not empty", None

        return True, "Safe to undo", rec
