"""Test-wide defaults. Tests never reach a live cloud model: the Claude Code brain is off unless a test turns it on
(the brain's own tests drive a scripted fake of the SDK)."""
import os

os.environ.setdefault("JARVIS_BRAIN", "ollama")
os.environ.setdefault("JARVIS_TTS_ENGINE", "")
