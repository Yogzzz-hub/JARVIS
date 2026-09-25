"""Follow-Up Intent Detector for JARVIS EDGE.

Sub-millisecond deterministic classification of follow-up conversational utterances:
- PRONOUN_REFERENCE ("open it", "install it", "send that", "what's it about")
- ORDINAL_REFERENCE ("the second one", "open the 1st", "item number 3")
- ELLIPSIS ("and Edge", "and Documents")
- REFINEMENT ("only PDFs", "from this week", "in Downloads")
- SLOT_OVERRIDE ("actually 40", "no, 60%")
- CORRECTION ("actually the third one", "no, Arun Kumar")
- COMPARISON ("compare the first one with the third one")
- ACTION_ON_TOPIC ("install it", "open it", "where is it installed")
- ACTION_AFTER_FAILURE ("install it" after app missing, "try Downloads" after file missing)
- CONFIRMATION ("yes", "sure", "do it", "go ahead")
- CANCELLATION ("no", "cancel", "abort", "stop")
- RETRY ("try again", "retry", "try that again")
- WHY_QUERY ("why?", "why did it fail?", "what failed?")
- TOPIC_SWITCH ("go back to Ollama", "about Docker", "forget that")
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from jarvis.core.context.models import (
    FollowupClassification,
    FollowupType,
    WorkingContext,
)

ORDINAL_WORDS = {
    "first": 0, "1st": 0, "one": 0,
    "second": 1, "2nd": 1, "two": 1,
    "third": 2, "3rd": 2, "three": 2,
    "fourth": 3, "4th": 3, "four": 3,
    "fifth": 4, "5th": 4, "five": 4,
    "last": -1, "final": -1,
}

CONFIRMATION_WORDS = frozenset({
    "yes", "yeah", "yep", "sure", "do it", "go ahead", "proceed",
    "confirm", "ok", "okay", "yup", "continue", "please do", "approved",
})

CANCELLATION_WORDS = frozenset({
    "no", "cancel", "stop", "abort", "don't", "dont", "never mind",
    "nevermind", "deny", "rejected", "leave it",
})

RETRY_PATTERNS = (
    r"^(?:try\s+again|retry|try\s+that\s+again|do\s+that\s+again|try\s+once\s+more|try\s+only\s+that\s+again)$",
)

WHY_PATTERNS = (
    r"^(?:why\??|why\s+did\s+it\s+fail\??|why\s+failed\??|what\s+failed\??|why\s+couldn'?t\s+you\s+find\s+it\??|what\s+was\s+the\s+error\??)$",
)

TOPIC_SWITCH_PATTERNS = (
    r"^(?:go\s+back\s+to|back\s+to|return\s+to)\s+([a-zA-Z0-9_\-\.\s]+)$",
    r"^(?:anyway,?\s+about|now\s+about|what\s+about|forget\s+that,?\s*(?:show|about)?)\s+([a-zA-Z0-9_\-\.\s]+)$",
)


class FollowupDetector:
    """Fast, deterministic classifier for conversational follow-ups."""

    @staticmethod
    def classify(utterance: str, context: Optional[WorkingContext] = None) -> FollowupClassification:
        text = utterance.strip()
        lowered = text.casefold().rstrip(".!,?")

        # 1. RETRY
        for pat in RETRY_PATTERNS:
            if re.match(pat, lowered):
                return FollowupClassification(
                    followup_type=FollowupType.RETRY,
                    confidence=1.0,
                )

        # 2. WHY / EXPLANATION
        for pat in WHY_PATTERNS:
            if re.match(pat, lowered):
                return FollowupClassification(
                    followup_type=FollowupType.WHY_QUERY,
                    confidence=1.0,
                )

        # 3. CONFIRMATION / CANCELLATION (Against pending state)
        if lowered in CONFIRMATION_WORDS:
            return FollowupClassification(
                followup_type=FollowupType.CONFIRMATION,
                confidence=1.0,
            )
        if lowered in CANCELLATION_WORDS:
            return FollowupClassification(
                followup_type=FollowupType.CANCELLATION,
                confidence=1.0,
            )

        # 4. TOPIC SWITCH ("go back to Ollama", "back to Docker", "forget that, show my emails")
        for pat in TOPIC_SWITCH_PATTERNS:
            m_sw = re.match(pat, lowered)
            if m_sw:
                target_topic = m_sw.group(1).strip()
                return FollowupClassification(
                    followup_type=FollowupType.TOPIC_SWITCH,
                    confidence=0.95,
                    target_hint=target_topic,
                )

        # 5. USER CORRECTION / SLOT OVERRIDE ("actually 40", "no, third", "no, Arun Kumar")
        m_act = re.match(r"^(?:actually|no,?|wait,?)\s+(?:just\s+)?(.+)$", lowered)
        if m_act:
            override_val = m_act.group(1).strip()
            # Check if it's an ordinal correction ("no, third", "actually the second one")
            for ord_w, idx in ORDINAL_WORDS.items():
                if ord_w in override_val:
                    return FollowupClassification(
                        followup_type=FollowupType.CORRECTION,
                        confidence=0.95,
                        extracted_ordinals=[idx],
                        target_hint=override_val,
                    )
            return FollowupClassification(
                followup_type=FollowupType.SLOT_OVERRIDE,
                confidence=0.90,
                target_hint=override_val,
            )

        # 6. COMPARISON ("compare the first one with the second one", "compare it with the third")
        if "compare" in lowered and any(k in lowered for k in ("with", "and")):
            ords = []
            for ord_w, idx in ORDINAL_WORDS.items():
                if re.search(rf"\b{ord_w}\b", lowered):
                    ords.append(idx)
            return FollowupClassification(
                followup_type=FollowupType.COMPARISON,
                confidence=0.95,
                extracted_ordinals=ords,
            )

        # 7. ORDINAL REFERENCE ("the second one", "open the 1st", "item number 2", "third file")
        for ord_w, idx in ORDINAL_WORDS.items():
            if (
                f"the {ord_w}" in lowered
                or f"{ord_w} one" in lowered
                or f"{ord_w} file" in lowered
                or f"{ord_w} result" in lowered
                or f"{ord_w} document" in lowered
                or f"{ord_w} app" in lowered
                or f"{ord_w} option" in lowered
                or re.match(rf"^(?:the\s+)?{ord_w}$", lowered)
            ):
                return FollowupClassification(
                    followup_type=FollowupType.ORDINAL_REFERENCE,
                    confidence=0.95,
                    extracted_ordinals=[idx],
                )

        m_num = re.search(r"\b(?:item\s+number|number|result)\s+(\d+)\b", lowered)
        if m_num:
            idx = int(m_num.group(1)) - 1
            return FollowupClassification(
                followup_type=FollowupType.ORDINAL_REFERENCE,
                confidence=0.95,
                extracted_ordinals=[idx],
            )

        # 8. ELLIPSIS / CONTEXTUAL REFINEMENT ("and Edge", "in Downloads", "only PDFs", "from this week", "try Downloads")
        if re.match(r"^(?:and|also|plus)\s+([a-zA-Z0-9_\-\.\s]+)$", lowered):
            return FollowupClassification(
                followup_type=FollowupType.ELLIPSIS,
                confidence=0.90,
                target_hint=re.sub(r"^(?:and|also|plus)\s+", "", lowered).strip(),
            )

        if re.match(r"^(?:only|just|filter\s+by)\s+([a-zA-Z0-9_\-\.\s]+)$", lowered) or re.match(r"^(?:in|from|under)\s+([a-zA-Z0-9_\\/\-\.\s]+)$", lowered):
            hint_val = re.sub(r"^(?:only|just|filter\s+by|in|from|under)\s+", "", lowered).strip()
            return FollowupClassification(
                followup_type=FollowupType.REFINEMENT,
                confidence=0.90,
                target_hint=hint_val,
            )

        if re.match(r"^(?:try|search\s+in|look\s+in)\s+([a-zA-Z0-9_\-\.\s]+)$", lowered):
            # Follow-up after search failure or folder override
            target_folder = re.sub(r"^(?:try|search\s+in|look\s+in)\s+", "", lowered).strip()
            return FollowupClassification(
                followup_type=FollowupType.ACTION_AFTER_FAILURE,
                confidence=0.92,
                target_hint=target_folder,
            )

        # 9. ACTION ON TOPIC / ACTION AFTER FAILURE
        # e.g. "install it", "download it", "open it"
        m_action_it = re.match(r"^(?:please\s+)?(install|download|open|run|launch|start|close|check\s+its\s+version|where\s+is\s+it(?:\s+installed)?)\s+(?:it|that|this)(?:\s+(?:app|software|package|file))?$", lowered)
        if m_action_it:
            verb = m_action_it.group(1).strip()
            # If we had a recent failure on opening an app (e.g. VLC), this is ACTION_AFTER_FAILURE
            if context and context.recent_failures and verb in ("install", "download"):
                return FollowupClassification(
                    followup_type=FollowupType.ACTION_AFTER_FAILURE,
                    confidence=0.95,
                    extracted_pronouns=["it"],
                    target_hint=verb,
                )
            return FollowupClassification(
                followup_type=FollowupType.ACTION_ON_TOPIC,
                confidence=0.95,
                extracted_pronouns=["it"],
                target_hint=verb,
            )

        # 10. TOPIC FOLLOW-UP QUESTIONS ("What is Ollama?" -> "Why would I use it?", "Does it need internet?", "Can it run Qwen?")
        if any(lowered.startswith(q) for q in ("why would i use it", "does it need", "can it run", "is it free", "how much ram", "what can it do", "can it ")):
            return FollowupClassification(
                followup_type=FollowupType.TOPIC_FOLLOWUP,
                confidence=0.90,
                extracted_pronouns=["it"],
            )

        # 11. GENERAL PRONOUN REFERENCE ("what's it about", "open its folder", "send it to my phone", "open it again")
        pronouns_found = []
        for p in ("that one", "this one", "its folder", "it", "this", "that", "them"):
            if re.search(rf"\b{p}\b", lowered):
                pronouns_found.append(p)

        if pronouns_found:
            return FollowupClassification(
                followup_type=FollowupType.PRONOUN_REFERENCE,
                confidence=0.88,
                extracted_pronouns=pronouns_found,
            )

        return FollowupClassification(
            followup_type=FollowupType.STANDALONE,
            confidence=1.0,
        )

    detect = classify
