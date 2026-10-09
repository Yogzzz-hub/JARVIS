"""Checks a reply candidate before it may be sent automatically.

Scores: RELEVANCE, STYLE_MATCH, LANGUAGE_MATCH, CONTEXT_CONSISTENCY, HALLUCINATION_RISK,
SENSITIVE_ACTION_RISK. Anything below threshold -> NEEDS_USER_REVIEW (never a guess).
Sensitive / consequential topics always need the owner, even in auto mode.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from jarvis.integrations.whatsapp.personal_reply import language as lang
from jarvis.integrations.whatsapp.personal_reply.models import ContactStyleProfile, QualityReport, ReplyCandidate
from jarvis.integrations.whatsapp.personal_reply.understand import Answerability, classify_answerability

SENSITIVE_PATTERNS: dict[str, re.Pattern[str]] = {
    "money": re.compile(r"\b(?:pay|paid|payment|money|transfer|send money|amount|rs\.?|rupees?|inr|upi|gpay|g-pay|phonepe|paytm|"
                        r"bank|account (?:no|number)|ifsc|loan|emi|invoice|salary|dues|borrow|lend|panam|kaasu|kadan|refund|"
                        r"price|fees?|cash)\b|₹|\$\s?\d", re.I),
    "credentials": re.compile(r"\b(?:otp|password|passcode|pin|cvv|login|log in|verification code|security code|aadhaa?r|"
                              r"pan (?:card|no)|card (?:no|number|details)|ssn|2fa|credentials?)\b", re.I),
    "files": re.compile(r"\b(?:send|share|forward|attach|mail|upload)\b[^.?!]{0,30}\b(?:pdfs?|files?|documents?|docs?|photos?|"
                        r"pics?|pictures?|images?|screenshots?|resumes?|reports?|attachments?|videos?|scans?|cop(?:y|ies)|"
                        r"recordings?|voice notes?)\b", re.I),
    "private_info": re.compile(r"\b(?:home address|address|location|live location|where do you live|phone number|number kudu|"
                               r"contact number|date of birth|dob|medical|salary)\b", re.I),
    "commitment": re.compile(r"\b(?:promise|guarantee|commit|confirm(?:ed)?|sign(?:ed)?|agree(?:d)?|it'?s a deal|"
                             r"book(?:ed|ing)? (?:a |the )?(?:ticket|table|room|cab|slot|appointment)|reserve|"
                             r"deadline|contract|i will pay|i'?ll pay|i'?ll transfer|final answer)\b", re.I),
    "conflict": re.compile(r"\b(?:angry|fight|hate|breakup|break up|divorce|upset|disappointed|cheat(?:ed|ing)?|liar|lied|"
                           r"insult|shut up|how dare|never talk|blocked you|sorry for what)\b", re.I),
    "legal_official": re.compile(r"\b(?:lawyer|advocate|court|police|legal|fir|complaint|legal notice|notice period|visa|passport|government|tax|"
                                 r"hr (?:team|department|manager)|resignation|resign|offer letter|termination|interview result|appraisal)\b", re.I),
    "emergency": re.compile(r"\b(?:hospital|accident|emergency|urgent|died|death|passed away|ambulance|icu|help me)\b", re.I),
    "instructions_to_assistant": re.compile(r"\b(?:ignore (?:all |your |previous )?(?:instructions|rules)|system prompt|"
                                            r"you are (?:an? )?(?:ai|bot|assistant)|jarvis|run (?:this|the) command|"
                                            r"execute|powershell|delete (?:the |all )?files?|open (?:the )?app)\b", re.I),
}

_AI_PHRASES = re.compile(r"\b(?:certainly|i'?d be (?:happy|glad) to help|here is|here's (?:a|the|your)|let me know if you need|"
                         r"as an ai|language model|i'?m jarvis|i am jarvis|feel free to|hope this helps|i understand your concern|"
                         r"absolutely!|great question)\b", re.I)
_BARE_ACK = re.compile(r"^(?:ok(?:ay)?|k+|seri|sari|haa+|ha|yes|yeah|yep|no|illa|sure|done|hmm+|fine|cool|👍)[\s!.👍🙂😊]*$", re.I)
_FACTS = re.compile(r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm)\b|\b\d{3,}\b|\b\d+(?:\.\d+)?\s?(?:k|rs|lakh|cr)\b|https?://\S+|"
                    r"\b\d{1,2}(?:st|nd|rd|th)\b|₹\s?\d+", re.I)


PARROT_SIMILARITY = 0.3


@dataclass
class Thresholds:
    relevance: float = 0.6
    style: float = 0.5
    language: float = 0.5
    consistency: float = 0.5
    max_hallucination: float = 0.5
    max_sensitive: float = 0.3


def sensitive_topics(text: str) -> list[str]:
    return [name for name, pat in SENSITIVE_PATTERNS.items() if pat.search(text or "")]


def has_ai_phrases(text: str) -> bool:
    return bool(_AI_PHRASES.search(text or ""))


def facts(text: str) -> set[str]:
    return {m.group(0).lower().replace(" ", "") for m in _FACTS.finditer(text or "")}


def _words(text: str) -> list[str]:
    return re.findall(r"[\w']+", (text or "").lower())


_QUESTION_STOP = {"are", "is", "do", "did", "you", "your", "the", "a", "an", "what", "when",
                  "where", "why", "how", "can", "could", "will", "would", "me", "i", "it",
                  "this", "that", "enna", "epdi", "eppo", "ah", "aa", "bro", "da", "di"}
_DEFER = re.compile(r"\b(?:wait|check(?:ing)?|not sure|don'?t know|therla|purila|"
                    r"paathutu|pathutu|solren|solluren)\b", re.I)
_YES_NO = re.compile(r"^(?:yes|no|yeah|nope|aama|haa|illa|correct|right|confirmed|"
                     r"sure|varen|varan|varuven|varuvaen)\b", re.I)
_ASK_BACK = re.compile(r"\b(?:tell|send|give|provide|share|update|sollu|solu|kudu|anuppu)\b", re.I)


def validate_semantics(candidate: ReplyCandidate, incoming: str, thread_text: str,
                       answerability: Answerability | None = None) -> tuple[bool, str, Answerability]:
    """Check answer direction and evidence without using model confidence or style."""
    thread = [(line.startswith("You:"), line.split(":", 1)[1].strip())
              for line in thread_text.splitlines() if line.startswith(("You:", "Them:"))]
    state = answerability or classify_answerability(incoming, thread)
    reply = (candidate.text or "").strip()
    if state.gate != "ANSWERABLE":
        return False, f"{state.category}: {state.reason}", state
    if not reply:
        return False, "empty reply", state
    asked = "?" in incoming or bool(re.search(r"\b(?:what|when|where|why|how|who|which|enna|epdi|eppo|enga|yen)\b", incoming, re.I))
    if not asked:
        return True, "", state
    if _BARE_ACK.fullmatch(reply):
        return False, "acknowledgement does not answer the contact's question", state
    if re.match(r"\s*(?:did|has|have|was|were)\b", incoming, re.I) and not any(mine for mine, _ in thread):
        return False, "past-event answer lacks owner or verified same-thread evidence", state
    if state.proposition in ("project_status", "meeting_confirmation"):
        if _ASK_BACK.search(reply) and "?" in reply:
            return False, "reply asks the contact to provide the answer they requested", state
        if state.proposition == "project_status" and _ASK_BACK.search(reply) and not _DEFER.search(reply):
            return False, "reply reverses the requested update direction", state
    words = _words(reply)
    if len(words) <= 1 and not _YES_NO.search(reply) and not _DEFER.search(reply):
        return False, "short reply supplies no answer or valid clarification", state
    if state.category == "CONVERSATION_KNOWN":
        owner_text = " ".join(text for mine, text in thread if mine)
        unsupported = facts(reply) - (facts(incoming) | facts(owner_text))
        if unsupported:
            return False, "reply adds a fact absent from the question and confirmed owner thread", state
        if state.proposition == "meeting_confirmation":
            owner_times = set(re.findall(r"\b\d{1,2}(?::\d{2})?\b", owner_text))
            reply_times = set(re.findall(r"\b\d{1,2}(?::\d{2})?\b", reply))
            if reply_times - owner_times:
                return False, "reply changes the owner-confirmed meeting time", state
        if _YES_NO.search(reply) or _DEFER.search(reply):
            return True, "", state
        owner_words = set(_words(owner_text))
        if not owner_words.intersection(words):
            return False, "reply does not use the confirmed same-thread evidence", state
    elif not (_DEFER.search(reply) or _YES_NO.search(reply)):
        topic = set(_words(incoming)) - _QUESTION_STOP
        if topic and not topic.intersection(words):
            return False, "reply does not address the question's subject", state
    return True, "", state


def evaluate(candidate: ReplyCandidate, incoming: str, thread_text: str, example_text: str, profile: ContactStyleProfile,
             target_language: str, owner_uses_ai_phrases: bool = False, thresholds: Thresholds | None = None,
             copied_example_similarity: float | None = None,
             answerability: Answerability | None = None) -> QualityReport:
    th = thresholds or Thresholds()
    reply = (candidate.text or "").strip()
    reasons: list[str] = []

    # SEMANTIC / WHAT is independent of the generator's self-confidence.
    semantic_pass, semantic_reason, state = validate_semantics(candidate, incoming, thread_text, answerability)
    relevance = 1.0 if semantic_pass else 0.0
    in_q = "?" in incoming or bool(re.search(r"\b(?:enna|epdi|eppo|enga|yen|what|when|where|why|how|who|which)\b", incoming, re.I))
    wh_q = bool(re.search(r"\b(?:what|when|where|why|how|who|which|enna|epdi|eppo|enga|yen|yaaru)\b", incoming, re.I))
    if wh_q and _BARE_ACK.match(reply):
        relevance -= 0.3  # an open question answered with just "ok"
    if copied_example_similarity is not None and copied_example_similarity < PARROT_SIMILARITY and len(_words(reply)) > 2:
        semantic_pass = False
        semantic_reason = "copied an owner reply from an unrelated situation"
        relevance = 0.0
    relevance = max(0.0, min(1.0, relevance))

    # STYLE_MATCH
    style = 1.0
    n = len(_words(reply))
    lo, hi = profile.length_band()
    if n > hi:
        overshoot = (n - hi) / max(hi, 1)
        allowance = 0.5 if in_q else 0.0  # a real question may need a slightly longer answer
        style -= min(0.6, max(0.0, overshoot - allowance) * 0.5)
    emo = len(lang.emojis(reply))
    if profile.emoji_frequency < 0.1 and emo >= 2:
        style -= 0.25
    if profile.emoji_frequency >= 0.8 and emo == 0 and n > 2:
        style -= 0.05
    if has_ai_phrases(reply) and not owner_uses_ai_phrases:
        style -= 0.5
    if profile.effective_formality() in ("VERY_CASUAL", "CASUAL") and re.search(r"\b(?:dear|regards|sincerely|kindly)\b", reply, re.I):
        style -= 0.2
    if profile.effective_formality() == "PROFESSIONAL" and re.search(r"\b(?:lol|lmao|dei|machan|bro)\b", reply, re.I):
        style -= 0.3
    style = max(0.0, style)

    # LANGUAGE_MATCH
    detected = lang.detect(reply).label
    if detected == lang.UNKNOWN or n <= 1:
        language = 0.85
    elif target_language == "ENGLISH":
        # Tanglish in an English turn is only acceptable where the owner really mixes with this person
        mixes = profile.effective_tanglish_ratio()
        language = 1.0 if detected == lang.ENGLISH else (0.8 if mixes >= 0.2 else 0.55) if detected == lang.MIXED \
            else 0.7 if mixes >= 0.3 else 0.25
    elif target_language == "TANGLISH":
        language = 1.0 if detected in (lang.TANGLISH, lang.MIXED) else 0.4
    else:  # MIXED
        language = 1.0 if detected in (lang.MIXED, lang.TANGLISH, lang.ENGLISH) else 0.5

    # CONTEXT_CONSISTENCY
    consistency = 1.0
    thread_lines = [ln.strip().lower() for ln in thread_text.splitlines() if ln.strip()]
    if reply and any(ln.endswith(reply.lower()) for ln in thread_lines[-6:] if ln.startswith("you:")):
        consistency -= 0.6  # repeating what the owner just said
    if re.search(r"\b(?:as i said|like i told you|i already sent)\b", reply, re.I) and "you:" not in thread_text.lower():
        consistency -= 0.4

    # Historical examples are style evidence, never authority for current facts.
    grounded = facts(incoming) | facts(thread_text)
    new_facts = facts(reply) - grounded
    hallucination = min(1.0, 0.45 * len(new_facts))
    if new_facts and in_q:
        semantic_pass = False
        semantic_reason = "reply introduces a factual value absent from the current thread"
        relevance = 0.0

    # SENSITIVE_ACTION_RISK
    topics = sorted(set(sensitive_topics(incoming)) | set(sensitive_topics(reply)))
    sensitive = 1.0 if topics else 0.0

    if relevance < th.relevance:
        reasons.append(semantic_reason or "low independent semantic relevance")
    if style < th.style:
        reasons.append("does not match your usual style")
    if language < th.language:
        reasons.append("language mix does not fit")
    if consistency < th.consistency:
        reasons.append("inconsistent with the recent conversation")
    if hallucination > th.max_hallucination:
        reasons.append(f"adds facts not in the chat: {', '.join(sorted(new_facts))[:60]}")
    if sensitive > th.max_sensitive:
        reasons.append(f"sensitive topic ({', '.join(topics)}) needs your approval")
    return QualityReport(relevance=round(relevance, 3), style_match=round(style, 3), language_match=round(language, 3),
                         context_consistency=round(consistency, 3), hallucination_risk=round(hallucination, 3),
                         sensitive_action_risk=sensitive, reasons=reasons, sensitive_topics=topics,
                         semantic_pass=semantic_pass, semantic_reason=semantic_reason,
                         answerability_category=state.category, answerability_gate=state.gate)
