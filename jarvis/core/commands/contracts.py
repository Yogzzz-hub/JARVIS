from typing import Literal
from uuid import uuid4
from pydantic import Field
from jarvis.tools.base import Contract, ToolResult, VerificationResult

class CommandRequest(Contract):
    text: str = Field(min_length=1, max_length=4096)
    request_id: str = Field(default_factory=lambda: uuid4().hex, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    source: Literal["http", "cli", "websocket", "benchmark", "test"] = "http"

class CommandResult(Contract):
    request_id: str
    state: Literal["SUCCESS", "FAILED", "CANCELLED"]
    message: str
    tool_result: ToolResult | None = None
    verification: VerificationResult | None = None
    metrics: dict[str, float | None]

class WSInput(Contract):
    version: Literal[1]
    type: Literal["command", "ping"]
    request_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    text: str | None = Field(default=None, min_length=1, max_length=4096)
