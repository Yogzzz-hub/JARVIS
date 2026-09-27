"""Answer "who did you send that to?", "what did you just do?", "did it work?" from what JARVIS really did."""
from __future__ import annotations

from typing import Any

from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition


class RecentActionsInput(Contract):
    question: str = Field(default="what did you just do", max_length=300, description="The follow-up question")


class RecentActionsOutput(Contract):
    status: str
    message: str


class RecentActionsTool(Tool):
    definition = ToolDefinition(
        name="recent_actions",
        description="Answers follow-up questions about what JARVIS just did (who a message went to, what it said, "
                    "whether it worked) from JARVIS's own action record - never guessed.",
        input_model=RecentActionsInput, output_model=RecentActionsOutput, read_only=True, risk=RiskLevel.READ_ONLY,
        timeout_s=2.0, tags=("memory", "history", "follow-up"), execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = RecentActionsInput(**arguments)
        from jarvis.core.action_log import answer_followup
        return {"status": "SUCCESS", "message": answer_followup(arguments.question)}


def create_action_recall_tools() -> list[Tool]:
    return [RecentActionsTool()]
