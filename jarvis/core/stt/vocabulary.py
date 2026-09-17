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
            "Chrome", "Edge", "VS Code", "Visual Studio", "Notepad",
            "Calculator", "PowerShell", "Terminal", "Cisco Packet Tracer",
            "Power BI", "NLP", "PDF", "FastAPI", "Supabase",
        ]

    def generate_prompt(self, active_context: str = "") -> str:
        """Generate vocabulary bias prompt for Whisper.

        Returns a short text that biases recognition toward known entities.
        """
        terms = set()

        # 1. Static technical terms
        terms.update(self._static_terms)

        # 2. Custom terms
        terms.update(self.custom_terms)

        # 3. App names from resolver
        if self.app_resolver:
            try:
                for name in self.app_resolver.list_apps()[:30]:
                    terms.add(name)
            except Exception:
                pass

        # 4. Recent files from working memory
        if self.working_memory:
            try:
                for entry in self.working_memory.recent_files()[:20]:
                    if isinstance(entry, str):
                        # Extract filename stem
                        stem = entry.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
                        stem = stem.rsplit(".", 1)[0]
                        terms.add(stem)
                    elif hasattr(entry, "name"):
                        terms.add(entry.name)
            except Exception:
                pass

        # 5. Active context
        if active_context:
            terms.add(active_context)

        # Build prompt — keep under max_tokens (rough word count)
        all_terms = sorted(terms)
        prompt_parts = []
        word_count = 0
        for term in all_terms:
            words = len(term.split())
            if word_count + words > self.max_tokens:
                break
            prompt_parts.append(term)
            word_count += words

        if not prompt_parts:
            return ""

        return ", ".join(prompt_parts) + "."
