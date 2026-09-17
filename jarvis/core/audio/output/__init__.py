"""Audio Output, Barge-in, and Echo Protection subsystem for JARVIS EDGE."""
from jarvis.core.audio.output.barge_in import BargeInController
from jarvis.core.audio.output.player import AudioOutputManager
from jarvis.core.audio.output.queue import AudioOutputQueue

__all__ = [
    "AudioOutputManager",
    "AudioOutputQueue",
    "BargeInController",
]
