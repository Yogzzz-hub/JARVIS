"""Reference resolution for conversational pronouns, ordinals, and project context."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from jarvis.core.context.models import ReferenceConfidence, ReferenceResolution
from jarvis.core.memory.working import BoundedWorkingMemory
from jarvis.core.memory.store import SQLiteMemoryStore


ORDINAL_MAP = {
    "first": 0, "1st": 0,
    "second": 1, "2nd": 1,
    "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3,
    "fifth": 4, "5th": 4,
    "last": -1,
}

EXTENSION_MAP = {
    "pdf": [".pdf"],
    "notes": [".pdf", ".txt", ".md"],
    "doc": [".docx", ".doc", ".txt", ".md"],
    "document": [".docx", ".doc", ".pdf", ".txt", ".md"],
    "script": [".py", ".ps1", ".bat", ".sh"],
    "python": [".py"],
    "image": [".png", ".jpg", ".jpeg"],
}


class ReferenceResolver:
    """
    Deterministic reference resolver that resolves conversational referents from
    working memory, search context, and durable memory without guessing.
    Strict Invariant: Consequential state changes require HIGH confidence or return AMBIGUOUS.
    """

    def __init__(
        self,
        working_memory: BoundedWorkingMemory,
        memory_store: Optional[SQLiteMemoryStore] = None,
    ):
        self.working_memory = working_memory
        self.memory_store = memory_store

    def resolve(self, utterance: str, is_consequential: bool = False) -> ReferenceResolution:
        text = utterance.strip().casefold()

        # 1. Folder references: "same folder", "that folder", "same directory as before"
        if any(p in text for p in ("same folder", "that folder", "the folder", "that directory", "same directory")):
            folder = self.working_memory.get_last_selected_folder()
            if folder:
                return ReferenceResolution(
                    referent=folder,
                    referent_type="FOLDER",
                    confidence=ReferenceConfidence.HIGH,
                    source="WORKING_MEMORY_FOLDER",
                )
            last_file = self.working_memory.get_last_opened_file()
            if last_file:
                parent = str(Path(last_file).parent)
                return ReferenceResolution(
                    referent=parent,
                    referent_type="FOLDER",
                    confidence=ReferenceConfidence.HIGH,
                    source="WORKING_MEMORY_FILE_PARENT",
                )
            return ReferenceResolution(
                referent=None,
                referent_type="FOLDER",
                confidence=ReferenceConfidence.LOW,
                source="NOT_FOUND",
                clarification_prompt="Which folder are you referring to?",
            )

        # 2. Ordinal references: "the second one", "open the 1st", "the second file"
        for ord_word, idx in ORDINAL_MAP.items():
            if f"the {ord_word}" in text or f"{ord_word} one" in text or f"{ord_word} file" in text:
                search_results = self.working_memory.get_recent_search_results()
                if search_results:
                    if idx == -1:
                        target = search_results[-1]
                        return ReferenceResolution(
                            referent=target.get("path") or target,
                            referent_type="SEARCH_RESULT",
                            confidence=ReferenceConfidence.HIGH,
                            source="RECENT_SEARCH_ORDINAL",
                        )
                    if 0 <= idx < len(search_results):
                        target = search_results[idx]
                        return ReferenceResolution(
                            referent=target.get("path") or target,
                            referent_type="SEARCH_RESULT",
                            confidence=ReferenceConfidence.HIGH,
                            source="RECENT_SEARCH_ORDINAL",
                        )
                recent_files = self.working_memory.get_recent_files()
                if recent_files and 0 <= idx < len(recent_files):
                    return ReferenceResolution(
                        referent=recent_files[idx],
                        referent_type="FILE",
                        confidence=ReferenceConfidence.HIGH,
                        source="RECENT_FILES_ORDINAL",
                    )
                return ReferenceResolution(
                    referent=None,
                    referent_type="SEARCH_RESULT",
                    confidence=ReferenceConfidence.LOW,
                    source="ORDINAL_OUT_OF_RANGE",
                    clarification_prompt=f"There are not enough recent results to select the {ord_word} one.",
                )

        # 3. Type-filtered references: "that pdf", "put that pdf in...", "the script"
        for type_key, extensions in EXTENSION_MAP.items():
            if type_key in text and ("that" in text or "the" in text):
                search_results = self.working_memory.get_recent_search_results()
                matched_paths = []
                for res in search_results:
                    path_str = res.get("path", "")
                    if any(path_str.casefold().endswith(ext) for ext in extensions):
                        matched_paths.append(path_str)
                if len(matched_paths) == 1:
                    return ReferenceResolution(
                        referent=matched_paths[0],
                        referent_type="FILE",
                        confidence=ReferenceConfidence.HIGH,
                        source="SEARCH_TYPE_FILTER_UNIQUE",
                    )
                elif len(matched_paths) > 1:
                    return ReferenceResolution(
                        referent=None,
                        referent_type="FILE",
                        confidence=ReferenceConfidence.AMBIGUOUS,
                        source="MULTIPLE_MATCHING_FILES",
                        candidates=matched_paths,
                        clarification_prompt=f"Which {type_key} do you mean: {', '.join(Path(p).name for p in matched_paths[:3])}?",
                    )

                # Fallback to last opened file if extension matches
                last_opened = self.working_memory.get_last_opened_file()
                if last_opened and any(last_opened.casefold().endswith(ext) for ext in extensions):
                    return ReferenceResolution(
                        referent=last_opened,
                        referent_type="FILE",
                        confidence=ReferenceConfidence.HIGH,
                        source="LAST_OPENED_TYPE_MATCH",
                    )

        # 4. Direct pronouns: "open it", "open it again", "that file", "open that", "do that again"
        if any(p in text for p in ("open it", "open it again", "open that", "that file", "do that again", "run it")):
            last_file = self.working_memory.get_last_opened_file()
            if last_file:
                return ReferenceResolution(
                    referent=last_file,
                    referent_type="FILE",
                    confidence=ReferenceConfidence.HIGH,
                    source="WORKING_MEMORY_LAST_FILE",
                )
            search_results = self.working_memory.get_recent_search_results()
            if len(search_results) == 1:
                return ReferenceResolution(
                    referent=search_results[0].get("path"),
                    referent_type="FILE",
                    confidence=ReferenceConfidence.HIGH,
                    source="SINGLE_SEARCH_RESULT",
                )
            elif len(search_results) > 1:
                return ReferenceResolution(
                    referent=None,
                    referent_type="FILE",
                    confidence=ReferenceConfidence.AMBIGUOUS,
                    source="AMBIGUOUS_SEARCH_RESULTS",
                    candidates=[r.get("path") for r in search_results[:3]],
                    clarification_prompt="Multiple files were recently found. Which one should I open?",
                )

        # 5. Project references: "open the project I was working on yesterday", "last project"
        if "project" in text and ("yesterday" in text or "last" in text or "worked on" in text or "open" in text):
            curr_proj = self.working_memory.get_current_project()
            if curr_proj:
                return ReferenceResolution(
                    referent=curr_proj,
                    referent_type="PROJECT",
                    confidence=ReferenceConfidence.HIGH,
                    source="WORKING_MEMORY_PROJECT",
                )
            if self.memory_store is not None:
                # Query durable project memories
                project_items = self.memory_store.list_active(limit=10)
                proj_candidates = [m for m in project_items if m.kind in ("project_root", "project_ide", "project")]
                if len(proj_candidates) == 1:
                    return ReferenceResolution(
                        referent=proj_candidates[0].value,
                        referent_type="PROJECT",
                        confidence=ReferenceConfidence.HIGH,
                        source="MEMORY_STORE_PROJECT_UNIQUE",
                    )
                elif len(proj_candidates) > 1:
                    names = [p.key for p in proj_candidates]
                    return ReferenceResolution(
                        referent=None,
                        referent_type="PROJECT",
                        confidence=ReferenceConfidence.AMBIGUOUS,
                        source="MULTIPLE_PROJECT_CANDIDATES",
                        candidates=[p.value for p in proj_candidates],
                        clarification_prompt=f"Which project did you mean: {' or '.join(names[:3])}?",
                    )

        # Default: no recognized referent
        return ReferenceResolution(
            referent=None,
            referent_type="UNKNOWN",
            confidence=ReferenceConfidence.LOW,
            source="NO_MATCH",
        )
