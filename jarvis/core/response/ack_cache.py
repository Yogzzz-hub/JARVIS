"""Pre-generated Acknowledgement Cache for JARVIS EDGE Phase 7.

Zero-LLM, sub-millisecond audio lookup for instant conversational feedback.
Stores pre-generated audio files on disk and caches them in RAM for hot path retrieval.
"""
from __future__ import annotations

import collections
import logging
import os
import random
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.response.ack_cache")

ACK_PHRASES_MAP = {
    "Understood.": "understood.wav",
    "Got it.": "got_it.wav",
    "I'm on it.": "on_it.wav",
    "Okay.": "okay.wav",
    "Starting now.": "starting.wav",
    "I'll handle that.": "handle_that.wav",
    "Please confirm.": "please_confirm.wav",
    "Cancelled.": "cancelled.wav",
    "Stopped.": "stopped.wav",
    "I didn't catch that.": "didnt_catch_that.wav",
}

DEFAULT_GENERAL_ACKS = [
    "Understood.",
    "Got it.",
    "I'm on it.",
    "Okay.",
    "Starting now.",
    "I'll handle that.",
]


class AckCache:
    """RAM-cached pre-generated acknowledgements with rotation and zero-LLM selection."""

    def __init__(self, asset_dir: Optional[str | Path] = None) -> None:
        self.asset_dir = Path(asset_dir or "assets/audio/acks")
        self._ram_cache: Dict[str, bytes] = {}
        self._durations: Dict[str, float] = {}
        self._recent_history: collections.deque = collections.deque(maxlen=2)
        self.sample_rate = 22050
        self.sample_width = 2
        self.channels = 1

    def load_cache(self) -> int:
        """Load all pre-generated ACK audio files from disk into RAM."""
        if not self.asset_dir.exists():
            self.asset_dir.mkdir(parents=True, exist_ok=True)

        loaded_count = 0
        for phrase, fname in ACK_PHRASES_MAP.items():
            fpath = self.asset_dir / fname
            if fpath.exists():
                try:
                    with wave.open(str(fpath), "rb") as wf:
                        self.channels = wf.getnchannels()
                        self.sample_width = wf.getsampwidth()
                        self.sample_rate = wf.getframerate()
                        frames = wf.readframes(wf.getnframes())
                        duration_ms = (len(frames) / (self.channels * self.sample_width * self.sample_rate)) * 1000.0
                        self._ram_cache[phrase] = frames
                        self._durations[phrase] = duration_ms
                        loaded_count += 1
                except Exception as exc:
                    logger.warning("Failed loading ACK audio for %s (%s): %s", phrase, fpath, exc)

        logger.info("Loaded %d ACK clips into RAM cache from %s", loaded_count, self.asset_dir)
        return loaded_count

    def get_ack(self, candidate_phrases: Optional[List[str]] = None) -> Tuple[str, bytes, float]:
        """Select an ACK phrase avoiding the last 2 used phrases.

        Returns (phrase, pcm_bytes, duration_ms).
        """
        candidates = candidate_phrases or DEFAULT_GENERAL_ACKS

        # Filter out recent to avoid immediate repetition
        available = [p for p in candidates if p not in self._recent_history]
        if not available:
            available = candidates

        chosen = random.choice(available)
        self.record_played(chosen)

        pcm = self._ram_cache.get(chosen, b"")
        duration = self._durations.get(chosen, 350.0)
        return chosen, pcm, duration

    def get_phrase_bytes(self, phrase: str) -> Optional[Tuple[bytes, float]]:
        """O(1) direct lookup for a specific phrase (e.g. 'Please confirm.', 'Cancelled.')."""
        if phrase in self._ram_cache:
            return self._ram_cache[phrase], self._durations.get(phrase, 350.0)
        return None

    def record_played(self, phrase: str) -> None:
        """Record phrase in recent history deque."""
        self._recent_history.append(phrase)

    def is_cached(self, phrase: str) -> bool:
        """Check if phrase is cached in RAM."""
        return phrase in self._ram_cache

    @property
    def cached_count(self) -> int:
        return len(self._ram_cache)

    def generate_all_assets(self, piper_model_path: str | Path) -> None:
        """Pre-generate all ACK clips using Piper and write to assets/audio/acks/."""
        from piper import PiperVoice

        self.asset_dir.mkdir(parents=True, exist_ok=True)
        voice = PiperVoice.load(str(piper_model_path))

        for phrase, fname in ACK_PHRASES_MAP.items():
            fpath = self.asset_dir / fname
            if not fpath.exists() or fpath.stat().st_size == 0:
                logger.info("Pre-generating ACK clip: %s -> %s", phrase, fpath)
                with wave.open(str(fpath), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(22050)
                    for chunk in voice.synthesize(phrase):
                        wf.writeframes(chunk.audio_int16_bytes)

        # Reload into RAM
        self.load_cache()
