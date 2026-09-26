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
    return re.sub(r"[ \t]+", " ", out).strip()


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
