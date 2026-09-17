"""TTS Manager for JARVIS EDGE Phase 7.

Orchestrates primary Piper engine, Windows SAPI fallback, keep-warm lifecycle,
and privacy-preserving bounded cache for generic final phrases.
"""
from __future__ import annotations

import collections
import logging
from typing import AsyncIterable, Dict, Optional, Tuple

from jarvis.core.tts.base import TTSChunk, TTSEngine
from jarvis.core.tts.piper_engine import PiperEngine
from jarvis.core.tts.sapi_engine import SAPIEngine

logger = logging.getLogger("jarvis.tts.manager")

# Only completely generic, non-sensitive phrases are allowed to be cached in RAM
GENERIC_CACHEABLE_PHRASES = {
    "Done.",
    "Stopped.",
    "Cancelled.",
    "Please confirm.",
    "I couldn't find it.",
    "Screenshot saved.",
    "The folder is empty.",
    "The file has been deleted.",
    "Task cancelled.",
    "Task completed and verified.",
}


class TTSManager:
    """Manages TTS engines, fallbacks, lifecycle, and memory caches."""

    def __init__(
        self,
        piper_engine: Optional[PiperEngine] = None,
        sapi_engine: Optional[SAPIEngine] = None,
        keep_warm: bool = True,
        cache_capacity: int = 32,
    ) -> None:
        self.piper = piper_engine or PiperEngine()
        self.sapi = sapi_engine or SAPIEngine()
        self.keep_warm = keep_warm

        # Privacy-conscious bounded cache for generic phrases only
        self._generic_phrase_cache: Dict[str, bytes] = {}
        self._cache_capacity = cache_capacity

        # Operational metrics
        self.piper_syntheses = 0
        self.piper_failures = 0
        self.sapi_syntheses = 0
        self.sapi_fallbacks = 0
        self.text_only_fallbacks = 0
        self.active_backend = "piper"

    def warm_up(self) -> None:
        """Pre-warm primary Piper engine if keep_warm is enabled."""
        if self.keep_warm:
            try:
                self.piper.load()
                self.active_backend = "piper"
                logger.info("Piper TTS engine pre-warmed successfully")
            except Exception as exc:
                logger.warning("Piper pre-warm failed; preparing SAPI fallback: %s", exc)
                self.piper_failures += 1
                try:
                    self.sapi.load()
                    self.active_backend = "sapi"
                except Exception:
                    self.active_backend = "text_only"

    def synthesize(self, text: str) -> Tuple[bytes, str]:
        """Synthesize text using primary engine with fallback chain.

        Returns (pcm_bytes, backend_used).
        """
        clean_text = text.strip()
        if not clean_text:
            return b"", "none"

        # Check generic phrase cache
        if clean_text in self._generic_phrase_cache:
            return self._generic_phrase_cache[clean_text], "cache"

        # 1. Try Piper
        try:
            pcm = self.piper.synthesize(clean_text)
            if pcm:
                self.piper_syntheses += 1
                self.active_backend = "piper"
                self._maybe_cache_generic(clean_text, pcm)
                return pcm, "piper"
            raise RuntimeError("Piper produced empty audio")
        except Exception as p_err:
            logger.warning("Piper synthesis failed (%s); falling back to SAPI", p_err)
            self.piper_failures += 1
            self.sapi_fallbacks += 1

        # 2. Try SAPI
        try:
            pcm = self.sapi.synthesize(clean_text)
            if pcm:
                self.sapi_syntheses += 1
                self.active_backend = "sapi"
                self._maybe_cache_generic(clean_text, pcm)
                return pcm, "sapi"
            raise RuntimeError("SAPI produced empty audio")
        except Exception as s_err:
            logger.error("Both Piper and SAPI failed: %s; falling back to text-only", s_err)
            self.text_only_fallbacks += 1
            self.active_backend = "text_only"
            return b"", "text_only"

    async def stream(self, text: str) -> AsyncIterable[Tuple[TTSChunk, str]]:
        """Stream chunks using primary engine with fallback to SAPI."""
        clean_text = text.strip()
        if not clean_text:
            return

        # 1. Try Piper streaming
        stream_success = False
        try:
            async for chunk in self.piper.stream(clean_text):
                stream_success = True
                self.active_backend = "piper"
                yield chunk, "piper"
            if stream_success:
                self.piper_syntheses += 1
                return
        except Exception as p_err:
            logger.warning("Piper streaming failed (%s); falling back to SAPI", p_err)
            self.piper_failures += 1
            self.sapi_fallbacks += 1

        # 2. Fallback to SAPI
        try:
            async for chunk in self.sapi.stream(clean_text):
                self.sapi_syntheses += 1
                self.active_backend = "sapi"
                yield chunk, "sapi"
            return
        except Exception as s_err:
            logger.error("Both Piper and SAPI stream failed: %s; fallback to text-only", s_err)
            self.text_only_fallbacks += 1
            self.active_backend = "text_only"

    def _maybe_cache_generic(self, text: str, pcm: bytes) -> None:
        """Cache generic non-sensitive phrase if cache has capacity."""
        if text in GENERIC_CACHEABLE_PHRASES and len(self._generic_phrase_cache) < self._cache_capacity:
            self._generic_phrase_cache[text] = pcm

    def cancel(self) -> None:
        """Cancel ongoing synthesis across engines."""
        self.piper.cancel()
        self.sapi.cancel()

    def unload(self) -> None:
        """Unload models and release memory."""
        self.piper.unload()
        self.sapi.unload()
        self._generic_phrase_cache.clear()
