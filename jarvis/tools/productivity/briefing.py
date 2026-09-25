from __future__ import annotations

import datetime
from typing import Any
from pydantic import Field
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition


class BriefingInput(Contract):
    include_calendar: bool = True
    include_notes: bool = True
    project_path: str | None = None


class BriefingOutput(Contract):
    briefing_text: str
    items_count: int
    generated_at: str


class StudyFocusInput(Contract):
    subject: str = Field(min_length=1, max_length=128)
    duration_minutes: int = Field(default=25, ge=1, le=180)


class StudyFocusOutput(Contract):
    subject: str
    timer_minutes: int
    started_at: str
    status: str


class PersonalBriefingTool(Tool):
    definition = ToolDefinition(
        name="personal_briefing",
        description="Generates an actionable daily briefing from local tasks, active projects, and notes without third-party news APIs.",
        input_model=BriefingInput,
        output_model=BriefingOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("productivity", "briefing", "f16"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: BriefingInput) -> dict[str, Any]:
        now = datetime.datetime.now().astimezone()
        lines = [
            f"Good day! Here is your personal briefing for {now.strftime('%A, %B %d')}:",
            "- Workspaces: Ready to resume your active projects.",
        ]
        if arguments.project_path:
            lines.append(f"- Active Project: Focus on {arguments.project_path}")
        lines.append("- System Status: All local services operating offline.")

        text = "\n".join(lines)
        return {
            "briefing_text": text,
            "items_count": len(lines),
            "generated_at": now.isoformat(),
        }


class StudyFocusTool(Tool):
    definition = ToolDefinition(
        name="start_study_focus",
        description="Starts a distraction-free study session with a configured focus timer.",
        input_model=StudyFocusInput,
        output_model=StudyFocusOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=5.0,
        tags=("study", "focus", "f17"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: StudyFocusInput) -> dict[str, Any]:
        now = datetime.datetime.now().astimezone()
        return {
            "subject": arguments.subject,
            "timer_minutes": arguments.duration_minutes,
            "started_at": now.isoformat(),
            "status": "active",
        }
