"""Low-latency answer streaming: model tokens -> sentences -> speech / live UI text.

The chat model produces text token by token. Waiting for the whole answer before speaking
adds the full generation time to every spoken reply. Instead the command service installs a
:class:`StreamSink` for the current request (a context variable, so it follows the request
through the executor without changing any tool signature). The assistant feeds deltas into
it; complete sentences are handed to the speech lane as soon as they exist, and the partial
text is published for the UI.
"""
from __future__ import annotations

import re
import time
from contextvars import ContextVar
from typing import Callable, Optional

_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e", "approx", "no", "fig", "inc", "ltd",
}
_BOUNDARY = re.compile(r"[.!?]+[\"')\]]*\s+|\n{1,}")


class SentenceChunker:
    """Turns a stream of text deltas into speakable sentences.

    The first chunk is released early (at a comma once it is long enough) so speech starts
    quickly; later chunks follow sentence boundaries. Abbreviations and decimals never split.
    """

    def __init__(self, first_min_chars: int = 28, max_chars: int = 200):
        self.first_min_chars = first_min_chars
        self.max_chars = max_chars
        self._buffer = ""
        self._emitted = 0

    def _split_point(self) -> int:
        buf = self._buffer
        for match in _BOUNDARY.finditer(buf):
            end = match.end()
            head = buf[: match.start()].rstrip()
            last_word = re.split(r"\s+", head)[-1].lower().rstrip(".") if head else ""
            if last_word in _ABBREVIATIONS or (len(last_word) == 1 and last_word.isalpha() and buf[match.start()] == "."):
                continue
            if len(head.strip()) < 2:
                continue
            return end
        min_len = self.first_min_chars if self._emitted == 0 else self.max_chars
        if len(buf) >= min_len:
            cut = max(buf.rfind(", ", 0, self.max_chars), buf.rfind("; ", 0, self.max_chars), buf.rfind(": ", 0, self.max_chars))
            if cut >= min(self.first_min_chars, len(buf) // 3) and (self._emitted == 0 or len(buf) >= self.max_chars):
                return cut + 2
            if len(buf) >= self.max_chars:
                space = buf.rfind(" ", 0, self.max_chars)
                return space + 1 if space > 0 else self.max_chars
        return -1

    def feed(self, delta: str) -> list[str]:
        self._buffer += delta or ""
        out: list[str] = []
        while True:
            cut = self._split_point()
            if cut <= 0:
                break
            piece, self._buffer = self._buffer[:cut].strip(), self._buffer[cut:]
            if piece:
                out.append(piece)
                self._emitted += 1
        return out

    def flush(self) -> list[str]:
        piece, self._buffer = self._buffer.strip(), ""
        if piece:
            self._emitted += 1
            return [piece]
        return []


class StreamSink:
    """Receives model deltas for one request and fans them out to speech and UI."""

    def __init__(
        self,
        on_sentence: Optional[Callable[[str], None]] = None,
        on_text: Optional[Callable[[str], None]] = None,
        text_interval_s: float = 0.06,
        max_spoken_chars: int = 600,
    ):
        self.on_sentence = on_sentence
        self.on_text = on_text
        self.text_interval_s = text_interval_s
        self.max_spoken_chars = max_spoken_chars
        self.chunker = SentenceChunker()
        self.text = ""
        self.sentences: list[str] = []
        self.spoken_chars = 0
        self.first_delta_at: int | None = None
        self.first_sentence_at: int | None = None
        self._last_text_emit = 0.0
        self.closed = False

    @property
    def spoke(self) -> bool:
        return bool(self.sentences)

    def _speak(self, sentence: str) -> None:
        if self.on_sentence is None or self.spoken_chars >= self.max_spoken_chars:
            return
        if self.first_sentence_at is None:
            self.first_sentence_at = time.perf_counter_ns()
        self.sentences.append(sentence)
        self.spoken_chars += len(sentence)
        try:
            self.on_sentence(sentence)
        except Exception:
            pass

    def _publish(self, force: bool = False) -> None:
        if self.on_text is None:
            return
        now = time.perf_counter()
        if force or now - self._last_text_emit >= self.text_interval_s:
            self._last_text_emit = now
            try:
                self.on_text(self.text)
            except Exception:
                pass

    def feed(self, delta: str) -> None:
        if self.closed or not delta:
            return
        if self.first_delta_at is None:
            self.first_delta_at = time.perf_counter_ns()
        self.text += delta
        for sentence in self.chunker.feed(delta):
            self._speak(sentence)
        self._publish()

    def close(self) -> None:
        if self.closed:
            return
        for sentence in self.chunker.flush():
            self._speak(sentence)
        self._publish(force=True)
        self.closed = True


current_stream: ContextVar[Optional[StreamSink]] = ContextVar("jarvis_answer_stream", default=None)
