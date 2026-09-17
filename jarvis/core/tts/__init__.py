"""Local Text-to-Speech (TTS) subsystem for JARVIS EDGE."""
from jarvis.core.tts.base import ResponsePolisher, TTSChunk, TTSEngine
from jarvis.core.tts.manager import TTSManager
from jarvis.core.tts.piper_engine import PiperEngine
from jarvis.core.tts.sapi_engine import SAPIEngine

__all__ = [
    "PiperEngine",
    "ResponsePolisher",
    "SAPIEngine",
    "TTSChunk",
    "TTSEngine",
    "TTSManager",
]
