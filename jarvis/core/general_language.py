"""Shared, side-effect-free language understanding before capability selection.

The adapter produces meaning and constraints. It never invokes a tool. Uncertain
references, channels and verb senses stay unresolved for the planner or user.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class LanguageFrame:
    text: str
    language: str = "english"
    speech_act: str = "UNKNOWN"
    action: str | None = None
    target_type: str | None = None
    recipient: str | None = None
    channel: str | None = None
    selector: str | None = None
    reference: str | None = None
    exclusions: list[str] = field(default_factory=list)
    corrections: list[dict[str, str]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    candidate_actions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def actionable(self) -> bool:
        return self.speech_act == "COMMAND" and self.action is not None and not self.missing

    def asdict(self) -> dict[str, Any]:
        return asdict(self)


# A phonetic family gives lexical candidates, never a final tool or action.
_FAMILIES = {
    "transfer": ("anupu", "anuppu", "anup", "annupu", "anp", "anpu", "anupidu", "anuppidu", "anuputu", "anuppitu", "sendu"),
    "change": ("maathu", "mathu", "matu", "maathidu", "mathidu"),
    "give": ("kudu", "kodu", "thaa", "thara"),
    "show": ("kaatu", "kaattu", "katu", "katunga"),
    "take": ("eduthu", "edu", "eduthuko", "edunga"),
    "put": ("podu", "podunga", "pottu", "potu"),
    "see": ("paaru", "paru", "paathu", "pathu"),
    "say": ("sollu", "sollunga", "solu"),
    "ask": ("kelu", "kelunga"),
    "get": ("vaangu", "vangu"),
    "keep": ("vechu", "vachu", "vai"),
    "light": ("pannu", "panu", "pannunga", "pannidu", "pannidunga", "panni", "pannitu", "panra", "pandra", "pannura", "pannanum"),
    "convert": ("convert",), "rewrite": ("rewrite",), "capture": ("capture",),
    "insert": ("insert",), "install": ("install",), "check": ("check",),
    "draft": ("draft",), "short": ("short",), "select": ("select",),
    "display": ("display",), "retrieve": ("retrieve",), "summarize": ("summarize",),
    "read": ("read",), "play": ("play",), "enter": ("enter", "type"),
    "create": ("create",), "set": ("set",), "switch": ("switch",),
    "share": ("share", "forward"), "show_en": ("show",),
}
_INDEX = {form: family for family, forms in _FAMILIES.items() for form in forms}
_PHONETIC_FORMS = {form for family in ("transfer", "change", "give", "show", "take", "put", "see", "say", "ask", "get", "keep", "light")
                   for form in _FAMILIES[family]}
_PARTICLES = {"da", "di", "bro", "nga", "ah", "a", "um", "than", "mattum", "please", "jarvis"}
_ORDINALS = {"first": "first", "muthala": "first", "second": "second", "rendaavathu": "second",
             "rendaavadhu": "second", "third": "third", "moonavathu": "third", "last": "last", "kadaisi": "last",
             "latest": "latest", "previous": "previous", "munnadi": "previous"}
_OBJECTS = {
    "screenshot": "SCREENSHOT", "screen": "SCREEN", "photo": "IMAGE", "image": "IMAGE", "picture": "IMAGE",
    "pdf": "PDF", "document": "DOCUMENT", "doc": "DOCUMENT", "file": "FILE", "folder": "FOLDER",
    "clipboard": "CLIPBOARD", "volume": "VOLUME", "sound": "VOLUME", "brightness": "BRIGHTNESS",
    "language": "LANGUAGE", "tab": "TAB", "mode": "MODE", "sentence": "TEXT", "text": "TEXT",
    "answer": "ANSWER", "reply": "REPLY", "summary": "SUMMARY", "number": "NUMBER",
    "song": "AUDIO", "music": "AUDIO", "password": "PASSWORD", "status": "STATUS",
    "software": "SOFTWARE", "app": "APP", "alarm": "ALARM", "calendar": "CALENDAR",
    "message": "MESSAGE", "msg": "MESSAGE", "chat": "CHAT", "emoji": "EMOJI", "database": "DATABASE",
    "backend": "SERVICE", "permission": "PERMISSION", "error": "ERROR", "usage": "METRIC",
}
_TAMIL_CUES = _PHONETIC_FORMS | {"kitta", "kita", "ku", "la", "lendhu", "irundhu", "oda", "atha", "athu", "idhu",
    "itha", "ithu", "avanuku", "avankita", "avanga", "venam", "venda", "vendam", "pannadha",
    "pannadhinga", "panna", "mudiyuma", "illa", "konjam", "kammi", "romba", "ippo", "naalaiku", "inniku"}
_TOKENS = re.compile(r"[a-zA-Z0-9]+(?:[:.][0-9]+)?")


def _family(token: str) -> str | None:
    t = token.casefold()
    if t in _INDEX:
        return _INDEX[t]
    if t in {"send", "message", "file", "answer", "summary", "latest", "saying", "late", "sound", "name", "same"}:
        return None
    # Repeated vowels and common polite/tense endings are lexical variation.
    t = re.sub(r"([a-z])\1{2,}", r"\1\1", t)
    t = re.sub(r"(unga|ingaa|idra|itu|ittu|iya)$", "", t)
    if t in _INDEX:
        return _INDEX[t]
    if len(t) >= 4:
        from difflib import get_close_matches
        match = get_close_matches(t, _PHONETIC_FORMS, n=1, cutoff=0.83)
        if match:
            return _INDEX[match[0]]
    return None


def _sense(family: str | None, obj: str | None, words: set[str], recipient: str | None,
           channel: str | None) -> tuple[str | None, list[str]]:
    """Object and relation evidence resolve a lexical family to an action."""
    if family == "transfer":
        return "SEND", ["SEND", "SHARE", "FORWARD"]
    if family == "change":
        if obj in {"PDF", "DOCUMENT", "IMAGE"} and words & {"word", "docx", "format", "convert"}:
            return "CONVERT_FORMAT", ["CONVERT_FORMAT"]
        if obj == "MODE":
            return "SWITCH_RESOURCE", ["SWITCH_RESOURCE", "SET_VALUE"]
        if obj in {"VOLUME", "BRIGHTNESS", "LANGUAGE"}:
            return "SET_VALUE", ["SET_VALUE", "SWITCH_RESOURCE"]
        if obj == "TAB" or words & {"chrome", "edge", "browser"}:
            return "SWITCH_RESOURCE", ["SWITCH_RESOURCE"]
        if obj == "TEXT" or words & {"professional", "short", "formal"}:
            return "REWRITE_STYLE", ["REWRITE_STYLE"]
        if words & {"replace", "instead"}:
            return "REPLACE_ENTITY", ["REPLACE_ENTITY"]
        return None, ["SET_VALUE", "CONVERT_FORMAT", "SWITCH_RESOURCE", "REPLACE_ENTITY", "REWRITE_STYLE"]
    if family == "give":
        if obj in {"REPLY", "MESSAGE"} and words & {"reply", "draft", "ready"}:
            return "DRAFT_REPLY", ["DRAFT_REPLY", "SEND"]
        if recipient:
            return "SEND", ["SEND", "PROVIDE"]
        if obj in {"ANSWER", "NUMBER", "FILE"}:
            return "PROVIDE", ["PROVIDE", "SEND"]
        if obj == "SUMMARY":
            return "SUMMARIZE", ["SUMMARIZE"]
        if obj == "PERMISSION":
            return "GRANT", ["GRANT"]
        return None, ["PROVIDE", "SEND", "RETURN", "DRAFT_REPLY"]
    if family in {"show", "show_en"}:
        return ({"FILE": "LIST", "FOLDER": "LIST", "IMAGE": "DISPLAY", "SCREEN": "DISPLAY", "MESSAGE": "READ",
                 "METRIC": "SHOW_METRICS", "ERROR": "DIAGNOSE"}.get(obj)
                or ("OPEN" if channel == "browser" else None), ["LIST", "DISPLAY", "READ", "OPEN", "DIAGNOSE"])
    if family == "take":
        return ({"SCREENSHOT": "CAPTURE", "IMAGE": "CAPTURE", "CLIPBOARD": "READ", "DATABASE": "RETRIEVE",
                 "FILE": "SELECT" if words & set(_ORDINALS) else "RETRIEVE",
                 "PDF": "SELECT" if words & set(_ORDINALS) else "RETRIEVE",
                 "DOCUMENT": "SELECT" if words & set(_ORDINALS) else "RETRIEVE"}.get(obj),
                ["CAPTURE", "SELECT", "RETRIEVE", "READ"])
    if family == "put":
        return ({"AUDIO": "PLAY", "VOLUME": "SET_VALUE", "BRIGHTNESS": "SET_VALUE", "PASSWORD": "ENTER",
                 "STATUS": "POST", "SOFTWARE": "INSTALL", "APP": "INSTALL", "ALARM": "CREATE", "CALENDAR": "CREATE",
                 "EMOJI": "INSERT", "TEXT": "INSERT" if words & {"line", "document", "message"} else "ENTER",
                 "FILE": "UPLOAD" if "upload" in words else None}.get(obj),
                ["PLAY", "SET_VALUE", "ENTER", "UPLOAD", "INSTALL", "CREATE", "INSERT"])
    if family == "see":
        return ({"MESSAGE": "READ", "FILE": "INSPECT", "ERROR": "DIAGNOSE", "STATUS": "CHECK_STATUS"}.get(obj),
                ["READ", "INSPECT", "CHECK_STATUS"])
    if family == "say":
        return ("SEND" if recipient else "ANSWER", ["ANSWER", "REPORT", "SEND"])
    if family == "ask":
        return ("ASK" if recipient else None, ["ASK", "LISTEN"])
    if family == "get":
        return ("RETRIEVE" if obj in {"FILE", "DOCUMENT", "PDF"} else None, ["RETRIEVE", "RECEIVE", "BUY"])
    if family == "keep":
        return ("SET_VALUE" if obj in {"VOLUME", "BRIGHTNESS", "LANGUAGE", "MODE"} else None,
                ["KEEP", "PLACE", "SET_VALUE", "USE"])
    explicit = {"convert": "CONVERT_FORMAT", "rewrite": "REWRITE_STYLE", "capture": "CAPTURE",
                "insert": "INSERT", "install": "INSTALL", "check": "CHECK_STATUS", "draft": "DRAFT_REPLY",
                "short": "SUMMARIZE", "select": "SELECT", "display": "DISPLAY", "retrieve": "RETRIEVE",
                "summarize": "SUMMARIZE", "read": "READ", "play": "PLAY", "enter": "ENTER",
                "create": "CREATE", "set": "SET_VALUE", "switch": "SWITCH_RESOURCE"}
    if family in explicit:
        return explicit[family], [explicit[family]]
    if family == "share":
        return "SEND" if recipient or channel else None, ["SEND", "SHARE", "FORWARD"]
    return None, []


class GeneralLanguageUnderstandingEngine:
    """One frame schema for English, Tanglish and uncertain ASR input."""

    @staticmethod
    def canonical_frame(frame: LanguageFrame):
        """Project language evidence into JARVIS's existing canonical frame."""
        from jarvis.core.capabilities.frame import SemanticFrame
        return SemanticFrame(intent=frame.action, actionability=frame.actionable,
            file_types=[frame.target_type.casefold()] if frame.target_type in {"PDF", "DOCUMENT", "IMAGE", "FILE"} else [],
            exclude_constraints=list(frame.exclusions), corrections=list(frame.corrections),
            ambiguity=bool(frame.missing), confidence=frame.confidence, raw_query=frame.text,
            clean_query=frame.text.casefold(), language_features=frame.asdict())

    @staticmethod
    def capability_candidates(frame: LanguageFrame, retriever, top_k: int = 5):
        """Retrieve schemas by semantic meaning; selection still needs policy."""
        if not frame.actionable:
            return []
        query = " ".join(x for x in (frame.action.replace("_", " "), frame.target_type or "",
                                       frame.channel or "") if x).casefold()
        return retriever.retrieve(query, top_k=top_k, min_score=0.0)

    def understand(self, text: str, context: dict[str, Any] | None = None, *, asr_confidence: float | None = None) -> LanguageFrame:
        context = context or {}
        raw = text.strip()
        tokens = _TOKENS.findall(raw)
        lower = [t.casefold() for t in tokens]
        words = set(lower)
        tamil_families = {"transfer", "change", "give", "show", "take", "put", "see", "say", "ask", "get", "keep", "light"}
        frame = LanguageFrame(text=raw, language="tanglish" if words & _TAMIL_CUES or any(
            _family(w[:-4]) in tamil_families if w.endswith("adha") else _family(w) in tamil_families for w in lower)
            else "english")
        if asr_confidence is not None and asr_confidence < 0.65:
            frame.missing.append("asr_confirmation")
        if not tokens:
            return frame
        # Correction supersedes the earlier clause; only the final clause may act.
        clauses = re.split(r"\b(?:illa|actually|sorry|wait|athu illa|ithu illa)\b", raw, flags=re.I)
        if len(clauses) > 1 and clauses[-1].strip():
            frame.corrections.append({"superseded": clauses[-2].strip(), "active": clauses[-1].strip()})
            active = clauses[-1].strip()
            if not re.search(r"\b(?:anup\w*|send|maath\w*|math\w*|podu|kudu|pannu)\b", active, re.I):
                active = clauses[0].strip() + " " + active
            tokens = _TOKENS.findall(active)
            lower = [t.casefold() for t in tokens]
            words = set(lower)
        else:
            active = raw
        for m in re.finditer(r"\b(?:venam|venda|vendam|pannadha|pannadhinga|don't|do not|not|without)\s+([a-z]+)|\b([a-z]+)(?:\s+ku)?\s+(?:venam|venda|vendam|pannadha|pannadhinga)\b", active, re.I):
            frame.exclusions.append((m.group(1) or m.group(2)).casefold())
        recipients = list(re.finditer(r"\b([A-Za-z][A-Za-z'-]{1,39})\s+(?:kitta|kita|ku|kku|ukku)\b(?!\s+related)", active, re.I))
        recipient_match = recipients[-1] if recipients else None
        if recipient_match and recipient_match.group(1).casefold() not in {"pdf", "volume", "english", "word", "chrome", "edge", "file", "second"}:
            frame.recipient = recipient_match.group(1)
        if not frame.recipient:
            english_recipient = re.search(r"\bto\s+([A-Za-z][A-Za-z'-]{1,39})\b", active, re.I)
            if english_recipient:
                frame.recipient = english_recipient.group(1)
        if not frame.recipient:
            pronoun_recipient = re.search(r"\b(avan|ivaru|avanga)(?:uku|kita|kitta)\b", active, re.I)
            if pronoun_recipient:
                frame.recipient = pronoun_recipient.group(1).casefold()
                if not context.get("contact_ref"):
                    frame.missing.append("recipient_reference")
        if re.search(r"\b(?:mail|gmail|email)\s+(?:la|le|via|through)\b", active, re.I):
            frame.channel = "email"
        elif re.search(r"\b(?:whatsapp|chat)\s+(?:la|le|via|through)\b", active, re.I):
            frame.channel = "whatsapp"
        elif re.search(r"\bbrowser\s+(?:la|le)\b", active, re.I):
            frame.channel = "browser"
        positive_active = re.sub(r",?\s+[A-Za-z]+(?:\s+ku)?\s+(?:venam|venda|vendam)\b", "", active, flags=re.I)
        positive_words = set(w.casefold() for w in _TOKENS.findall(positive_active))
        prioritized = ("emoji", "reply", "status", "line", "password", "screenshot")
        frame.target_type = next((_OBJECTS[w] if w in _OBJECTS else "TEXT" for w in prioritized if w in positive_words), None)
        if frame.target_type is None:
            frame.target_type = next((_OBJECTS[w] for w in lower if w in _OBJECTS and w in positive_words), None)
        if frame.target_type is None:
            frame.target_type = next((_OBJECTS[w[:-1]] for w in lower if w.endswith("s") and w[:-1] in _OBJECTS), None)
        if frame.target_type is None and (re.search(r"\b(?:atha|athu|itha|ithu|idhu|same)\b", active, re.I)
                                          or frame.corrections):
            selected = context.get("selected_resource")
            if isinstance(selected, dict):
                frame.target_type = selected.get("target_type")
        frame.selector = next((_ORDINALS[w] for w in lower if w in _ORDINALS), None)
        frame.reference = next((w for w in lower if w in {"atha", "athu", "itha", "ithu", "idhu", "same", "previous"}), None)
        if frame.selector is None and frame.reference and isinstance(context.get("selected_resource"), dict):
            frame.selector = context["selected_resource"].get("selector")
        families = [(w, _family(w[:-4]) if w.endswith("adha") else _family(w)) for w in lower if w not in _PARTICLES]
        families = [(w, f) for w, f in families if f and f != "light"]
        if frame.language == "tanglish" and "send" in words and not families:
            families.append(("send", "transfer"))
        frame.evidence = {"lexical_families": families, "object": frame.target_type, "recipient": frame.recipient,
                          "channel": frame.channel, "context_keys": sorted(context)}
        if re.search(r"\b(?:enna|what|why|how|mudiyuma|can|could|pannuma)\b|\bpanna\s+enna\s+aagum\b", active, re.I) or raw.endswith("?"):
            frame.speech_act = "QUESTION"
        elif re.search(r"\b(?:naan|avan|avanga|he|she|they|i)\b.*\b(?:poren|pannitan|sent|anupitan)\b", active, re.I):
            frame.speech_act = "STATEMENT"
        elif (re.search(r"\b(?:pannadha|pannadhinga|anupadha)\b", active, re.I)
              or re.search(r"\b(?:venam|venda|vendam)\b", active, re.I) and not frame.corrections
              and (not families or frame.exclusions and frame.exclusions[-1] in {"panna", "pannu", "send", "anupu", "anupu"})):
            frame.speech_act = "PROHIBITION"
        else:
            frame.speech_act = "COMMAND" if families else "UNKNOWN"
        if families:
            family = families[-1][1]
            frame.action, frame.candidate_actions = _sense(family, frame.target_type,
                words | set(context.get("semantic_hints", [])) | ({frame.selector} if frame.selector else set()),
                frame.recipient, frame.channel)
            if frame.speech_act == "QUESTION" and family == "transfer":
                frame.action = "CAPABILITY_QUERY" if "mudiyuma" in words else "CHECK_STATUS" if any(
                    w.endswith(("itiya", "ichaa", "iya")) for w in lower) else "HYPOTHETICAL" if "aagum" in words else "EXPLAIN"
        if frame.reference and not context.get("selected_resource"):
            frame.missing.append("reference")
        if frame.action == "SEND" and not frame.channel:
            frame.missing.append("channel")
        if frame.action in {"SEND", "DRAFT_REPLY"} and not frame.recipient and not context.get("thread_ref"):
            frame.missing.append("recipient_or_thread")
        if frame.action in {"READ", "DISPLAY", "SELECT", "RETRIEVE", "CONVERT_FORMAT", "REWRITE_STYLE"} \
                and frame.target_type in {"MESSAGE", "PDF", "DOCUMENT", "IMAGE", "FILE", "TEXT", "TAB"} \
                and not context.get("selected_resource") and not (frame.selector == "latest" and context.get("thread_ref")):
            frame.missing.append("selected_resource")
        if frame.action == "SWITCH_RESOURCE" and frame.target_type == "TAB" and not context.get("selected_resource"):
            frame.missing.append("tab_selection")
        if frame.action == "LIST" and frame.target_type in {"FILE", "FOLDER"} and not context.get("folder_ref"):
            frame.missing.append("folder")
        if frame.action == "PLAY" and frame.target_type == "AUDIO" and not context.get("media_ref") and not words & {"lofi", "playlist"}:
            frame.missing.append("audio_selection")
        if frame.action in {"PROVIDE", "SUMMARIZE"} and frame.target_type in {"ANSWER", "SUMMARY"} \
                and not context.get("current_question") and not context.get("selected_resource"):
            frame.missing.append("source_or_question")
        if frame.action is None and frame.speech_act == "COMMAND" and families:
            frame.missing.append("verb_sense")
        frame.confidence = 0.9 if frame.action and not frame.missing else 0.55 if frame.candidate_actions else 0.25
        if frame.speech_act != "COMMAND":
            frame.confidence = min(frame.confidence, 0.7)
        return frame
