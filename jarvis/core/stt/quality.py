"""Transcript quality: keep what was really said, drop what Whisper invented from noise.

Whisper is trained to always produce text, so on background noise, fans, music or a TV it "hears" things:
filler ("Also, we..."), subtitle credits ("Thanks for watching") and repetition loops ("Akash Anna, Akash Anna,
Akash Anna ..."). Three independent checks remove them:

1. per segment, Whisper's own confidence: ``no_speech_prob`` (it thinks nothing was said), ``avg_logprob``
   (low certainty) and ``compression_ratio`` (a highly repetitive, i.e. looping, output);
2. repetition loops in the text itself (the same 1-4 word phrase three or more times in a row);
3. too much text for too little real speech (words per second of voiced audio no human produces).

``prepare_audio`` removes low-frequency rumble (fans, AC hum, desk bumps) and normalises the level, which helps
recognition on laptop microphones without adding latency.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

import numpy as np

# Segment confidence thresholds (faster-whisper segment fields).
MAX_NO_SPEECH_PROB = 0.6      # together with a low logprob: "nothing was said here"
NO_SPEECH_LOGPROB = -0.8
MIN_AVG_LOGPROB = -1.15       # below this Whisper is guessing
MAX_COMPRESSION_RATIO = 2.4   # above this the segment is a repetition loop
MAX_WORDS_PER_SECOND = 5.5    # fast human speech is ~3-4 words/s

KNOWN_NOISE_PHRASES = frozenset({
    "you", "thank you", "thanks", "thanks for watching", "thank you for watching", "please subscribe", "subscribe",
    "subtitles by the amara.org community", "subtitles", "bye", "bye bye", "so", "um", "uh", "hmm", "okay", "also we",
    "also", "and", "the", "i", "oh", "ah", "music", "applause", "laughter", "silence", "[music]", "[applause]",
    "[blank_audio]", "(music)", "(silence)",
})


def segment_ok(seg: Any) -> bool:
    """Keep a faster-whisper segment only when Whisper itself believes something was said."""
    nsp = float(getattr(seg, "no_speech_prob", 0.0) or 0.0)
    lp = float(getattr(seg, "avg_logprob", 0.0) or 0.0)
    cr = float(getattr(seg, "compression_ratio", 1.0) or 1.0)
    if nsp > MAX_NO_SPEECH_PROB and lp < NO_SPEECH_LOGPROB:
        return False
    if lp < MIN_AVG_LOGPROB:
        return False
    if cr > MAX_COMPRESSION_RATIO:
        return False
    return True


def _words(text: str) -> list[str]:
    return re.findall(r"[\w']+", (text or "").lower())


def repetition_loop(text: str, min_repeats: int = 3) -> bool:
    """True when a 1-4 word phrase repeats back to back ``min_repeats`` times ("akash anna, akash anna, ...")."""
    w = _words(text)
    for n in range(1, 5):
        if len(w) < n * min_repeats:
            continue
        for i in range(0, len(w) - n * min_repeats + 1):
            phrase = w[i:i + n]
            if all(w[i + k * n:i + (k + 1) * n] == phrase for k in range(min_repeats)):
                # "no no no" / "very very very" are real speech for n == 1 with short words; be stricter there
                if n == 1 and min_repeats < 4 and len(w) <= 4:
                    continue
                return True
    return False


def clean_transcript(text: str, speech_ms: float | None = None) -> str:
    """Final text to act on, or "" when it is noise / a Whisper hallucination."""
    t = " ".join((text or "").split()).strip()
    t = re.sub(r"\s*(?:\.\.\.|…)\s*$", "", t)  # "Also, we..." - trailing ellipsis marks a cut-off guess
    t = re.sub(r"[\[(][^\])]{0,40}[\])]", " ", t).strip()  # "[BLANK_AUDIO]", "(music)" annotations
    norm = " ".join(_words(t))
    if not norm or norm in KNOWN_NOISE_PHRASES:
        return ""
    if repetition_loop(t):
        return ""
    if speech_ms is not None and speech_ms > 0:
        words = len(norm.split())
        if words >= 4 and words / max(speech_ms / 1000.0, 0.25) > MAX_WORDS_PER_SECOND:
            return ""  # far more words than the voiced audio could hold
    return t


def join_segments(segments: Iterable[Any]) -> tuple[str, list[dict]]:
    """Text from the trustworthy segments only (plus their details for the UI/logs)."""
    kept, info = [], []
    for seg in segments:
        text = (getattr(seg, "text", "") or "").strip()
        ok = segment_ok(seg)
        info.append({"start": getattr(seg, "start", 0.0), "end": getattr(seg, "end", 0.0), "text": text, "kept": ok,
                     "avg_logprob": round(float(getattr(seg, "avg_logprob", 0.0) or 0.0), 3),
                     "no_speech_prob": round(float(getattr(seg, "no_speech_prob", 0.0) or 0.0), 3)})
        if ok and text:
            kept.append(text)
    return " ".join(kept).strip(), info


def prepare_audio(pcm: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    """High-pass at ~90 Hz (rumble, hum, bumps) and normalise the peak to ~-3 dBFS."""
    x = np.asarray(pcm, dtype=np.float32)
    if x.size == 0:
        return x
    try:  # 4th-order Butterworth high-pass when SciPy is installed
        from scipy.signal import butter, sosfilt
        sos = butter(4, 90.0 / (sample_rate / 2), btype="highpass", output="sos")
        y = sosfilt(sos, x).astype(np.float32)
    except Exception:  # vectorised fallback: subtract a ~11 ms moving average (removes rumble and DC offset)
        k = max(3, int(sample_rate / 90.0))
        y = x - np.convolve(x, np.ones(k, dtype=np.float32) / k, mode="same")
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak > 1e-4:
        y = y * min(4.0, 0.7 / peak)
    return y.astype(np.float32)
