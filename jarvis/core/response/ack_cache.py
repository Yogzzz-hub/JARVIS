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
    "Yes?": "yes.wav",
    "I'm listening.": "listening.wav",
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
    "Done.": "done.wav",
    "Yes, it is completed.": "completed.wav",
    "Opening it.": "opening_it.wav",
    "Opening Chrome.": "opening_chrome.wav",
    "Opening Notepad.": "opening_notepad.wav",
    "Checking your WhatsApp messages.": "checking_whatsapp.wav",
    "Sending WhatsApp message.": "sending_whatsapp.wav",
}

WAKE_ACKS = [
    "Yes?",
    "I'm listening.",
]
# Rotated when wake_ack = "voice" (any that exist in the cache or were synthesized at warm-up).
WAKE_VOICE_ACKS = ["I'm listening.", "Go ahead.", "Mm-hmm?", "What's up?", "Tell me.", "Ready."]

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
        self._norm_cache: Dict[str, bytes] = {}
        self._norm_durations: Dict[str, float] = {}
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
                        norm_key = phrase.strip().rstrip(".").lower()
                        self._norm_cache[norm_key] = frames
                        self._norm_durations[norm_key] = duration_ms
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

    def get_wake_ack(self) -> Tuple[str, bytes, float]:
        """Spoken wake acknowledgement, rotated so it never sounds canned (prefers phrases other than 'Yes?')."""
        preferred = [p for p in WAKE_VOICE_ACKS if p in self._ram_cache and p not in self._recent_history]
        fallback = [p for p in WAKE_VOICE_ACKS + ["Yes?", "Okay."] if p in self._ram_cache]
        chosen = random.choice(preferred) if preferred else (fallback[0] if fallback else "Okay.")
        self.record_played(chosen)
        pcm = self._ram_cache.get(chosen, b"")
        duration = self._durations.get(chosen, 300.0)
        return chosen, pcm, duration

    def get_phrase_bytes(self, phrase: str) -> Optional[Tuple[bytes, float]]:
        """O(1) direct lookup for a specific phrase (e.g. 'Please confirm.', 'Cancelled.')."""
        if phrase in self._ram_cache:
            return self._ram_cache[phrase], self._durations.get(phrase, 350.0)

        norm_key = phrase.strip().rstrip(".").lower()
        if norm_key in self._norm_cache:
            return self._norm_cache[norm_key], self._norm_durations.get(norm_key, 350.0)

        # Fast prefix matching to existing cached clips (0ms delay)
        if norm_key.startswith("opening"):
            if "chrome" in norm_key and "opening chrome" in self._norm_cache:
                return self._norm_cache["opening chrome"], self._norm_durations.get("opening chrome", 350.0)
            if "notepad" in norm_key and "opening notepad" in self._norm_cache:
                return self._norm_cache["opening notepad"], self._norm_durations.get("opening notepad", 350.0)
            if "opening it" in self._norm_cache:
                return self._norm_cache["opening it"], self._norm_durations.get("opening it", 350.0)
        if norm_key.startswith("sending") and "sending whatsapp message" in self._norm_cache:
            return self._norm_cache["sending whatsapp message"], self._norm_durations.get("sending whatsapp message", 350.0)
        if (norm_key.startswith("checking") or norm_key.startswith("searching") or "whatsapp" in norm_key) and "checking your whatsapp messages" in self._norm_cache:
            return self._norm_cache["checking your whatsapp messages"], self._norm_durations.get("checking your whatsapp messages", 350.0)
        return None

    def add_phrase(self, phrase: str, pcm: bytes, sample_rate: int | None = None) -> None:
        """Cache a phrase synthesized at runtime (e.g. extra wake acknowledgements)."""
        if not pcm:
            return
        rate = sample_rate or self.sample_rate
        duration_ms = len(pcm) / (self.channels * self.sample_width * rate) * 1000.0
        self._ram_cache[phrase] = pcm
        self._durations[phrase] = duration_ms
        norm_key = phrase.strip().rstrip(".").lower()
        self._norm_cache[norm_key] = pcm
        self._norm_durations[norm_key] = duration_ms

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
