"""Alias Resolver and Query Normalizer for JARVIS EDGE.
Provides high-speed in-memory resolution of colloquial names to canonical application IDs,
with deterministic ambiguity detection.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("jarvis.catalog.alias_resolver")

# Built-in synonym mappings for standard Windows and popular software
DEFAULT_SYNONYMS: Dict[str, str] = {
    # Text editors & IDEs
    "vs code": "vscode",
    "visual studio code": "vscode",
    "code": "vscode",
    "notepad plus plus": "notepadplusplus",
    "notepad++": "notepadplusplus",
    "npp": "notepadplusplus",
    "sublime text": "sublimetext",
    "sublime": "sublimetext",
    # Browsers
    "google chrome": "chrome",
    "chrome browser": "chrome",
    "microsoft edge": "edge",
    "msedge": "edge",
    "edge browser": "edge",
    "mozilla firefox": "firefox",
    "firefox browser": "firefox",
    "mozilla": "firefox",
    "brave browser": "brave",
    "opera browser": "opera",
    # Media & Players
    "vlc media player": "vlc",
    "vlc player": "vlc",
    "videolan": "vlc",
    "videolan vlc": "vlc",
    "obs studio": "obs",
    "open broadcaster software": "obs",
    "spotify music": "spotify",
    "windows media player": "wmplayer",
    # Windows utilities & Tools
    "calc": "calculator",
    "file explorer": "explorer",
    "windows explorer": "explorer",
    "my computer": "explorer",
    "this pc": "explorer",
    "windows terminal": "terminal",
    "wt": "terminal",
    "command prompt": "cmd",
    "powershell terminal": "powershell",
    "task manager": "taskmgr",
    "taskmanager": "taskmgr",
    "paint": "mspaint",
    "ms paint": "mspaint",
    "microsoft paint": "mspaint",
    "snipping tool": "snippingtool",
    "snip": "snippingtool",
    "screen snip": "snippingtool",
    "screenshot tool": "snippingtool",
    "control panel": "control",
    # Office
    "ms word": "word",
    "microsoft word": "word",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "ms powerpoint": "powerpoint",
    "microsoft powerpoint": "powerpoint",
    "ppt": "powerpoint",
    "ms outlook": "outlook",
    "microsoft outlook": "outlook",
    "mail": "outlook",
    "ms onenote": "onenote",
    "microsoft onenote": "onenote",
    "ms teams": "teams",
    "microsoft teams": "teams",
    # Windows Apps & UWP
    "photos": "photos",
    "windows photos": "photos",
    "microsoft photos": "photos",
    "camera": "camera",
    "webcam": "camera",
    "windows camera": "camera",
    "clock": "clock",
    "windows clock": "clock",
    "alarms": "clock",
    "timer": "clock",
    "weather": "weather",
    "msn weather": "weather",
    "maps": "maps",
    "windows maps": "maps",
}

# Known inherently ambiguous terms that should request clarification if multiple exist
AMBIGUOUS_TERMS: Dict[str, Tuple[str, ...]] = {
    "studio": ("Android Studio", "Visual Studio", "Visual Studio Code"),
    "office": ("Microsoft Word", "Microsoft Excel", "Microsoft PowerPoint"),
}


class AliasResolver:
    """Fast in-memory resolver that maps colloquial terms to canonical application IDs."""

    def __init__(self):
        self._alias_to_app_id: Dict[str, str] = {}
        self._app_id_to_aliases: Dict[str, Set[str]] = {}
        # Pre-seed with defaults
        for alias, app_id in DEFAULT_SYNONYMS.items():
            self.register_alias(alias, app_id)

    @staticmethod
    def normalize(text: str) -> str:
        """Standardizes query text, collapsing whitespace and lowercasing."""
        if not text:
            return ""
        return " ".join(text.casefold().split())

    @classmethod
    def clean_conversational(cls, text: str) -> str:
        """Strips conversational action prefixes, polite fillers, and suffixes."""
        cleaned = cls.normalize(text)
        if not cleaned:
            return ""

        # Strip common leading verbs and articles
        cleaned = re.sub(
            r"^(?:please\s+|can\s+you\s+|could\s+you\s+|kindly\s+|open\s+|start\s+|launch\s+|run\s+|bring\s+up\s+|show\s+|the\s+|an\s+|a\s+)+",
            "",
            cleaned,
        ).strip()

        # Strip trailing polite phrases and common noun suffixes
        for _ in range(3):
            prev_len = len(cleaned)
            cleaned = re.sub(
                r"\s+(?:for me please|for us please|for me|for us|please|kindly|plz|if you can|right now|quickly|immediately|now|bro|dude|yaar|da|app|application|program|software|browser)$",
                "",
                cleaned,
            ).strip()
            if len(cleaned) == prev_len:
                break

        return cleaned

    def register_alias(self, alias: str, app_id: str) -> None:
        """Associates an alias with a canonical app_id."""
        norm_alias = self.normalize(alias)
        norm_app_id = self.normalize(app_id)
        if not norm_alias or not norm_app_id:
            return

        self._alias_to_app_id[norm_alias] = norm_app_id
        if norm_app_id not in self._app_id_to_aliases:
            self._app_id_to_aliases[norm_app_id] = set()
        self._app_id_to_aliases[norm_app_id].add(norm_alias)

    def register_app_aliases(self, app_id: str, display_name: str, aliases: Tuple[str, ...]) -> None:
        """Registers all aliases for an application entry."""
        self.register_alias(app_id, app_id)
        self.register_alias(display_name, app_id)
        for a in aliases:
            self.register_alias(a, app_id)

    def unregister_app(self, app_id: str) -> None:
        """Removes all aliases pointing to this app_id."""
        norm_app_id = self.normalize(app_id)
        aliases = self._app_id_to_aliases.pop(norm_app_id, set())
        for a in aliases:
            if self._alias_to_app_id.get(a) == norm_app_id:
                self._alias_to_app_id.pop(a, None)

    def resolve(self, query: str) -> Tuple[Optional[str], Optional[List[str]], Optional[str]]:
        """
        Resolves query to (app_id, ambiguous_candidates, clarification_prompt).
        Returns:
            - (app_id, None, None) on clean unambiguous resolution.
            - (None, [c1, c2], prompt) on ambiguous query.
            - (None, None, None) if not found.
        """
        cleaned = self.clean_conversational(query)
        if not cleaned:
            return None, None, None

        # 1. Exact direct match in alias table
        if cleaned in self._alias_to_app_id:
            return self._alias_to_app_id[cleaned], None, None

        # 2. Check for inherently ambiguous terms (e.g. "studio")
        if cleaned in AMBIGUOUS_TERMS:
            candidates = list(AMBIGUOUS_TERMS[cleaned])
            choices_str = ", ".join(candidates[:-1]) + f", or {candidates[-1]}"
            prompt = f"Which one do you mean: {choices_str}?"
            return None, candidates, prompt

        # 3. Check token matches
        tokens = cleaned.split()
        if len(tokens) > 1:
            for t in tokens:
                if t in self._alias_to_app_id:
                    return self._alias_to_app_id[t], None, None

        # 4. Prefix match check or whole word match for ambiguity
        matches: List[str] = []
        for alias, app_id in self._alias_to_app_id.items():
            if len(cleaned) >= 3 and (alias.startswith(cleaned) or re.search(rf"\b{re.escape(cleaned)}\b", alias)):
                if app_id not in matches:
                    matches.append(app_id)

        if len(matches) == 1:
            return matches[0], None, None
        elif len(matches) > 1:
            # Genuine ambiguity among discovered installed apps
            choices = matches[:3]
            choices_str = ", ".join(choices[:-1]) + f", or {choices[-1]}"
            prompt = f"Multiple installed applications match '{cleaned}': {choices_str}. Which one do you mean?"
            return None, choices, prompt

        return None, None, None
