"""Generate one reply candidate with the existing local LLM (the WhatsApp ``chat`` role).

No planner, no tools: one compact JSON call. When the model is offline there is NO canned fallback
reply for auto mode - the message is held for the owner instead of guessing.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from jarvis.integrations.whatsapp.personal_reply import language as lang
from jarvis.integrations.whatsapp.personal_reply.context_builder import ReplyContext
from jarvis.integrations.whatsapp.personal_reply.models import ContactStyleProfile, ReplyCandidate

logger = logging.getLogger("jarvis.whatsapp.personal_reply.generator")

SCHEMA = {"type": "object", "properties": {"reply": {"type": "string"}, "understood": {"type": "boolean"},
                                           "confidence": {"type": "number"}, "intent": {"type": "string"}},
          "required": ["reply", "understood", "confidence"]}
_LEADING_AI = re.compile(r"^(?:certainly|sure thing|of course|absolutely)[!,.]\s+", re.I)
_TRAILING_AI = re.compile(r"\s*(?:let me know if you need anything else|hope this helps|feel free to ask)[.!]?\s*$", re.I)


def postprocess(text: str, profile: ContactStyleProfile, owner_uses_ai_phrases: bool = False) -> str:
    out = (text or "").strip().strip('"').strip()
    out = re.sub(r"^(?:you|me|reply|owner)\s*:\s*", "", out, flags=re.I)
    if not owner_uses_ai_phrases:
        out = _LEADING_AI.sub("", out)
        out = _TRAILING_AI.sub("", out)
    if profile.emoji_frequency < 0.05:
        out = "".join(ch for ch in out if not lang.is_emoji(ch)).strip()
    if profile.capitalization_style == "lowercase" and out[:1].isupper() and not out[:2].isupper():
        out = out[:1].lower() + out[1:]
    if profile.punctuation_style == "none":
        out = out.rstrip(".")
    out = apply_habits(out, profile)
    return "\n".join(re.sub(r"[ \t]+", " ", ln).strip() for ln in out.split("\n") if ln.strip())


# Emoji mood groups: a model emoji the owner never uses with this person is swapped for the owner's own emoji with the
# same feeling (😆 -> their 😂), or dropped when they have none (never a laughing emoji on sad news).
EMOJI_MOODS = {
    "laugh": "😂🤣😆😹😁😄😅😝😜🙈",
    "love": "❤️❤😍🥰😘💕💖💗💙💚💛💜🤍🖤♥️😻🫶",
    "smile": "🙂😊☺️☺😇🤗😌😀😃",
    "sad": "😢😭😞😔🥺😟☹️🙁💔😿",
    "ok": "👍👌✅🙏🤝👏💯✌️",
    "wow": "😮😯😲🤯😱😳",
    "angry": "😡😠🤬😤",
    "cool": "😎🔥✨🎉🥳💪",
    "sleep": "😴🥱💤",
    "think": "🤔🧐",
    "food": "😋🍕🍔🍛☕🍫",
}


def _mood(emoji: str) -> str:
    return next((m for m, chars in EMOJI_MOODS.items() if emoji in chars), "")


def _swap_emojis(text: str, profile: ContactStyleProfile) -> str:
    vocab = profile.emoji_vocab
    if not vocab or profile.messages_analyzed < 10:
        return text
    by_mood: dict[str, str] = {}
    for e in vocab:  # most used first
        by_mood.setdefault(_mood(e), e)
    out = []
    for ch in text:
        if lang.is_emoji(ch) and ch not in "\ufe0f\u200d" and ch not in vocab:
            out.append(by_mood.get(_mood(ch), "") if _mood(ch) else "")
        elif ch == "\ufe0f" and out and out[-1] == "":
            continue
        else:
            out.append(ch)
    return "".join(out)


def _repeat_emojis(text: str, run: int) -> str:
    if run < 2:
        return text
    def widen(m: re.Match) -> str:
        return m.group(1) * max(run, len(m.group(0)) // max(1, len(m.group(1))))
    laughing = "".join(re.escape(c) for c in "😂🤣")
    return re.sub(rf"([{laughing}])\1*", widen, text)


def apply_habits(text: str, profile: ContactStyleProfile) -> str:
    """Make a draft read like the owner's own texting with this person (shorthand, laugh, emojis, bursts)."""
    out = text
    for full, short in (profile.shorthand or {}).items():
        out = re.sub(rf"\b{re.escape(full)}\b", short, out, flags=re.I)
    if profile.laugh_style and not lang.emojis(profile.laugh_style):
        out = re.sub(r"\b(?:a?ha(?:ha)+h?|he(?:he)+|lol+|lmao+)\b", profile.laugh_style, out, flags=re.I)
    out = _swap_emojis(out, profile)
    out = _repeat_emojis(out, profile.emoji_run)
    if profile.burst_rate < 0.3:
        out = " ".join(p.strip() for p in out.split("\n") if p.strip())
    elif profile.burst_rate >= 0.5 and "\n" not in out:
        parts = [p for p in re.split(r"(?<=[.!?])\s+", out) if p.strip()]
        if 2 <= len(parts) <= 3:
            out = "\n".join(parts)
    return out


class ReplyGenerator:
    def __init__(self, client: Any = None, role: str = "chat", timeout_s: float = 25.0) -> None:
        self._client = client
        self.role = role
        self.timeout_s = timeout_s

    @property
    def client(self):
        if self._client is not None:
            return self._client
        from jarvis.core.llm.client import get_llm
        return get_llm()

    async def generate(self, ctx: ReplyContext, profile: ContactStyleProfile, owner_uses_ai_phrases: bool = False) -> Optional[ReplyCandidate]:
        lo, hi = profile.length_band()
        max_tokens = min(220, 24 + hi * 4)
        try:
            data = await self.client.chat_json(
                [{"role": "system", "content": ctx.system}, {"role": "user", "content": ctx.user}],
                SCHEMA, role=self.role, max_tokens=max_tokens, timeout=self.timeout_s, temperature=0.5)
        except Exception as exc:
            logger.info("Personal reply model unavailable: %s", exc)
            return None
        text = postprocess(str(data.get("reply", "")), profile, owner_uses_ai_phrases)
        try:
            conf = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        return ReplyCandidate(text=text, understood=bool(data.get("understood", False)), model_confidence=max(0.0, min(1.0, conf)),
                              language_mode=ctx.target_language, examples_used=list(ctx.example_ids), prompt_chars=ctx.prompt_chars)
