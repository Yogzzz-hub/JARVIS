"""Permission gates must hold even when the optional SDK is absent."""
import pytest

from jarvis.core.brain import claude_code as brain


@pytest.mark.parametrize("name", ["Bash", "Write", "Agent", "Task", "ToolSearch",
    "mcp__android__list_devices", "mcp__exa__search", "mcp__openrouter__send-message"])
def test_environment_cannot_authorize_foreign_tools(name, monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOW_WRITES", "1")
    assert not brain.decide_tool(name, allow_writes=True)


def test_local_default_and_external_mcp_disabled(monkeypatch):
    monkeypatch.delenv("JARVIS_BRAIN", raising=False)
    monkeypatch.delenv("JARVIS_CLAUDE_MCP", raising=False)
    assert brain.brain_mode() == "ollama"
    assert brain.configured_mcp_servers() == {}
