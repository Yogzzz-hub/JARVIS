"""Profile-derived reply modality prediction; no sending or tool execution."""
from __future__ import annotations

from dataclasses import dataclass

from jarvis.integrations.whatsapp.personal_reply import language
from jarvis.integrations.whatsapp.personal_reply.models import ContactStyleProfile


@dataclass(frozen=True)
class ModalityPrediction:
    modality: str
    confidence: float
    sticker_hash: str = ""


def observed(text: str) -> str:
    emoji = bool(language.emojis(text))
    letters = "".join(ch for ch in text if not language.is_emoji(ch) and ch not in "\ufe0f\u200d").strip(" \t.!?,")
    return "EMOJI_ONLY" if emoji and not letters else "TEXT_EMOJI" if emoji else "TEXT"


def predict(profile: ContactStyleProfile, conversation_mode: str, *, sensitive: bool = False,
            sticker_candidates: list[dict] | None = None) -> ModalityPrediction:
    if sensitive or conversation_mode in ("URGENT", "SERIOUS", "APOLOGETIC", "TECHNICAL"):
        return ModalityPrediction("TEXT", 1.0)
    counts = profile.modality_counts or {}
    total = sum(max(0, int(value)) for value in counts.values())
    if total < 20:
        return ModalityPrediction("TEXT", 0.5)
    sticker = (sticker_candidates or [])[:1]
    if sticker and counts.get("STICKER_ONLY", 0) / total >= 0.4 and sticker[0].get("score", 0) >= 0.55:
        return ModalityPrediction("STICKER_ONLY", min(0.95, counts["STICKER_ONLY"] / total),
                                  sticker[0]["sticker_hash"])
    if conversation_mode in ("NO_REPLY_NEEDED", "CASUAL") and counts.get("EMOJI_ONLY", 0) / total >= 0.55:
        return ModalityPrediction("EMOJI_ONLY", min(0.95, counts["EMOJI_ONLY"] / total))
    if counts.get("TEXT_EMOJI", 0) / total >= 0.5:
        return ModalityPrediction("TEXT_EMOJI", min(0.95, counts["TEXT_EMOJI"] / total))
    return ModalityPrediction("TEXT", max(0.5, counts.get("TEXT", 0) / total))
