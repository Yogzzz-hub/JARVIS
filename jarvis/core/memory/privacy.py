"""Privacy, secret filtering, and untrusted-data boundary for JARVIS memory."""

from __future__ import annotations

import re
from typing import Any, Tuple
from jarvis.core.memory.models import MemoryCandidate, MemorySourceType


# High-entropy / known token / secret detection regexes
SECRET_PATTERNS = [
    re.compile(r"(?:api[_-]?key|apikey|secret|token|bearer|password|passwd|pwd)[\s:=]+['\"]?([a-zA-Z0-9_\-\.]{6,})['\"]?", re.IGNORECASE),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36}\b"),  # GitHub tokens
    re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}\b"),  # Google API keys
    re.compile(r"\bsk-[a-zA-Z0-9_\-]{20,}\b"),  # OpenAI-style secret keys (including sk-proj-)
    re.compile(r"(?:password|passwd|secret)[A-Za-z0-9!@#$%^&*()_+=\-]{4,}", re.IGNORECASE),  # Passwords
    re.compile(r"\b[0-9]{6}\b"),  # Standard 6-digit OTPs / PINs
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),  # Private keys
    re.compile(r"\b(?:session[_-]?id|cookie)[\s:=]+['\"]?[a-zA-Z0-9_%=\-]{16,}['\"]?", re.IGNORECASE),
]


def contains_sensitive_secret(text: str) -> bool:
    """Detects if a given string contains secrets, passwords, OTPs, or API keys."""
    if not isinstance(text, str):
        text = str(text)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return True
    return False


def is_trusted_memory_source(source_type: MemorySourceType) -> bool:
    """Verifies that the memory candidate comes from a trusted authority."""
    return source_type in (
        MemorySourceType.USER_EXPLICIT,
        MemorySourceType.VERIFIED_ACTION,
        MemorySourceType.USER_CORRECTION,
        MemorySourceType.APPROVED_WORKFLOW,
        MemorySourceType.TRUSTED_SYSTEM_STATE,
    )


def filter_memory_candidate(candidate: MemoryCandidate) -> Tuple[bool, str]:
    """
    Evaluates whether a candidate can be committed to durable memory.
    Returns (is_approved, reason).
    """
    # 1. Source Trust Invariant
    if not is_trusted_memory_source(candidate.source_type):
        return False, f"REJECT: untrusted source type {candidate.source_type.value}"

    # 2. Secret Filtering Invariant
    content_to_check = f"{candidate.key} {candidate.value}"
    if contains_sensitive_secret(content_to_check):
        return False, "REJECT: sensitive secret or credential pattern detected"

    # 3. Source Reference Validation (reject external content indicators)
    if candidate.source_reference:
        ref_lower = candidate.source_reference.lower()
        if any(marker in ref_lower for marker in ("email", "webpage", "html", "screen", "document", "untrusted")):
            return False, "REJECT: external content reference detected in durable candidate"

    return True, "STORE"
