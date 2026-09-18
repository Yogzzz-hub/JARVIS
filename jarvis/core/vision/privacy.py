"""Privacy, Redaction, and Anti-Bypass Security Gate for Vision Automation."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw

from jarvis.core.vision.models import VisualCandidate, VisualObservation


# Known prompt-injection signatures visible on screens or web pages
SUSPICIOUS_VISUAL_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:previous\s+)?(?:user\s+)?instructions",
    r"upload\s+(?:all\s+)?files?\s+(?:from\s+)?(?:desktop|c:\\|downloads)",
    r"delete\s+(?:all\s+)?(?:files|downloads|c:\\)",
    r"send\s+(?:all\s+)?(?:passwords|tokens|credentials)",
    r"system:\s*override",
    r"ai\s+agent:\s*ignore",
    r"execute\s+(?:command|cmd|powershell|bash)",
]

# Sensitive screen indicators
PASSWORD_INDICATORS = ["password", "passwd", "pin", "credential", "login password", "enter password"]
OTP_INDICATORS = ["otp", "one-time password", "verification code", "2fa code", "security code", "authenticator"]
CAPTCHA_INDICATORS = ["captcha", "recaptcha", "hcaptcha", "verify you are human", "select all squares with", "not a robot"]
UAC_INDICATORS = ["user account control", "do you want to allow this app", "credential prompt", "secure desktop"]


def detect_visual_prompt_injection(text: str) -> List[str]:
    """Scan visible screen text for adversarial prompt-injection payloads."""
    findings: List[str] = []
    if not text:
        return findings
    for pattern in SUSPICIOUS_VISUAL_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            findings.append(f"Suspicious visual instruction detected: '{match.group(0)}'")
    return findings


def check_auth_or_challenge_screen(
    window_title: str,
    visible_texts: List[str],
    candidates: List[VisualCandidate],
) -> Tuple[bool, str, Optional[str]]:
    """Detect password prompts, CAPTCHAs, or UAC elevation screens."""
    combined_text = (window_title + " " + " ".join(visible_texts)).lower()

    # 1. Check UAC / Secure Desktop
    if any(k in combined_text for k in UAC_INDICATORS):
        return True, "PAUSE_FOR_USER", "UAC / Secure Desktop prompt detected. Automated elevation prohibited."

    # 2. Check CAPTCHA
    if any(k in combined_text for k in CAPTCHA_INDICATORS):
        return True, "PAUSE_FOR_USER", "CAPTCHA challenge detected. Automated bypass prohibited."

    for c in candidates:
        cand_text = f"{c.visible_text or ''} {c.icon_description or ''} {c.candidate_id}".lower()
        if any(k in cand_text for k in CAPTCHA_INDICATORS):
            return True, "PAUSE_FOR_USER", "CAPTCHA element detected in visual candidates."

    # 3. Check Password / OTP
    if any(k in combined_text for k in PASSWORD_INDICATORS):
        return True, "AUTH_REQUIRED", "Login/password screen detected. Automated password entry prohibited."

    if any(k in combined_text for k in OTP_INDICATORS):
        return True, "AUTH_REQUIRED", "OTP / 2FA verification screen detected. Automated credential scraping prohibited."

    return False, "OK", None


def redact_sensitive_boxes(
    image: Image.Image,
    boxes_pixels: List[Tuple[int, int, int, int]],
    fill_color: str = "#000000",
) -> Image.Image:
    """Mask known sensitive screen regions (e.g. password fields, secret tokens) before VLM inference."""
    if not boxes_pixels:
        return image
    redacted = image.copy()
    draw = ImageDraw.Draw(redacted)
    for x1, y1, x2, y2 in boxes_pixels:
        draw.rectangle([x1, y1, x2, y2], fill=fill_color)
    return redacted


def evaluate_visual_observation_privacy(
    observation: VisualObservation,
    visible_text_corpus: str = "",
) -> Tuple[bool, str, List[str]]:
    """Run full privacy, security, and prompt-injection check on a visual observation.
    
    Returns:
        (allowed_to_interact, decision_code, quarantine_notes)
    """
    notes: List[str] = []

    # 1. Prompt injection check
    injections = detect_visual_prompt_injection(visible_text_corpus)
    if injections:
        notes.extend(injections)
        observation.quarantine_notes.extend(injections)

    # 2. Screen challenge / auth check
    is_blocked, status, reason = check_auth_or_challenge_screen(
        window_title=observation.window_title,
        visible_texts=[visible_text_corpus] if visible_text_corpus else [],
        candidates=observation.candidates,
    )
    if is_blocked:
        return False, status, [reason or "Screen challenge blocked by policy."]

    return True, "OK", notes
