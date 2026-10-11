"""Alternative reasoning brains for JARVIS (the local Ollama models stay the default)."""
from jarvis.core.brain.claude_code import ClaudeCodeBrain, brain_mode, decide_tool, get_claude_brain

__all__ = ["ClaudeCodeBrain", "brain_mode", "decide_tool", "get_claude_brain"]
