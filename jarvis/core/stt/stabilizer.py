"""Transcript stabilizer for JARVIS EDGE.

Tracks longest common stable prefix across repeated Whisper hypotheses.
Words remaining unchanged across N consecutive revisions become stable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter_ns

from jarvis.core.stt.base import TranscriptPartial, TranscriptStablePrefix


from jarvis.core.stt.prefix_consensus import PrefixConsensus, TranscriptView


class TranscriptStabilizer:
    """Stabilizes streaming transcripts using PrefixConsensus across hypotheses."""

    def __init__(self, stability_threshold: int = 2, session_id: str = ""):
        self.stability_threshold = max(2, stability_threshold)
        self.session_id = session_id
        self._consensus = PrefixConsensus(agreement=self.stability_threshold)
        if session_id:
            self._consensus.start(session_id)
        self._seq = 0
        self._stable_prefix = ""

    def update(self, partial: TranscriptPartial) -> TranscriptStablePrefix | None:
        """Process a new partial transcript, return stable prefix if updated.

        Returns None if stable prefix hasn't changed.
        """
        turn_id = self.session_id or partial.session_id or "default"
        if self._consensus.turn_id != turn_id:
            self._consensus.start(turn_id)
        self._seq += 1
        words = partial.text.strip().split()
        if not words:
            return None

        view = self._consensus.update(turn_id, self._seq, partial.text.strip())
        if view.stable != self._stable_prefix:
            self._stable_prefix = view.stable
            return TranscriptStablePrefix(
                session_id=turn_id,
                text=view.stable,
                stability_score=min(1.0, len(view.stable.split()) / max(len(words), 1)),
                revision_count=view.revision,
            )
        return None

    @property
    def stable_prefix(self) -> str:
        """Current stable prefix text."""
        return self._stable_prefix

    @property
    def revision_count(self) -> int:
        return self._consensus.view.revision

    def reset(self) -> None:
        """Reset for new session."""
        self._seq = 0
        self._stable_prefix = ""
        if self.session_id:
            self._consensus.start(self.session_id)
        else:
            self._consensus = PrefixConsensus(agreement=self.stability_threshold)

