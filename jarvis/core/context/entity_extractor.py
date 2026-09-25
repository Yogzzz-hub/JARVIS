"""Lightweight Semantic Entity and Topic Extractor for JARVIS EDGE.

Extracts high-confidence software, model, technology, person, and project entities
from user utterances and assistant responses without requiring large language models.
Provides canonicalization and alias unification.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from jarvis.core.catalog.package_catalog import CURATED_PACKAGES
from jarvis.core.context.models import EntityRef, EntityType, TopicRef

# Canonical alias dictionary
CANONICAL_ENTITIES: Dict[str, Dict[str, Any]] = {
    "ollama": {
        "canonical_name": "ollama",
        "display_name": "Ollama",
        "entity_type": EntityType.SOFTWARE,
        "aliases": ["ollama", "ollama ai", "ollama runtime"],
        "capabilities": ["app.install_software", "app.open", "app.check_installed"],
    },
    "lm studio": {
        "canonical_name": "lmstudio",
        "display_name": "LM Studio",
        "entity_type": EntityType.SOFTWARE,
        "aliases": ["lm studio", "lmstudio"],
        "capabilities": ["app.install_software", "app.open"],
    },
    "docker": {
        "canonical_name": "docker",
        "display_name": "Docker",
        "entity_type": EntityType.SOFTWARE,
        "aliases": ["docker", "docker desktop"],
        "capabilities": ["app.install_software", "app.open", "app.check_installed"],
    },
    "vs code": {
        "canonical_name": "vscode",
        "display_name": "Visual Studio Code",
        "entity_type": EntityType.APPLICATION,
        "aliases": ["vscode", "vs code", "visual studio code", "code"],
        "capabilities": ["app.open", "app.close", "app.get_location"],
    },
    "vlc": {
        "canonical_name": "vlc",
        "display_name": "VLC Media Player",
        "entity_type": EntityType.APPLICATION,
        "aliases": ["vlc", "vlc player", "vlc media player"],
        "capabilities": ["app.open", "app.install_software", "app.close"],
    },
    "chrome": {
        "canonical_name": "chrome",
        "display_name": "Google Chrome",
        "entity_type": EntityType.APPLICATION,
        "aliases": ["chrome", "google chrome", "chrome browser"],
        "capabilities": ["app.open", "app.close", "app.get_location"],
    },
    "edge": {
        "canonical_name": "msedge",
        "display_name": "Microsoft Edge",
        "entity_type": EntityType.APPLICATION,
        "aliases": ["edge", "microsoft edge", "msedge"],
        "capabilities": ["app.open", "app.close"],
    },
    "firefox": {
        "canonical_name": "firefox",
        "display_name": "Mozilla Firefox",
        "entity_type": EntityType.APPLICATION,
        "aliases": ["firefox", "mozilla firefox"],
        "capabilities": ["app.open", "app.close", "app.install_software"],
    },
    "spotify": {
        "canonical_name": "spotify",
        "display_name": "Spotify",
        "entity_type": EntityType.APPLICATION,
        "aliases": ["spotify", "spotify music"],
        "capabilities": ["app.open", "app.close", "windows.media_control"],
    },
    "notepad": {
        "canonical_name": "notepad",
        "display_name": "Notepad",
        "entity_type": EntityType.APPLICATION,
        "aliases": ["notepad", "text editor"],
        "capabilities": ["app.open", "app.close"],
    },
    "calculator": {
        "canonical_name": "calculator",
        "display_name": "Calculator",
        "entity_type": EntityType.APPLICATION,
        "aliases": ["calc", "calculator"],
        "capabilities": ["app.open", "app.close"],
    },
    "qwen": {
        "canonical_name": "qwen",
        "display_name": "Qwen",
        "entity_type": EntityType.MODEL,
        "aliases": ["qwen", "qwen2", "qwen 2.5", "qwen3"],
        "capabilities": ["rag.document_qa"],
    },
    "llama": {
        "canonical_name": "llama",
        "display_name": "Llama",
        "entity_type": EntityType.MODEL,
        "aliases": ["llama", "llama2", "llama3", "llama 3.1"],
        "capabilities": ["rag.document_qa"],
    },
    "mistral": {
        "canonical_name": "mistral",
        "display_name": "Mistral",
        "entity_type": EntityType.MODEL,
        "aliases": ["mistral", "mistral 7b", "mixtral"],
        "capabilities": ["rag.document_qa"],
    },
    "python": {
        "canonical_name": "python",
        "display_name": "Python",
        "entity_type": EntityType.TECHNOLOGY,
        "aliases": ["python", "python3"],
        "capabilities": ["terminal.powershell"],
    },
    "git": {
        "canonical_name": "git",
        "display_name": "Git",
        "entity_type": EntityType.SOFTWARE,
        "aliases": ["git", "git scm"],
        "capabilities": ["workflow.git_status", "app.install_software"],
    },
}

# Reverse lookup alias map
ALIAS_MAP: Dict[str, Dict[str, Any]] = {}
for entry in CANONICAL_ENTITIES.values():
    for alias in entry["aliases"]:
        ALIAS_MAP[alias.casefold()] = entry
    ALIAS_MAP[entry["canonical_name"].casefold()] = entry
    ALIAS_MAP[entry["display_name"].casefold()] = entry

# Also include curated packages from PackageCatalog
for pkg_id, pkg in CURATED_PACKAGES.items():
    if pkg.canonical_name.casefold() not in ALIAS_MAP:
        e = {
            "canonical_name": pkg.canonical_name,
            "display_name": pkg.display_name,
            "entity_type": EntityType.SOFTWARE,
            "aliases": list(pkg.aliases),
            "capabilities": ["app.install_software", "app.open"],
        }
        for al in pkg.aliases:
            ALIAS_MAP[al.casefold()] = e


class EntityExtractor:
    """Extracts entities from user requests and assistant output."""

    @staticmethod
    def extract_from_utterance(text: str, turn_index: int = 0) -> List[EntityRef]:
        """Extracts candidate entities from user text."""
        lowered = text.casefold()
        found: List[EntityRef] = []
        seen_canon = set()

        # 1. Pattern checks for explanatory / question preambles:
        # "What is Ollama?", "What is Ollama used for?", "Explain Docker", "Tell me about Qwen"
        m_what = re.search(
            r"\b(?:what\s+is|what\s+are|what's|what\s+does|how\s+does|tell\s+me\s+about|explain|describe)\s+([a-zA-Z0-9_\-\.\+\#\s]+?)(?:\s+(?:used\s+for|do|mean|work|differ))?\??$",
            lowered,
        )
        if m_what:
            candidate_phrase = m_what.group(1).strip()
            # Split conjunctions if multiple: "Python, Java and C++" or "Ollama and LM Studio"
            parts = re.split(r",\s*|\s+and\s+|\s+vs\s+|\s+versus\s+", candidate_phrase)
            for p in parts:
                clean_p = p.strip()
                if clean_p and len(clean_p) >= 2:
                    ent = EntityExtractor._resolve_or_create(clean_p, turn_index=turn_index)
                    if ent.canonical_name not in seen_canon:
                        seen_canon.add(ent.canonical_name)
                        found.append(ent)

        # 2. Comparison queries: "Compare Ollama and LM Studio"
        m_comp = re.search(r"\bcompare\s+([a-zA-Z0-9_\-\.\s]+?)\s+(?:and|with|to)\s+([a-zA-Z0-9_\-\.\s]+)", lowered)
        if m_comp:
            for group_idx in (1, 2):
                c_cand = m_comp.group(group_idx).strip()
                ent = EntityExtractor._resolve_or_create(c_cand, turn_index=turn_index)
                if ent.canonical_name not in seen_canon:
                    seen_canon.add(ent.canonical_name)
                    found.append(ent)

        # 3. Known alias search in text
        for alias, info in ALIAS_MAP.items():
            if re.search(rf"\b{re.escape(alias)}\b", lowered):
                canon = info["canonical_name"]
                if canon not in seen_canon:
                    seen_canon.add(canon)
                    found.append(
                        EntityRef(
                            entity_id=f"ent_{canon}_{turn_index}",
                            canonical_name=canon,
                            display_name=info["display_name"],
                            entity_type=info["entity_type"],
                            aliases=info["aliases"],
                            source_turn=turn_index,
                            confidence=0.98,
                            salience=1.0,
                            possible_capabilities=info.get("capabilities", []),
                        )
                    )

        # Sort by salience and order of appearance
        return found

    @staticmethod
    def extract_from_assistant_response(text: str, turn_index: int = 0) -> List[EntityRef]:
        """Extracts high-confidence mentioned entities from assistant's generated explanation."""
        lowered = text.casefold()
        found: List[EntityRef] = []
        seen_canon = set()

        for alias, info in ALIAS_MAP.items():
            if re.search(rf"\b{re.escape(alias)}\b", lowered):
                canon = info["canonical_name"]
                if canon not in seen_canon:
                    seen_canon.add(canon)
                    found.append(
                        EntityRef(
                            entity_id=f"ent_ans_{canon}_{turn_index}",
                            canonical_name=canon,
                            display_name=info["display_name"],
                            entity_type=info["entity_type"],
                            aliases=info["aliases"],
                            source_turn=turn_index,
                            confidence=0.95,
                            salience=0.9,
                            possible_capabilities=info.get("capabilities", []),
                        )
                    )

        return found

    @staticmethod
    def _resolve_or_create(name: str, turn_index: int = 0) -> EntityRef:
        clean = name.strip()
        lowered = clean.casefold()
        if lowered in ALIAS_MAP:
            info = ALIAS_MAP[lowered]
            return EntityRef(
                entity_id=f"ent_{info['canonical_name']}_{turn_index}",
                canonical_name=info["canonical_name"],
                display_name=info["display_name"],
                entity_type=info["entity_type"],
                aliases=info["aliases"],
                source_turn=turn_index,
                confidence=0.95,
                salience=1.0,
                possible_capabilities=info.get("capabilities", []),
            )
        # Novel / unseen entity fallback
        canon = clean.lower().replace(" ", "_")
        return EntityRef(
            entity_id=f"ent_{canon}_{turn_index}",
            canonical_name=canon,
            display_name=clean,
            entity_type=EntityType.TOPIC,
            aliases=[clean.lower()],
            source_turn=turn_index,
            confidence=0.85,
            salience=1.0,
            possible_capabilities=["rag.document_qa", "app.install_software"],
        )

    extract_from_user_query = extract_from_utterance
