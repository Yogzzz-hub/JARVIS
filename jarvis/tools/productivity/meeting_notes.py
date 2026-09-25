from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any
from pydantic import Field
from jarvis.config import ROOT
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

MEETINGS_DIR = ROOT / "jarvis" / "data" / "meetings"


class MeetingNotesInput(Contract):
    title: str = Field(min_length=1, max_length=256)
    transcript: str = Field(min_length=1, max_length=50000)


class MeetingNotesOutput(Contract):
    title: str
    summary_path: str
    action_items: tuple[str, ...]
    summary_points: tuple[str, ...]
    status: str


class MeetingNotesTool(Tool):
    definition = ToolDefinition(
        name="generate_meeting_notes",
        description="Generates timestamped summary and proposed action items from meeting transcript without inventing speakers.",
        input_model=MeetingNotesInput,
        output_model=MeetingNotesOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=15.0,
        tags=("productivity", "meeting", "f12"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: MeetingNotesInput) -> dict[str, Any]:
        MEETINGS_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.datetime.now().astimezone()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        out_file = MEETINGS_DIR / f"meeting_{timestamp_str}.md"

        # Deterministic extraction of action items (lines with 'todo', 'action', 'will', 'follow up')
        action_items: list[str] = []
        summary_points: list[str] = []

        for line in arguments.transcript.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            lower = line_str.lower()
            if any(k in lower for k in ("todo", "action item", "will", "follow up", "assigned")):
                action_items.append(line_str)
            elif len(line_str) > 30 and len(summary_points) < 5:
                summary_points.append(line_str)

        if not summary_points:
            summary_points.append(arguments.transcript[:200] + ("..." if len(arguments.transcript) > 200 else ""))

        markdown = f"""# Meeting: {arguments.title}
**Date:** {now.strftime("%Y-%m-%d %H:%M:%S")}
*(Note: Speaker identities are not inferred automatically to ensure accuracy)*

## Key Discussion Points
""" + "\n".join(f"- {p}" for p in summary_points) + "\n\n## Proposed Action Items\n" + "\n".join(f"- [ ] {a}" for a in action_items)

        with open(out_file, "w", encoding="utf-8") as f:
            f.write(markdown)

        return {
            "title": arguments.title,
            "summary_path": str(out_file),
            "action_items": tuple(action_items),
            "summary_points": tuple(summary_points),
            "status": "created",
        }
