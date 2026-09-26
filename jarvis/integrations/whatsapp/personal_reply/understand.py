"""Cheap understanding of an incoming message (EXTERNAL_MESSAGE_CONTENT).

The local decision engine (JDE) may classify it - conversation intent, whether it asks for a PC action,
whether context is needed - but its output is advisory only: an incoming message can never authorize a
JARVIS tool. "Send me your PDF" becomes a conversation-only reply that the owner must review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from jarvis.integrations.whatsapp.personal_reply import language as lang

_ACTION_FAMILIES = {"FILE", "TRANSFER", "APP", "SYSTEM", "DESKTOP", "PACKAGE", "DEVELOPMENT", "BROWSER", "GOOGLE", "PHONE", "MEDIA"}
_PC_ACTION = re.compile(r"\b(?:send|share|forward|mail|upload|open|install|delete|remove|run|execute|download|screenshot|"
                        r"switch on|turn on|turn off|shut ?down|restart)\b[^.?!]{0,40}\b(?:your|the|my|that|this|a)?\s*"
                        r"(?:pdf|file|files|document|doc|photo|pic|pics|screenshot|resume|report|app|laptop|pc|computer|folder|"
                        r"system|password|otp|code)\b", re.I)
_GREETING = re.compile(r"^(?:hi+|hey+|hello|hlo|good (?:morning|night|evening|afternoon)|gm|gn|vanakkam|dei|machan|bro)\b", re.I)
_ACK = re.compile(r"^(?:ok(?:ay)?|k+|seri|sari|thanks?|thank you|ty|cool|nice|super|haa+|hmm+|done|got it)[\s!.👍🙂😊]*$", re.I)
_QUESTION = re.compile(r"\?\s*$|\b(?:what|when|where|why|how|who|which|can you|could you|will you|are you|did you|do you|"
                       r"enna|epdi|eppadi|eppo|enga|yen|yaaru)\b|\b\w+(?:ya|la|aa)\s*[?!.]*$", re.I)
_FILLER = re.compile(r"^(?:h+m+|m+h*m+|k+|ok+|okay|oh+|ah+|uh+|ha(?:ha)+|lol+|hm+)$")
_TOKENS = re.compile(r"[a-z\u0B80-\u0BFF']+")


def _wordlike(tok: str) -> bool:
    """Could this unknown token be a real (possibly Tanglish) word, rather than keyboard mash?"""
    if not tok.isascii():
        return True  # Tamil script
    return (bool(re.search(r"[aeiou]", tok)) and not re.search(r"[^aeiouy']{4,}", tok)
            and not re.search(r"q(?!u)", tok) and not re.search(r"(.)\1\1", tok))


def is_unclear(text: str) -> bool:
    """Nothing a reply could safely answer: emoji/punctuation only, "hmm?" / "k?", a lone letter, keyboard mash."""
    t = (text or "").strip().lower()
    toks = _TOKENS.findall(t)
    if not toks:
        return True
    content = [x for x in toks if not _FILLER.match(x)]
    if not content:
        return "?" in t
    if len("".join(content)) <= 1:
        return True
    return all(lang.classify_token(x) == "" for x in content) and any(not _wordlike(x) for x in content)


@dataclass
class Understanding:
    intent: str                 # QUESTION / REQUEST / GREETING / ACK / STATEMENT / UNCLEAR / EMPTY
    requests_pc_action: bool
    language: str
    jde_route: str = ""
    jde_is_action: float = 0.0
    confidence: float = 0.7


def understand(text: str, use_jde: bool = True) -> Understanding:
    t = (text or "").strip()
    if not t:
        return Understanding("EMPTY", False, lang.UNKNOWN, confidence=0.0)
    mix = lang.detect(t)
    if is_unclear(t):
        return Understanding("UNCLEAR", False, mix.label, confidence=0.2)
    if _ACK.match(t):
        intent = "ACK"
    elif _GREETING.match(t) and len(t.split()) <= 4:
        intent = "GREETING"
    elif _QUESTION.search(t):
        intent = "QUESTION"
    elif re.match(r"^(?:please|pls|plz|can you|send|call|come|bring|tell|share)\b", t, re.I):
        intent = "REQUEST"
    else:
        intent = "STATEMENT"
    pc = bool(_PC_ACTION.search(t))
    route, is_action = "", 0.0
    if use_jde:
        try:
            from jarvis.decision.runtime import get_runtime
            from jarvis.decision.schemas import DecisionState
            result = get_runtime().decide(DecisionState(text=t, channel="whatsapp_external"))
            if result is not None:
                route = result.route.value
                is_action = result.p("is_action")
                if route in _ACTION_FAMILIES and is_action >= 0.7 and re.search(r"\b(?:send|share|open|install|delete|run)\b", t, re.I):
                    pc = True
        except Exception:
            pass
    confidence = 0.8 if mix.label != lang.UNKNOWN else 0.55
    return Understanding(intent, pc, mix.label, route, is_action, confidence)
