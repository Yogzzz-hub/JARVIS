"""Linguistic normalization; vocabulary mappings never authorize capabilities."""
from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo
from jarvis.core.capabilities.temporal import TemporalResolver
from jarvis.integrations.whatsapp.personal_reply.language import detect
from jarvis.integrations.whatsapp.personal_reply.understand import understand
from .models import SemanticMessageFrame, UnderstandingConfidence

VARIANTS = {"ena": "enna", "epdi": "eppadi", "pandra": "panra", "pannura": "panra", "iruka": "irukka",
            "anupu": "anuppu", "anupidu": "anuppu", "anupdu": "anuppu", "aprm": "aprom", "sari": "seri",
            "venda": "venam", "vendam": "venam", "naalaiku": "tomorrow", "nethu": "yesterday",
            "ippo": "now", "tmrw": "tomorrow", "pls": "please", "msg": "message", "u": "you",
            "kaatu": "show", "kaattu": "show", "kaami": "show", "thedu": "search",
            "maathu": "change", "pannu": "do", "kudu": "give", "anuppadha": "do not send"}


class TanglishNormalizer:
    def normalize(self, text: str, lexicon: dict[str, str] | None = None) -> str:
        terms = {**VARIANTS, **(lexicon or {})}
        text = re.sub(r"([a-z])\1{2,}", r"\1\1", text.casefold())
        return re.sub(r"\b[a-z]+\b", lambda m: terms.get(m[0], m[0]), text)


def semantic_frame(thread_id: str, text: str, timestamp: float, message_id: str = "", timezone: str = "Asia/Kolkata", lexicon: dict[str, str] | None = None) -> SemanticMessageFrame:
    # Raw text is durable in wa_events; linguistic parsing has a bounded window.
    normalized = TanglishNormalizer().normalize(text[:4000], lexicon)
    und = understand(normalized, use_jde=False)
    negations = re.findall(r"\b(?:don't|do not|never|not|venam|illa|except)\b[^.!?]*", normalized)
    references = re.findall(r"\b(?:it|that|this|him|her|they|same one|previous one|second one|avan|atha|athu)\b", normalized)
    parts = re.split(r"(?:,?\s+(?:actually|make that|instead)|\.\.\.\s*no,)\s+", normalized, maxsplit=1)
    corrections = [{"old": parts[0].strip(), "new": parts[1].split('.')[0].strip()}] if len(parts) == 2 else []
    temporal, _ = TemporalResolver(datetime.fromtimestamp(timestamp, ZoneInfo(timezone))).resolve(normalized)
    date = str(getattr(temporal, "isoformat", getattr(temporal, "start_iso", ""))) if temporal else ""
    act = "CORRECTION" if corrections else "NEGATION" if negations else und.intent
    if re.search(r"\b(?:venum|need|please|anuppu|sollu|kudu)\b", normalized) and not negations and act == "STATEMENT":
        act = "REQUEST"
    return SemanticMessageFrame(thread_id=thread_id, message_id=message_id, raw_text=text,
        normalized_text=normalized, language_mix=detect(text).label, speech_act=act, references=references,
        entities=re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}\b", text), negations=negations,
        corrections=corrections, temporal_expressions=[{"value": date, "source_timestamp": timestamp}] if temporal else [],
        requested_actions=[normalized] if act == "REQUEST" else [],
        confidence=UnderstandingConfidence(intent=und.confidence, requested_action=und.confidence if act == "REQUEST" else 0,
            temporal_reference=0.9 if temporal else 0))


def reply_necessity(frame: SemanticMessageFrame) -> str:
    if frame.speech_act in {"ACK", "EMPTY"}:
        return "NO_REPLY_NEEDED"
    if frame.speech_act in {"UNCLEAR", "CORRECTION", "NEGATION"}:
        return "USER_DECISION_REQUIRED"
    return "REPLY_REQUIRED" if frame.speech_act in {"REQUEST", "QUESTION"} else "REPLY_OPTIONAL"
