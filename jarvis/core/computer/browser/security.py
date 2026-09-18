"""Web Security, Untrusted Content Quarantine, and Script Audit Boundaries."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

SUSPICIOUS_WEB_PATTERNS = [
    re.compile(r"ignore\s+(previous|all|system|user)\s+instructions?", re.IGNORECASE),
    re.compile(r"delete\s+(everything|all\s+files|downloads)", re.IGNORECASE),
    re.compile(r"(system|ai\s+agent)\s*:\s*", re.IGNORECASE),
    re.compile(r"(send|upload)\s+(my|all)\s+files?\s+to", re.IGNORECASE),
    re.compile(r"run\s+(powershell|cmd|bash|terminal)", re.IGNORECASE),
    re.compile(r"upload\s+every\s+file", re.IGNORECASE),
]


def detect_web_prompt_injection(text: str) -> Tuple[bool, str]:
    """Detect if webpage content contains prompt-injection instructions."""
    if not text:
        return False, ""
    for pattern in SUSPICIOUS_WEB_PATTERNS:
        match = pattern.search(text)
        if match:
            return True, match.group(0)
    return False, ""


class BrowserScriptTemplate:
    """Audited, registered JavaScript template to prevent arbitrary LLM JS execution."""

    def __init__(self, script_id: str, script_body: str, description: str = "") -> None:
        self.script_id = script_id
        self.script_body = script_body
        self.description = description


REGISTERED_BROWSER_SCRIPTS: Dict[str, BrowserScriptTemplate] = {}


def register_audited_script(script: BrowserScriptTemplate) -> None:
    REGISTERED_BROWSER_SCRIPTS[script.script_id] = script


def validate_script_execution(script_id: str) -> Optional[BrowserScriptTemplate]:
    """Verify script is in pre-audited whitelist. Arbitrary model scripts are rejected."""
    return REGISTERED_BROWSER_SCRIPTS.get(script_id)
