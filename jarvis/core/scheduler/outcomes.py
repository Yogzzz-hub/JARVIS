"""Structured ActionOutcome, CommandOutcome, and ResultAggregator for JARVIS EDGE."""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ActionStatus(StrEnum):
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    UNCERTAIN = "UNCERTAIN"


class ActionOutcome(BaseModel):
    model_config = ConfigDict(extra="ignore")
    step_id: str
    capability: str
    status: ActionStatus
    dependency: list[str] = Field(default_factory=list)
    reason: Optional[str] = None
    verified_result: Optional[dict[str, Any]] = None


class CommandStatus(StrEnum):
    COMPLETED = "COMPLETED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    CONFIRMATION = "CONFIRMATION"
    UNCERTAIN = "UNCERTAIN"
    CANCELLED = "CANCELLED"


class CommandOutcome(BaseModel):
    model_config = ConfigDict(extra="ignore")
    command_id: str
    status: CommandStatus
    message: str
    action_outcomes: list[ActionOutcome] = Field(default_factory=list)
    successful_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    uncertain_count: int = 0
    total: int = 0
    outcome_version: int = 1
    finalized: bool = True
    verified: bool = False
    metrics: dict[str, Any] = Field(default_factory=dict)


class ResultAggregator:
    """Aggregates real ActionOutcome records into a unified CommandOutcome with truthful reporting."""

    @classmethod
    def aggregate(
        cls,
        action_outcomes: list[ActionOutcome],
        command_id: str = "",
        waiting_confirmation: bool = False,
        is_voice: bool = False,
    ) -> CommandOutcome:
        total = len(action_outcomes)
        successful_count = sum(1 for a in action_outcomes if a.status == ActionStatus.VERIFIED_SUCCESS)
        failed_count = sum(1 for a in action_outcomes if a.status == ActionStatus.FAILED)
        skipped_count = sum(1 for a in action_outcomes if a.status in (ActionStatus.SKIPPED, ActionStatus.BLOCKED))
        uncertain_count = sum(1 for a in action_outcomes if a.status == ActionStatus.UNCERTAIN)

        if waiting_confirmation:
            status = CommandStatus.CONFIRMATION
            verified = False
        elif uncertain_count > 0 and successful_count == 0 and failed_count == 0:
            status = CommandStatus.UNCERTAIN
            verified = False
        elif total > 0 and successful_count == total:
            status = CommandStatus.COMPLETED
            verified = True
        elif successful_count > 0 and (failed_count > 0 or skipped_count > 0 or uncertain_count > 0):
            status = CommandStatus.PARTIAL_SUCCESS
            verified = True
        elif successful_count == 0 and total > 0:
            status = CommandStatus.FAILED
            verified = False
        else:
            status = CommandStatus.UNCERTAIN
            verified = False

        message = cls.compose_message(action_outcomes, status)

        return CommandOutcome(
            command_id=command_id,
            status=status,
            message=message,
            action_outcomes=action_outcomes,
            successful_count=successful_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            uncertain_count=uncertain_count,
            total=total,
            outcome_version=1,
            finalized=True,
            verified=verified,
        )

    @classmethod
    def _friendly_cap_name(cls, act: ActionOutcome) -> str:
        cap = act.capability.strip()
        # Clean up tool names
        lower = cap.lower()
        if lower.startswith("open_app"):
            return "Application"
        if lower.startswith("find_file"):
            return "File search"
        if lower.startswith("open_file"):
            return "Document"
        if "_" in cap:
            parts = [w.capitalize() for w in cap.split("_")]
            return " ".join(parts)
        return cap.title()

    @classmethod
    def compose_message(cls, action_outcomes: list[ActionOutcome], status: CommandStatus) -> str:
        """Compose clear, factual, and concise outcome text from individual action outcomes."""
        if not action_outcomes:
            if status == CommandStatus.COMPLETED:
                return "Task completed successfully."
            if status == CommandStatus.UNCERTAIN:
                return "I performed the action, but I couldn't verify whether it completed."
            return "Task could not be completed."

        failed_nodes = {a.step_id: a for a in action_outcomes if a.status == ActionStatus.FAILED}
        success_nodes = [a for a in action_outcomes if a.status == ActionStatus.VERIFIED_SUCCESS]
        skipped_nodes = [a for a in action_outcomes if a.status in (ActionStatus.SKIPPED, ActionStatus.BLOCKED)]

        # 1. Total Success / Completed
        if status == CommandStatus.COMPLETED:
            if len(action_outcomes) == 1:
                act = action_outcomes[0]
                name = cls._friendly_cap_name(act)
                if act.verified_result and isinstance(act.verified_result, dict):
                    msg = act.verified_result.get("spoken_summary") or act.verified_result.get("summary") or act.verified_result.get("message")
                    if msg:
                        return str(msg)
                return f"{name} completed successfully."
            names = [cls._friendly_cap_name(a) for a in success_nodes]
            if len(names) == 2:
                joined = f"{names[0]} and {names[1]}"
            else:
                joined = ", ".join(names[:-1]) + f", and {names[-1]}"
            return f"Completed all {len(action_outcomes)} steps successfully ({joined})."

        # 2. Partial Success
        if status == CommandStatus.PARTIAL_SUCCESS:
            sentences = [f"Completed {len(success_nodes)} of {len(action_outcomes)} steps."]
            # Success descriptions
            s_names = [cls._friendly_cap_name(a) for a in success_nodes]
            if s_names:
                if len(s_names) == 1:
                    sentences.append(f"{s_names[0]} opened successfully." if "open" in success_nodes[0].capability.lower() or s_names[0] in ("Notepad", "Calculator", "Chrome") else f"{s_names[0]} succeeded.")
                else:
                    sentences.append(f"{' and '.join(s_names)} completed successfully.")

            # Failed descriptions
            f_names = [cls._friendly_cap_name(a) for a in failed_nodes.values()]
            if f_names:
                f_desc = f"{' and '.join(f_names)} failed"
                # Check if any skipped nodes were dependent on these failed nodes
                dep_skips = []
                for s in skipped_nodes:
                    if any(dep in failed_nodes for dep in s.dependency):
                        dep_skips.append(cls._friendly_cap_name(s))

                if dep_skips:
                    dep_str = " and ".join(dep_skips)
                    sentences.append(f"{f_desc}, so the dependent {dep_str} step was skipped.")
                else:
                    sentences.append(f"{f_desc}.")

            # Other non-dependent skipped nodes
            indep_skips = [cls._friendly_cap_name(s) for s in skipped_nodes if not any(dep in failed_nodes for dep in s.dependency)]
            if indep_skips:
                sentences.append(f"{' and '.join(indep_skips)} was skipped.")

            return " ".join(sentences)

        # 3. Failed
        if status == CommandStatus.FAILED:
            from jarvis.core.response.formatter import ResponseFormatter
            if failed_nodes:
                first_fail = next(iter(failed_nodes.values()))
                reason = first_fail.reason or "unknown failure"
                clean_err = ResponseFormatter.sanitize_error(reason, tool_name=first_fail.capability)
                cap = cls._friendly_cap_name(first_fail)
                if clean_err.startswith("I couldn't") or clean_err.startswith("Could not") or clean_err.startswith("The requested"):
                    return clean_err
                return f"{cap} failed: {clean_err}"
            return "I couldn't complete the task."

        # 4. Uncertain
        if status == CommandStatus.UNCERTAIN:
            return "I performed the action, but I couldn't verify whether it completed."

        return "Task finished."
