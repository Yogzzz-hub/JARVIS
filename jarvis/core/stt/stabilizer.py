"""Transcript stabilizer for JARVIS EDGE.

Tracks longest common stable prefix across repeated Whisper hypotheses.
Words remaining unchanged across N consecutive revisions become stable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter_ns

from jarvis.core.stt.base import TranscriptPartial, TranscriptStablePrefix


class TranscriptStabilizer:
    """Stabilizes streaming transcripts by tracking consistent word prefixes.

    Whisper partial outputs may rewrite earlier words:
      Update 1: "open visual"
      Update 2: "open visual studio"
      Update 3: "open visual studio coat"
      Update 4: "open visual studio code"

    Only words unchanged across `stability_threshold` consecutive
    hypotheses are promoted to stable prefix.
    """

    def __init__(self, stability_threshold: int = 2, session_id: str = ""):
        self.stability_threshold = stability_threshold
        self.session_id = session_id
        self._revision_count = 0
        self._word_counts: dict[int, int] = {}  # word_position -> consecutive_match_count
        self._last_words: list[str] = []
        self._stable_prefix: str = ""
        self._stable_word_count: int = 0

    def update(self, partial: TranscriptPartial) -> TranscriptStablePrefix | None:
        """Process a new partial transcript, return stable prefix if updated.

        Returns None if stable prefix hasn't changed.
        """
        self._revision_count += 1
        current_words = partial.text.strip().split()

        if not current_words:
            return None

        # Compare with previous words to find matching prefix
        mismatch_idx = len(current_words)
        for i, word in enumerate(current_words):
            if i < len(self._last_words) and self._last_words[i].lower() == word.lower():
                # Word matches — increment stability counter
                self._word_counts[i] = self._word_counts.get(i, 0) + 1
            else:
                mismatch_idx = i
                break

        # Invalidate any word counts beyond the matching prefix
        max_len = max(len(current_words), len(self._last_words))
        for j in range(mismatch_idx, max_len + 1):
            self._word_counts.pop(j, None)

        # Words from mismatch_idx onwards in current_words are seen for the first time
        for k in range(mismatch_idx, len(current_words)):
            self._word_counts[k] = 1

        # Determine stable prefix: longest prefix where all words meet threshold
        stable_end = 0
        for i in range(len(current_words)):
            count = self._word_counts.get(i, 0)
            if count >= self.stability_threshold:
                stable_end = i + 1
            else:
                break

        self._last_words = current_words

        # Check if stable prefix actually changed
        new_stable = " ".join(current_words[:stable_end]) if stable_end > 0 else ""
        if new_stable == self._stable_prefix:
            return None

        self._stable_prefix = new_stable
        self._stable_word_count = stable_end

        return TranscriptStablePrefix(
            session_id=self.session_id or partial.session_id,
            text=new_stable,
            stability_score=min(1.0, stable_end / max(len(current_words), 1)),
            revision_count=self._revision_count,
        )

    @property
    def stable_prefix(self) -> str:
        """Current stable prefix text."""
        return self._stable_prefix

    @property
    def revision_count(self) -> int:
        return self._revision_count

    def reset(self) -> None:
        """Reset for new session."""
        self._revision_count = 0
        self._word_counts.clear()
        self._last_words.clear()
        self._stable_prefix = ""
        self._stable_word_count = 0
