"""Vocabulary bias provider for JARVIS EDGE STT.

Generates initial_prompt/context for Whisper from local knowledge:
installed apps, recent files, known folders, technical terms.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("jarvis.stt.vocabulary")


class VocabularyBiasProvider:
    """Provides vocabulary hints for STT initial prompt.

    Sources:
    - Installed app aliases (from AppResolver)
    - Recent files (from WorkingMemory)
    - Known folder names
    - Technical terms and project names

    Keeps prompt small (< 200 tokens) to avoid slowing transcription.
    """

    def __init__(
        self,
        app_resolver: Any = None,
        working_memory: Any = None,
        custom_terms: list[str] | None = None,
        max_tokens: int = 200,
    ):
        self.app_resolver = app_resolver
        self.working_memory = working_memory
        self.custom_terms = custom_terms or []
        self.max_tokens = max_tokens

        # Static technical terms common in user's workflow
        self._static_terms = [
            "Jarvis", "FastAPI", "Postgres", "GitHub", "React", "Docker", "Supabase",
            "Gmail", "WhatsApp", "Chrome", "backend", "frontend", "API", "GPU", "CPU",
            "Python", "Wi-Fi", "Edge", "VS Code", "PowerShell", "PDF",
        ]

    def generate_prompt(self, active_context: str = "") -> str:
        """Generate vocabulary bias prompt for Whisper.

        Returns a short text that biases recognition toward known entities,
        kept small (< 30 words / 150 chars) to prevent context overflow.
        """
        import re

        def _is_clean_term(t: str) -> bool:
            if not t or len(t) < 2 or len(t) > 30:
                return False
            if t[0].isdigit():
                return False
            digits = sum(c.isdigit() for c in t)
            if digits > 2:
                return False
            return any(c.isalpha() for c in t)

        ordered_terms: list[str] = []
        seen: set[str] = set()

        def _add_term(raw: str):
            c = re.sub(r"[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\ufe00-\ufe0f]", "", str(raw or ""))
            c = " ".join(c.split())
            if _is_clean_term(c) and c.lower() not in seen:
                seen.add(c.lower())
                ordered_terms.append(c)

        # Context names are hints only; bounded ahead of generic vocabulary.
        for term in self.custom_terms[:8]:
            _add_term(term)
        # 1. Static technical terms
        for term in self._static_terms:
            _add_term(term)

        # 2. Custom terms (e.g. key user contacts)
        for term in self.custom_terms:
            _add_term(term)

        # 3. App names from resolver
        if self.app_resolver:
            try:
                for name in self.app_resolver.list_apps()[:20]:
                    _add_term(name)
            except Exception:
                pass

        # 4. Recent files from working memory
        if self.working_memory:
            try:
                for entry in self.working_memory.recent_files()[:10]:
                    if isinstance(entry, str):
                        stem = entry.rsplit("\\", 1)[-1].rsplit("/", 1)[-1].rsplit(".", 1)[0]
                        _add_term(stem)
                    elif hasattr(entry, "name"):
                        _add_term(entry.name)
            except Exception:
                pass

        # 5. Active context
        if active_context:
            _add_term(active_context)

        # Build prompt — keep strictly under max_tokens / max 30 words / 150 chars
        max_words = min(int(self.max_tokens or 30), 30)
        prompt_parts = []
        word_count = 0
        char_count = 0
        for term in ordered_terms:
            words = len(term.split())
            if word_count + words > max_words or char_count + len(term) > 150:
                break
            prompt_parts.append(term)
            word_count += words
            char_count += len(term) + 2

        if not prompt_parts:
            return ""

        return ", ".join(prompt_parts) + "."


class JarvisSpeechVocabulary(VocabularyBiasProvider):
    """Bounded local metadata hints, never a transcript replacement dictionary."""
    @classmethod
    def from_metadata(cls, *, apps=(), projects=(), contacts=(), capabilities=()):
        terms = list(contacts)[:3] + list(projects)[:2] + list(apps)[:2]
        for capability in capabilities:
            terms.extend(str(capability).replace('_', ' ').replace('.', ' ').split())
        return cls(custom_terms=terms[:100], max_tokens=30)
