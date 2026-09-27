"""Reply language: "reply in thanglish", "english la pesu", "reply in my language" (auto: mirror the owner)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition


class ReplyLanguageInput(Contract):
    mode: Literal["auto", "english", "thanglish"] = Field(
        description="thanglish = always Tamil in English letters, english = always English, auto = reply in the language I use")


class ReplyLanguageOutput(Contract):
    status: str
    mode: str
    message: str


_MESSAGES = {
    "thanglish": "Seri, ippo irundhu Thanglish la pesuren.",
    "english": "Okay, I'll reply in English from now on.",
    "auto": "Okay, I'll reply in the language you use: English or Thanglish.",
}


class SetReplyLanguageTool(Tool):
    definition = ToolDefinition(
        name="set_reply_language",
        description="Sets the language JARVIS replies in: English, Thanglish (Tamil in English letters), or auto "
                    "(the same language the owner speaks).",
        input_model=ReplyLanguageInput,
        output_model=ReplyLanguageOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=2.0,
        tags=("language", "thanglish", "tamil", "english", "settings"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = ReplyLanguageInput(**arguments)
        from jarvis.core.multilingual import set_preference
        mode = set_preference(arguments.mode)
        return {"status": "SUCCESS", "mode": mode, "message": _MESSAGES[mode]}


def create_language_tools() -> list[Tool]:
    return [SetReplyLanguageTool()]
