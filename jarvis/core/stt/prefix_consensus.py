"""Prefix Consensus Algorithm for Streaming STT Stabilization.

Implements the research-verified PrefixConsensus mechanism:
- Requires explicit turn creation and full-turn same-origin hypotheses.
- Tracks monotonic audio sequence numbers to reject replayed hypotheses.
- Enforces strict agreement across N consecutive hypotheses (default N=2).
- Automatically clears history when a prefix contradiction occurs.
- Emits immutable TranscriptView updates with revision tracking.
"""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass


def _norm(token: str) -> str:
    """Comparison form of a word: Whisper revises case and punctuation ("Chrome," / "chrome") without changing it."""
    return re.sub(r"[^\w']", "", token.lower())


def _common(a: tuple[str, ...], b: tuple[str, ...]) -> int:
    n = 0
    for x, y in zip(a, b):
        if _norm(x) != _norm(y):
            break
        n += 1
    return n


@dataclass(frozen=True)
class TranscriptView:
    """Immutable view of current transcript consensus state."""
    turn_id: str
    revision: int
    stable: str
    unstable: str
    final: bool = False


class PrefixConsensus:
    """Full-turn, same-origin hypotheses; stable text is only a hint."""

    def __init__(self, agreement: int = 2):
        if agreement < 2:
            raise ValueError("At least two hypotheses are required")
        self.agreement = agreement
        self.history: deque[tuple[str, ...]] = deque(maxlen=agreement)
        self.turn_id = ""
        self.last_audio_seq = -1
        self.stable_tokens: tuple[str, ...] = ()
        self.view = TranscriptView("", 0, "", "")

    def start(self, turn_id: str) -> None:
        """Start a new turn session."""
        if not turn_id:
            raise ValueError("A turn ID is required")
        self.turn_id = turn_id
        self.last_audio_seq = -1
        self.stable_tokens = ()
        self.history.clear()
        self.view = TranscriptView(turn_id, 0, "", "")

    def update(self, turn_id: str, audio_seq: int, text: str) -> TranscriptView:
        """Update consensus with a new streaming hypothesis."""
        if turn_id != self.turn_id or self.view.final:
            return self.view  # Late result from another or closed turn.
        if audio_seq <= self.last_audio_seq:
            return self.view  # Replayed hypotheses do not count as agreement.
        self.last_audio_seq = audio_seq
        words = tuple(text.split())
        keep = _common(self.stable_tokens, words)
        if keep < len(self.stable_tokens):
            # A real revision: drop only the words it contradicts, keep the agreed part before them (no flicker
            # back to an empty line), and forget the older hypotheses that led to the contradicted words.
            self.stable_tokens = words[:keep]
            self.history.clear()
        self.history.append(words)

        common: tuple[str, ...] = self.stable_tokens[:_common(self.stable_tokens, words)]
        if len(self.history) == self.agreement:
            n = min(len(h) for h in self.history)
            for i in range(n):
                if any(_norm(h[i]) != _norm(words[i]) for h in self.history):
                    n = i
                    break
            if n > len(common):
                # words already stable keep the form they were shown (and typed) in; only new words are added
                common = common + words[len(common):n]

        changed = common != self.stable_tokens
        self.stable_tokens = common
        self.view = TranscriptView(
            turn_id=turn_id,
            revision=self.view.revision + int(changed),
            stable=" ".join(common),
            unstable=" ".join(words[len(common):]),
        )
        return self.view

    def finish(self, turn_id: str, authoritative_text: str) -> TranscriptView:
        """Finalize consensus turn with authoritative transcript."""
        if turn_id != self.turn_id:
            raise ValueError("Wrong turn")
        if self.view.final:
            raise ValueError("Turn already finalized")
        self.history.clear()
        self.view = TranscriptView(
            turn_id, self.view.revision + 1, authoritative_text, "", True
        )
        return self.view
