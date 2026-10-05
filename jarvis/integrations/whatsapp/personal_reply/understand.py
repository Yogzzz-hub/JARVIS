"""Cheap understanding of an incoming message (EXTERNAL_MESSAGE_CONTENT).

The local decision engine (JDE) may classify it - conversation intent, whether it asks for a PC action,
whether context is needed - but its output is advisory only: an incoming message can never authorize a
JARVIS tool. "Send me your PDF" becomes a conversation-only reply that the owner must review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from jarvis.integrations.whatsapp.personal_reply import language as lang
from jarvis.integrations.whatsapp.personal_reply.tanglish_gloss import GLOSS

_ACTION_FAMILIES = {"FILE", "TRANSFER", "APP", "SYSTEM", "DESKTOP", "PACKAGE", "DEVELOPMENT", "BROWSER", "GOOGLE", "PHONE", "MEDIA"}
_PC_ACTION = re.compile(r"\b(?:send|share|forward|mail|upload|open|install|delete|remove|run|execute|download|screenshot|"
                        r"switch on|turn on|turn off|shut ?down|restart)\b[^.?!]{0,40}\b(?:your|the|my|that|this|a)?\s*"
                        r"(?:pdf|file|files|document|doc|photo|pic|pics|screenshot|resume|report|app|laptop|pc|computer|folder|"
                        r"system|password|otp|code)\b", re.I)
_PC_ACTION_TA = re.compile(r"\b(?:pdf|file|files|photo|photos|pic|pics|document|doc|resume|notes|screenshot|ss|password|otp|code|"
                           r"report|video)\s+(?:ah\s+|a\s+|ai\s+)?(?:anuppu|anupu|anuppi\s*vidu|send\s+pannu|kudu|share\s+pannu|"
                           r"forward\s+pannu)\b", re.I)
_GREETING = re.compile(r"^(?:hi+|hey+|hello|hlo|hai|good (?:morning|night|evening|afternoon)|gm|gn|vanakkam|dei|machan|machi|"
                       r"bro|enna da|enna di|hi da|hey da)\b", re.I)
_ACK = re.compile(r"^(?:ok(?:ay)?|k+|seri|sari|thanks?|thank you|ty|tq|cool|nice|super|semma|haa+|hmm+|done|got it|aama|amam|"
                  r"ok da|seri da|sari da|ok di|seri di|paravala|kandippa)(?:\s+(?:da|di|bro|machan|pa|ma))?[\s!.👍🙂😊🙏]*$", re.I)
_QUESTION = re.compile(r"\?\s*$|\b(?:what|when|where|why|how|who|which|can you|could you|will you|are you|did you|do you|"
                       r"enna|ena|epdi|eppadi|eppo|epo|enga|yen|yaaru|yaar|evlo|ethana|edhuku|ethuku)\b"
                       r"|\b\w+(?:ya|la|aa|ah|ngala|uma|ma)(?:\s+(?:da|di|dei|bro|machan|machi|pa|ma|anna|akka))?\s*[?!.]*$", re.I)
_TANGLISH_REQUEST = re.compile(r"\b(?:anuppu|anupu|sollu|sollunga|kudu|kudunga|vaa|vaanga|vanga|call pannu|paaru|pannu|"
                               r"pannunga|eduthutu vaa|vaangitu vaa)\b(?:\s+(?:da|di|dei|bro|machan|pa|ma|please|pls))?\s*[!.]*$", re.I)
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
    if any(x in GLOSS for x in content):
        return False  # a known Tanglish word: a real message
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
    conversation_mode: str = "INFORMATION"


@dataclass(frozen=True)
class Answerability:
    category: str
    gate: str
    reason: str
    proposition: str = ""
    who_asked: str = "CONTACT"
    who_must_answer: str = "OWNER"


_SENSITIVE_REQUEST = re.compile(
    r"(?:[₹$]\s*\d+|\b(?:pay|payment|money|cash|rupees?|rs\.?|upi|otp|password|pin|"
    r"bank|salary|loan|kaasu|panam)\b)", re.I)
_LOCATION = re.compile(r"\b(?:where\s+(?:are|r)\s+(?:you|u)|enga\s+(?:iruk\w*|por\w*)|location\s*(?:enna|where)?)\b", re.I)
_FOOD = re.compile(r"\b(?:saptiya|saaptiya|saaptiyaa|saptingala|saaptingala|"
                   r"(?:did\s+you|have\s+you)\s+(?:eat|eaten)|had\s+(?:food|lunch|dinner))\b", re.I)
_AVAILABILITY = re.compile(r"\b(?:free|available|busy|time\s+iruk\w*)\b", re.I)
_PERSONAL_WELLBEING = re.compile(r"\b(?:how\s+(?:are|r)\s+(?:you|u)|epdi\s+iruk\w*|eppadi\s+iruk\w*)\b", re.I)
_ATTENDANCE = re.compile(r"\b(?:varaya|varuviya|vareengala|varuveengala|coming|come|attend|join|go\w*)\b", re.I)
_FUTURE = re.compile(r"\b(?:tomorrow|naalaiku|naalaikku|next\s+week|later|tonight|evening|morning)\b", re.I)
_PROJECT_STATUS = re.compile(r"\b(?:backend|server|api|project|deploy\w*|bug|issue|fix\w*|"
                             r"status|progress|updates?)\b", re.I)
_MEETING = re.compile(r"\b(?:meeting|meet|call|appointment|gmeet)\b", re.I)
_REFERENCE = re.compile(r"\b(?:that|this|it|same|previous|last\s+time|remember|antha|athu|atha|"
                        r"andha|old\s+one)\b", re.I)
_EPISODIC = re.compile(r"\b(?:last\s+time|remember|previous|earlier|before|old\s+one|"
                       r"same\s+(?:issue|person|project|hotel|place)|that\s+(?:hotel|person|project|issue))\b", re.I)
_CONFIRM = re.compile(r"\b(?:yes|yeah|confirmed|correct|fixed|done|completed|seri|aama|"
                      r"scheduled|booked)\b", re.I)


def classify_answerability(text: str, thread: list[tuple[bool, str]] | None = None) -> Answerability:
    """Conservatively identify who must supply facts; never infer owner state from style examples."""
    raw = (text or "").strip()
    prior = thread or []
    lower = raw.casefold()
    owner_lines = [body for mine, body in prior if mine and body]
    und = understand(raw, use_jde=False)
    if _SENSITIVE_REQUEST.search(raw):
        return Answerability("SENSITIVE", "REQUIRES_OWNER", "sensitive request needs owner review", "sensitive_request")
    if und.intent in ("EMPTY", "ACK"):
        return Answerability("NO_REPLY_NEEDED", "NOT_ANSWERABLE", "acknowledgement does not require a factual answer")
    if _LOCATION.search(raw):
        return Answerability("PERSONAL_STATE_REQUIRED", "REQUIRES_OWNER", "current owner location is unavailable", "owner_location")
    if _FOOD.search(raw):
        return Answerability("PERSONAL_STATE_REQUIRED", "REQUIRES_OWNER", "current owner meal state is unavailable", "owner_meal_state")
    if _AVAILABILITY.search(raw) and (und.intent == "QUESTION" or "?" in raw):
        return Answerability("PERSONAL_STATE_REQUIRED", "REQUIRES_OWNER", "current owner availability is unavailable", "owner_availability")
    if _PERSONAL_WELLBEING.search(raw) and (und.intent == "QUESTION" or "?" in raw):
        return Answerability("PERSONAL_STATE_REQUIRED", "REQUIRES_OWNER", "current owner wellbeing is unavailable", "owner_wellbeing")
    if _ATTENDANCE.search(raw) and (_FUTURE.search(raw) or und.intent == "QUESTION" or "?" in raw):
        return Answerability("OWNER_DECISION_REQUIRED", "REQUIRES_OWNER", "owner has not supplied a current attendance decision", "owner_attendance")
    if _MEETING.search(raw) and (und.intent == "QUESTION" or "?" in raw):
        times = set(re.findall(r"\b\d{1,2}(?::\d{2})?\b", raw))
        confirmed = any(_MEETING.search(body) and _CONFIRM.search(body)
                        and (not times or times & set(re.findall(r"\b\d{1,2}(?::\d{2})?\b", body)))
                        for body in owner_lines)
        if confirmed:
            return Answerability("CONVERSATION_KNOWN", "ANSWERABLE", "same-thread owner confirmation", "meeting_confirmation")
        return Answerability("OWNER_DECISION_REQUIRED", "REQUIRES_OWNER", "meeting confirmation is not in the owner thread", "meeting_confirmation")
    if _PROJECT_STATUS.search(raw) and (und.intent == "QUESTION" or "?" in raw or "update" in lower):
        confirmed = any(_CONFIRM.search(body) and _PROJECT_STATUS.search(body) for body in owner_lines)
        if confirmed:
            return Answerability("CONVERSATION_KNOWN", "ANSWERABLE", "same-thread owner project status", "project_status")
        if re.search(r"\b(?:status|progress|updates?)\b", raw, re.I) and not re.search(
                r"\b(?:backend|server|api|project|deploy\w*|bug|issue|fix\w*)\b", raw, re.I):
            return Answerability("PERSONAL_STATE_REQUIRED", "REQUIRES_OWNER", "owner's current progress is unavailable", "project_status")
        return Answerability("JARVIS_KNOWN", "REQUIRES_TOOL", "verified project status is not supplied", "project_status")
    if _REFERENCE.search(raw) and len(raw.split()) <= 7 and not prior:
        return Answerability("AMBIGUOUS", "REQUIRES_CLARIFICATION", "reference has no same-thread referent", "reference")
    if und.intent == "QUESTION":
        return Answerability("AMBIGUOUS", "REQUIRES_CLARIFICATION",
                             "no verified answer evidence identified for this question", "unknown_question")
    return Answerability("STYLE_ONLY", "ANSWERABLE", "no private factual state identified")


def memory_need(text: str, category: str = "") -> str:
    """Choose whether the existing contact example index is useful for this turn."""
    raw = (text or "").strip()
    if category == "NO_REPLY_NEEDED" or not raw or len(raw.split()) <= 2 and not _EPISODIC.search(raw):
        return "MEMORY_NOT_NEEDED"
    if _EPISODIC.search(raw):
        return "EPISODIC_REFERENCE_REQUIRED"
    return "STYLE_EXAMPLES_HELPFUL"


def understand(text: str, use_jde: bool = True) -> Understanding:
    t = (text or "").strip()
    if not t:
        return Understanding("EMPTY", False, lang.UNKNOWN, confidence=0.0)
    mix = lang.detect(t)
    if is_unclear(t):
        return Understanding("UNCLEAR", False, mix.label, confidence=0.2)
    if _ACK.match(t):
        intent = "ACK"
    elif (_GREETING.match(t) and len(t.split()) <= 4 and "?" not in t
          and not _QUESTION.search(_GREETING.sub("", t, count=1).strip())):  # "dei tomorrow varuviya?" is a question
        intent = "GREETING"
    elif _QUESTION.search(t):
        intent = "QUESTION"
    elif re.match(r"^(?:please|pls|plz|can you|send|call|come|bring|tell|share)\b", t, re.I) or _TANGLISH_REQUEST.search(t):
        intent = "REQUEST"
    else:
        intent = "STATEMENT"
    pc = bool(_PC_ACTION.search(t) or _PC_ACTION_TA.search(t))
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
    lower = t.casefold()
    if re.search(r"\b(?:urgent|emergency|asap|hospital|accident|help me)\b", lower):
        mode = "URGENT"
    elif re.search(r"\b(?:sorry|apolog|mannich|forgive)\w*\b", lower):
        mode = "APOLOGETIC"
    elif re.search(r"\b(?:backend|database|server|deploy|api|bug|code)\b", lower):
        mode = "TECHNICAL"
    elif re.search(r"\b(?:haha|hehe|lol|joke|funny|kidding)\b", lower):
        mode = "JOKING"
    elif intent == "QUESTION":
        mode = "QUESTION"
    elif intent == "REQUEST":
        mode = "REQUEST"
    elif intent == "ACK":
        mode = "NO_REPLY_NEEDED"
    elif intent == "GREETING":
        mode = "CASUAL"
    else:
        mode = "INFORMATION"
    return Understanding(intent, pc, mix.label, route, is_action, confidence, mode)
