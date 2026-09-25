from typing import Literal
from uuid import uuid4
from pydantic import Field
from jarvis.tools.base import Contract, ToolResult, VerificationResult

class CommandRequest(Contract):
    text: str = Field(min_length=1, max_length=4096)
    request_id: str = Field(default_factory=lambda: uuid4().hex, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    source: Literal["http", "cli", "websocket", "benchmark", "test", "voice", "whatsapp"] = "http"
    is_owner: bool = True
    chat_id: str | None = None
    sender_id: str | None = None
    trust_level: str = "TRUSTED_LOCAL"
    metadata: dict = Field(default_factory=dict)

class CommandResult(Contract):
    request_id: str
    state: Literal["SUCCESS", "FAILED", "CANCELLED", "WAITING_CONFIRMATION"]
    message: str
    tool_result: ToolResult | None = None
    verification: VerificationResult | None = None
    metrics: dict[str, float | None]

class WSInput(Contract):
    version: Literal[1]
    type: Literal["command", "ping", "ptt_start", "ptt_stop", "stop_speaking", "confirm", "reject", "approve", "deny"]
    request_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    text: str | None = Field(default=None, min_length=1, max_length=4096)
    source: str | None = None
