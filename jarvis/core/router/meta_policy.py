"""Meta-Instruction and Response-Policy Detection for JARVIS EDGE Router.

Classifies meta-instructions that configure reporting/execution behavior (e.g. verification
timing, partial success reporting, verbosity, failure detail, retry rules) without executing
tools or triggering command negation.
"""

from __future__ import annotations

import re
from typing import Optional
from jarvis.core.router.models import (
    ComplexityLevel,
    RouteDecision,
    RouteLane,
    RouteSource,
)


def match_meta_policy(text: str, request_id: str) -> Optional[RouteDecision]:
    """Detects and extracts meta/response-policy instructions.

    Returns a RouteDecision with lane=RouteLane.CONTROL and intent='response_policy',
    or None if the text is not a meta-instruction.
    """
    if not text:
        return None

    cleaned = text.strip()
    lowered = cleaned.casefold()

    # Normalize leading conversational fillers or prefixes
    lowered = re.sub(
        r"^(?:please\s+|remember\s*,?\s*|from\s+now\s+on\s*,?\s*|in\s+future\s*,?\s*|make\s+sure\s+(?:that\s+)?|hey\s+jarvis\s*,?\s*|jarvis\s*,?\s*)+",
        "",
        lowered,
    ).strip()

    # 1. Verification Before Completion Rule
    # e.g. "don't say done until all required verification finishes", "never say done before verifier completes",
    # "do not announce success without verifying"
    is_verif_rule = bool(
        re.search(r"\b(?:don'?t|do\s+not|never)\s+(?:say|announce|call|mark|report)\s+(?:['\"]?done['\"]?|['\"]?completed['\"]?|['\"]?success['\"]?)\b", lowered)
        and re.search(r"\b(?:until|before|without)\b", lowered)
        and re.search(r"\b(?:verif\w+|finish\w*|pass\w*|complet\w*)\b", lowered)
    ) or bool(
        re.search(r"\b(?:only\s+say|only\s+report|only\s+announce)\s+(?:['\"]?done['\"]?|['\"]?completed['\"]?|['\"]?success['\"]?)\b", lowered)
        and re.search(r"\b(?:when|after|once)\b", lowered)
        and re.search(r"\b(?:verif\w+)\b", lowered)
    )

    if is_verif_rule:
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.CONTROL,
            intent="response_policy",
            slots={
                "policy_type": "verification_rule",
                "require_verification_before_done": True,
                "allow_premature_done": False,
            },
            confidence=1.0,
            source=RouteSource.EXACT,
            complexity=ComplexityLevel.SIMPLE,
            normalized_text=cleaned,
            clarification="Understood. I will not announce completion until all required verification has finished.",
            reason_code="RESPONSE_POLICY",
        )

    # 2. Partial Success / Failure Classification Rule
    # e.g. "If only two actions succeed, don't call the whole task a failure."
    # e.g. "if some steps work, call it partial success"
    # e.g. "don't call the whole task a failure when some steps succeed"
    # e.g. "treat partial completion as partial success"
    is_partial_success_rule = bool(
        re.search(r"\b(?:if|when)\b.*\b(?:succeed\w*|work\w*|pass\w*)\b.*\b(?:don'?t|do\s+not|never)\s+(?:call|mark|label|treat|consider)\b.*\b(?:whole|entire|all|task)\b.*\b(?:failure|fail\w*)\b", lowered)
    ) or bool(
        re.search(r"\b(?:don'?t|do\s+not|never)\s+(?:call|mark|label|treat|consider)\b.*\b(?:whole|entire|all|task)\b.*\b(?:failure|fail\w*)\b.*\b(?:if|when)\b", lowered)
    ) or bool(
        re.search(r"\b(?:call|label|treat|report|mark|count)\s+(?:it|the\s+task|task|completion)?\s*(?:as\s+)?partial\s+success\b", lowered)
    ) or bool(
        re.search(r"\b(?:if|when)\s+(?:only\s+)?(?:\w+\s+)?(?:actions?|steps?)\s+succeed\w*\b.*\b(?:failure|partial)\b", lowered)
    ) or bool(
        re.search(r"\bpartial\s+completion\s*(?:=>|->|means|is|equals)\s*partial\s+success\b", lowered)
    )

    if is_partial_success_rule:
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.CONTROL,
            intent="response_policy",
            slots={
                "policy_type": "partial_success_policy",
                "partial_completion_status": "PARTIAL_SUCCESS",
                "partial_success_enabled": True,
            },
            confidence=1.0,
            source=RouteSource.EXACT,
            complexity=ComplexityLevel.SIMPLE,
            normalized_text=cleaned,
            clarification="Understood. When some actions succeed and others fail, I will report the task as a partial success rather than a total failure.",
            reason_code="RESPONSE_POLICY",
        )

    # 3. Reply Style / Brevity
    # e.g. "keep replies short", "keep responses concise", "be concise", "give brief answers"
    is_brevity_rule = bool(
        re.search(r"\b(?:keep|make)\s+(?:my\s+|your\s+)?(?:replies|responses|answers)\s+(?:short|concise|brief)\b", lowered)
        or re.search(r"\b(?:be\s+concise|give\s+brief\s+answers|keep\s+it\s+brief)\b", lowered)
        or re.search(r"\b(?:don'?t|do\s+not)\s+give\s+long\s+(?:replies|answers|responses)\b", lowered)
    )

    if is_brevity_rule:
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.CONTROL,
            intent="response_policy",
            slots={
                "policy_type": "verbosity_policy",
                "concise_responses": True,
                "reply_style": "short",
            },
            confidence=1.0,
            source=RouteSource.EXACT,
            complexity=ComplexityLevel.SIMPLE,
            normalized_text=cleaned,
            clarification="Understood. I will keep my replies short and concise.",
            reason_code="RESPONSE_POLICY",
        )

    # 4. Failure Detail Policy
    # e.g. "tell me exactly what failed", "explain which step failed", "always list failed steps"
    is_failure_detail_rule = bool(
        re.search(r"\b(?:tell|show|explain)\s+(?:me\s+)?(?:exactly\s+)?(?:what|which\s+step)\s+failed\b", lowered)
        or re.search(r"\b(?:always\s+)?(?:explain|detail)\s+(?:the\s+)?failures\b", lowered)
        or re.search(r"\blist\s+(?:all\s+)?failed\s+steps\b", lowered)
    )

    if is_failure_detail_rule:
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.CONTROL,
            intent="response_policy",
            slots={
                "policy_type": "failure_detail_policy",
                "explain_failures": True,
                "failure_detail": "detailed",
            },
            confidence=1.0,
            source=RouteSource.EXACT,
            complexity=ComplexityLevel.SIMPLE,
            normalized_text=cleaned,
            clarification="Understood. I will provide a detailed explanation of which steps succeeded, failed, or were skipped.",
            reason_code="RESPONSE_POLICY",
        )

    # 5. Retry Policy
    # e.g. "don't automatically retry uncertain sends", "do not auto retry failed actions", "never retry without asking"
    is_retry_policy = bool(
        re.search(r"\b(?:don'?t|do\s+not|never)\s+(?:automatically\s+|auto[\s-]?)?retry\s+(?:uncertain|failed)\b", lowered)
        or re.search(r"\b(?:don'?t|do\s+not|never)\s+retry\s+without\s+asking\b", lowered)
    )

    if is_retry_policy:
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.CONTROL,
            intent="response_policy",
            slots={
                "policy_type": "retry_policy",
                "auto_retry_uncertain": False,
            },
            confidence=1.0,
            source=RouteSource.EXACT,
            complexity=ComplexityLevel.SIMPLE,
            normalized_text=cleaned,
            clarification="Understood. I will not automatically retry uncertain actions.",
            reason_code="RESPONSE_POLICY",
        )

    # 6. Benchmark / Meta-Test Evaluation Instruction
    # e.g. "Speak continuously for two minutes with corrections and verify no duplicated partial words."
    is_benchmark_instruction = bool(
        (re.search(r"\b(?:speak|talk)\s+continuously\b", lowered) and re.search(r"\b(?:verify|test|check)\b", lowered))
        or re.search(r"\bverify\s+no\s+(?:duplicated|duplicate)\s+partial\b", lowered)
        or re.search(r"\b(?:run|execute)\s+(?:benchmark|dictation\s+test|evaluation\s+suite)\b", lowered)
    )

    if is_benchmark_instruction:
        return RouteDecision(
            request_id=request_id,
            lane=RouteLane.CONTROL,
            intent="meta_instruction",
            slots={
                "instruction_type": "benchmark_evaluation",
                "instruction": cleaned,
            },
            confidence=1.0,
            source=RouteSource.EXACT,
            complexity=ComplexityLevel.SIMPLE,
            normalized_text=cleaned,
            clarification="Understood. Benchmark evaluation instruction noted; no unintended actions will be performed.",
            reason_code="META_INSTRUCTION",
        )

    return None
