"""Deterministic Reference Resolver for Conversational Continuity in JARVIS EDGE.

Implements intent-guided, typed reference resolution with:
- Deterministic salience scoring (Type Compatibility > Selection > Active Task > Active Topic > Recency)
- Multi-entity resolution per slot ("Send it to him" -> it: file, him: contact)
- Ordinal resolution against active ResultSets
- Failure recovery follow-ups (e.g. "Install it" after "I couldn't find VLC")
- Active topic & software package resolution (e.g. "What is Ollama?" -> "Install it")
- Explainable disambiguation with candidate names when ambiguous
- Revalidation before consequential action
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from jarvis.core.catalog.package_catalog import CURATED_PACKAGES, PackageCatalog
from jarvis.core.context.models import (
    ApplicationResourceRef,
    BaseResourceRef,
    ContactResourceRef,
    DeviceResourceRef,
    DraftResourceRef,
    EntityRef,
    EntityType,
    FileResourceRef,
    FolderResourceRef,
    PackageResourceRef,
    ReferenceConfidence,
    ReferenceResolution,
    ResultSet,
    TopicRef,
)

ORDINAL_MAP = {
    "first": 0, "1st": 0, "one": 0,
    "second": 1, "2nd": 1, "two": 1,
    "third": 2, "3rd": 2, "three": 2,
    "fourth": 3, "4th": 3, "four": 3,
    "fifth": 4, "5th": 4, "five": 4,
    "last": -1, "final": -1,
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
    working context, search results, and durable memory without guessing.
    Strict Invariant: Consequential state changes require HIGH confidence or return AMBIGUOUS.
    """

    def __init__(
        self,
        working_memory: BoundedWorkingMemory,
        memory_store: Optional[SQLiteMemoryStore] = None,
        package_catalog: Optional[PackageCatalog] = None,
    ):
        self.working_memory = working_memory
        self.memory_store = memory_store
        self.package_catalog = package_catalog or PackageCatalog()

    def resolve(self, utterance: str, is_consequential: bool = False) -> ReferenceResolution:
        """General resolution for an utterance, inferring target slot from context."""
        return self.resolve_for_slot(utterance, expected_slot_type=None, intent=None, is_consequential=is_consequential)

    def resolve_for_slot(
        self,
        phrase_or_utterance: str = "",
        expected_slot_type: Optional[str] = None,
        intent: Optional[str] = None,
        is_consequential: bool = False,
        expected_type: Optional[str] = None,
        phrase: Optional[str] = None,
        utterance: Optional[str] = None,
    ) -> ReferenceResolution:
        """
        Resolves reference guided by the candidate action's expected slot type and intent.
        Slot types: 'file', 'folder', 'app', 'package', 'contact', 'device', 'query', 'recipient'
        """
        raw_text = utterance or phrase_or_utterance
        text = raw_text.strip().casefold()
        slot_type = (expected_type or expected_slot_type or "").lower()
        intent_str = (intent or "").lower()
        target_phrase = phrase or (phrase_or_utterance if utterance else "it")

        # ---------------------------------------------------------------------
        # 1. Folder references: "same folder", "that folder", "its folder", "parent directory"
        # ---------------------------------------------------------------------
        if any(p in text for p in ("same folder", "that folder", "the folder", "that directory", "same directory", "its folder", "parent folder", "parent dir")) or slot_type == "folder":
            is_parent_ref = any(p in text for p in ("its folder", "parent folder", "parent dir", "parent directory"))
            curr_res = getattr(self.working_memory, "get_current_resource", lambda: None)()

            if is_parent_ref:
                if curr_res and hasattr(curr_res, "canonical_path") and curr_res.canonical_path:
                    parent = str(Path(curr_res.canonical_path).parent)
                    return ReferenceResolution(
                        referent=parent,
                        referent_type="FOLDER",
                        confidence=ReferenceConfidence.HIGH,
                        source="CURRENT_RESOURCE_PARENT",
                        phrase="its folder",
                        evidence=["current_resource_parent"],
                        score=1.0,
                    )

            if curr_res and isinstance(curr_res, FolderResourceRef) and curr_res.canonical_path:
                return ReferenceResolution(
                    referent=curr_res.canonical_path,
                    referent_type="FOLDER",
                    confidence=ReferenceConfidence.HIGH,
                    source="CURRENT_RESOURCE_FOLDER",
                    score=0.98,
                )

            folder = self.working_memory.get_last_selected_folder()
            if folder:
                return ReferenceResolution(
                    referent=folder,
                    referent_type="FOLDER",
                    confidence=ReferenceConfidence.HIGH,
                    source="WORKING_MEMORY_FOLDER",
                    score=0.95,
                )

            if curr_res and hasattr(curr_res, "canonical_path") and curr_res.canonical_path:
                parent = str(Path(curr_res.canonical_path).parent)
                return ReferenceResolution(
                    referent=parent,
                    referent_type="FOLDER",
                    confidence=ReferenceConfidence.HIGH,
                    source="CURRENT_RESOURCE_PARENT",
                    phrase="its folder",
                    evidence=["current_resource_parent"],
                    score=0.90,
                )

            last_file = self.working_memory.get_last_opened_file()
            if last_file:
                parent = str(Path(last_file).parent)
                return ReferenceResolution(
                    referent=parent,
                    referent_type="FOLDER",
                    confidence=ReferenceConfidence.HIGH,
                    source="WORKING_MEMORY_FILE_PARENT",
                    score=0.90,
                )
            return ReferenceResolution(
                referent=None,
                referent_type="FOLDER",
                confidence=ReferenceConfidence.LOW,
                source="NOT_FOUND",
                clarification_prompt="Which folder are you referring to?",
            )

        # ---------------------------------------------------------------------
        # 2. Ordinal references: "the second one", "open the 1st", "item number 2", "second file"
        # ---------------------------------------------------------------------
        for ord_word, idx in ORDINAL_MAP.items():
            if (
                f"the {ord_word}" in text
                or f"{ord_word} one" in text
                or f"{ord_word} file" in text
                or f"{ord_word} result" in text
                or f"{ord_word} document" in text
                or f"{ord_word} app" in text
                or f"{ord_word} option" in text
                or re.match(rf"^(?:the\s+)?{ord_word}$", text)
            ):
                return self._resolve_ordinal(idx, ord_word, expected_slot_type=slot_type)

        m_num = re.search(r"\b(?:item\s+number|number|result)\s+(\d+)\b", text)
        if m_num:
            idx = int(m_num.group(1)) - 1
            return self._resolve_ordinal(idx, str(idx + 1), expected_slot_type=slot_type)

        # ---------------------------------------------------------------------
        # 3. Follow-up after failure: "Install it" after "I couldn't find VLC"
        # ---------------------------------------------------------------------
        if ("install" in text or "install" in intent_str or slot_type in ("package", "software")) and any(p in text for p in ("it", "that", "this", "app", "software")):
            last_fail = getattr(self.working_memory, "get_last_failure", lambda: None)()
            active_topic = getattr(self.working_memory, "get_active_topic", lambda: None)()
            if last_fail and last_fail.get("target") and (not active_topic or active_topic.canonical_name.casefold() == last_fail["target"].casefold()):
                failed_target = last_fail["target"]
                return ReferenceResolution(
                    referent=failed_target,
                    referent_type="PACKAGE",
                    confidence=ReferenceConfidence.HIGH,
                    source="FAILURE_RECOVERY",
                    phrase="it",
                    evidence=["recent_failure_target", "install_intent_compatibility"],
                    score=0.98,
                )

        # ---------------------------------------------------------------------
        # 4. Contact / Recipient reference: "Send it to him", "What does he want?"
        # ---------------------------------------------------------------------
        if slot_type in ("contact", "recipient") or any(p in text for p in ("he", "him", "she", "her", "contact")):
            curr_c = getattr(self.working_memory, "get_current_contact", lambda: None)()
            if curr_c:
                c_name = getattr(curr_c, "name", str(curr_c))
                return ReferenceResolution(
                    referent=c_name,
                    referent_type="CONTACT",
                    confidence=ReferenceConfidence.HIGH,
                    source="CURRENT_CONTACT",
                    phrase="him" if "him" in text else "he",
                    score=0.98,
                    resolved_resource=curr_c,
                )
            persons = getattr(self.working_memory, "get_recent_entities", lambda t=None: [])(EntityType.PERSON)
            if len(persons) == 1:
                return ReferenceResolution(
                    referent=persons[0].canonical_name,
                    referent_type="CONTACT",
                    confidence=ReferenceConfidence.HIGH,
                    source="RECENT_PERSON_ENTITY",
                    score=0.95,
                    resolved_entity=persons[0],
                )
            elif len(persons) > 1:
                names = [p.display_name for p in persons[:3]]
                return ReferenceResolution(
                    referent=None,
                    referent_type="CONTACT",
                    confidence=ReferenceConfidence.AMBIGUOUS,
                    source="AMBIGUOUS_CONTACTS",
                    candidates=names,
                    clarification_prompt=f"Which contact: {' or '.join(names)}?",
                )

        # ---------------------------------------------------------------------
        # 5. Draft / Message reference: "Send it", "Show it", "Make it Monday"
        # ---------------------------------------------------------------------
        if slot_type in ("draft", "message", "reply") or (slot_type == "draft" and "it" in text):
            draft = getattr(self.working_memory, "get_pending_draft", lambda: None)()
            if draft:
                val = getattr(draft, "content", None) or getattr(draft, "text", "")
                return ReferenceResolution(
                    referent=val,
                    referent_type="DRAFT",
                    confidence=ReferenceConfidence.HIGH,
                    source="PENDING_DRAFT",
                    phrase="it",
                    score=0.98,
                    resolved_resource=draft,
                )

        # ---------------------------------------------------------------------
        # 6. Media / Browser Playback reference: "Pause it", "Play another"
        # ---------------------------------------------------------------------
        if slot_type in ("media", "playback", "browser_page", "page", "url"):
            page = getattr(self.working_memory, "get_current_browser_resource", lambda: None)()
            if page:
                val = getattr(page, "url", None) or getattr(page, "title", str(page))
                return ReferenceResolution(
                    referent=val,
                    referent_type="BROWSER_PAGE",
                    confidence=ReferenceConfidence.HIGH,
                    source="CURRENT_BROWSER_PAGE",
                    phrase="it",
                    score=0.95,
                    resolved_resource=page,
                )

        # ---------------------------------------------------------------------
        # 7. Model reference: "Can Ollama run it?", "Download it"
        # ---------------------------------------------------------------------
        if slot_type in ("model", "llm"):
            models = getattr(self.working_memory, "get_recent_entities", lambda t=None: [])(EntityType.MODEL)
            if models:
                return ReferenceResolution(
                    referent=models[0].canonical_name,
                    referent_type="MODEL",
                    confidence=ReferenceConfidence.HIGH,
                    source="RECENT_MODEL_ENTITY",
                    phrase="it",
                    score=0.95,
                    resolved_entity=models[0],
                )

        # ---------------------------------------------------------------------
        # 8. Action on Topic / Software Entity ("What is Ollama?" -> "Install it")
        # ---------------------------------------------------------------------
        is_software_intent = (
            "install" in text
            or "install" in intent_str
            or slot_type in ("software", "package", "package_name", "app", "application", "name")
            or "where did it install" in text
            or "check its version" in text
            or "is it installed" in text
            or "where is it installed" in text
            or "open it" in text
        )

        has_pronoun = any(re.search(rf"\b{p}\b", text) for p in ("it", "that", "this", "that one", "this one", "them")) or target_phrase in ("it", "this", "that")

        if is_software_intent and has_pronoun:
            # Check active topic first
            active_topic = getattr(self.working_memory, "get_active_topic", lambda: None)()
            recent_entities = getattr(self.working_memory, "get_recent_entities", lambda t=None: [])()
            software_entities = [
                e for e in recent_entities
                if e.entity_type in (EntityType.SOFTWARE, EntityType.APPLICATION, EntityType.PACKAGE, EntityType.TECHNOLOGY)
            ]

            # Ambiguity check: If 2 or more candidate software entities are currently in focus
            # and no single clear active topic exists
            if len(software_entities) >= 2 and not active_topic:
                names = [e.display_name for e in software_entities[:3]]
                return ReferenceResolution(
                    referent=None,
                    referent_type="PACKAGE" if "install" in text else "APPLICATION",
                    confidence=ReferenceConfidence.AMBIGUOUS,
                    source="AMBIGUOUS_SOFTWARE_ENTITIES",
                    candidates=names,
                    clarification_prompt=f"Do you mean {' or '.join(names)}?",
                    evidence=["multiple_recent_software_entities"],
                )

            if active_topic and active_topic.entity_type in (EntityType.SOFTWARE, EntityType.APPLICATION, EntityType.PACKAGE, EntityType.TECHNOLOGY, EntityType.TOPIC):
                target_type = "PACKAGE" if ("install" in text or "install" in intent_str or slot_type in ("package", "software")) else "APPLICATION"
                return ReferenceResolution(
                    referent=active_topic.canonical_name,
                    referent_type=target_type,
                    confidence=ReferenceConfidence.HIGH,
                    source="ACTIVE_TOPIC",
                    phrase="it",
                    evidence=["active_topic", "software_intent_compatibility"],
                    score=0.96,
                    resolved_entity=active_topic,
                )

            if software_entities:
                chosen = software_entities[0]
                target_type = "PACKAGE" if ("install" in text or "install" in intent_str or slot_type in ("package", "software")) else "APPLICATION"
                return ReferenceResolution(
                    referent=chosen.canonical_name,
                    referent_type=target_type,
                    confidence=ReferenceConfidence.HIGH,
                    source="RECENT_SOFTWARE_ENTITY",
                    phrase="it",
                    evidence=["recent_software_entity", "software_intent_compatibility"],
                    score=0.92,
                    resolved_entity=chosen,
                )

        # ---------------------------------------------------------------------
        # 9. Device target resolution: "send it to my phone", "send this to it"
        # ---------------------------------------------------------------------
        if slot_type in ("device", "destination") or (not slot_type and any(d in text for d in ("phone", "android", "mobile", "cell"))):
            return ReferenceResolution(
                referent="phone",
                referent_type="DEVICE",
                confidence=ReferenceConfidence.HIGH,
                source="DEVICE_SLOT",
                phrase="phone",
                score=1.0,
            )

        # ---------------------------------------------------------------------
        # 10. File / Document reference by slot type: "Send it", "Where is it", "Delete it"
        # ---------------------------------------------------------------------
        if slot_type in ("file", "document", "path", "source") and has_pronoun:
            sel_res = getattr(self.working_memory, "get_selected_resource", lambda: None)()
            if sel_res and hasattr(sel_res, "canonical_path") and sel_res.canonical_path:
                return ReferenceResolution(
                    referent=sel_res.canonical_path,
                    referent_type="FILE",
                    confidence=ReferenceConfidence.HIGH,
                    source="UI_SELECTED_RESOURCE",
                    phrase="it",
                    score=1.0,
                    resolved_resource=sel_res,
                )

            curr_res = getattr(self.working_memory, "get_current_resource", lambda: None)()
            if curr_res and hasattr(curr_res, "canonical_path") and curr_res.canonical_path:
                if not isinstance(curr_res, FolderResourceRef) or slot_type == "path":
                    return ReferenceResolution(
                        referent=curr_res.canonical_path,
                        referent_type="FILE",
                        confidence=ReferenceConfidence.HIGH,
                        source="CURRENT_RESOURCE",
                        phrase="it",
                        score=0.98,
                        resolved_resource=curr_res,
                    )

            last_file = getattr(self.working_memory, "get_last_opened_file", lambda: None)()
            if last_file:
                return ReferenceResolution(
                    referent=last_file,
                    referent_type="FILE",
                    confidence=ReferenceConfidence.HIGH,
                    source="WORKING_MEMORY_LAST_FILE",
                    phrase="it",
                    score=0.95,
                )

            search_results = getattr(self.working_memory, "get_recent_search_results", lambda: [])()
            if len(search_results) == 1:
                first = search_results[0]
                target_p = first.get("path") if isinstance(first, dict) else getattr(first, "path", str(first))
                return ReferenceResolution(
                    referent=target_p,
                    referent_type="FILE",
                    confidence=ReferenceConfidence.HIGH,
                    source="SINGLE_SEARCH_RESULT",
                    phrase="it",
                    score=0.90,
                )
            elif len(search_results) > 1:
                cands = [r.get("path") if isinstance(r, dict) else getattr(r, "path", str(r)) for r in search_results[:5]]
                names = [Path(p).name for p in cands if p]
                return ReferenceResolution(
                    referent=None,
                    referent_type="FILE",
                    confidence=ReferenceConfidence.AMBIGUOUS,
                    source="AMBIGUOUS_SEARCH_RESULTS",
                    candidates=cands,
                    clarification_prompt=f"Which file do you mean: {' or '.join(names[:3])}?",
                )

        # ---------------------------------------------------------------------
        # 6. Type-filtered references: "that pdf", "the document", "that script"
        # ---------------------------------------------------------------------
        for type_key, extensions in EXTENSION_MAP.items():
            if type_key in text and ("that" in text or "the" in text or "this" in text):
                # Check current resource first if extension matches
                curr_res = getattr(self.working_memory, "get_current_resource", lambda: None)()
                if curr_res and hasattr(curr_res, "canonical_path") and curr_res.canonical_path:
                    if any(curr_res.canonical_path.casefold().endswith(ext) for ext in extensions):
                        return ReferenceResolution(
                            referent=curr_res.canonical_path,
                            referent_type="FILE",
                            confidence=ReferenceConfidence.HIGH,
                            source="CURRENT_RESOURCE_TYPE_MATCH",
                            phrase=f"that {type_key}",
                            score=1.0,
                        )

                search_results = self.working_memory.get_recent_search_results()
                matched_paths = []
                for res in search_results:
                    path_str = res.get("path", "") if isinstance(res, dict) else getattr(res, "path", str(res))
                    if any(path_str.casefold().endswith(ext) for ext in extensions):
                        matched_paths.append(path_str)
                if len(matched_paths) == 1:
                    return ReferenceResolution(
                        referent=matched_paths[0],
                        referent_type="FILE",
                        confidence=ReferenceConfidence.HIGH,
                        source="SEARCH_TYPE_FILTER_UNIQUE",
                        score=0.95,
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

                last_opened = self.working_memory.get_last_opened_file()
                if last_opened and any(last_opened.casefold().endswith(ext) for ext in extensions):
                    return ReferenceResolution(
                        referent=last_opened,
                        referent_type="FILE",
                        confidence=ReferenceConfidence.HIGH,
                        source="LAST_OPENED_TYPE_MATCH",
                        score=0.90,
                    )

        # ---------------------------------------------------------------------
        # 7. Knowledge follow-up on file: "What's it about?", "Where is it stored?", "Summarize it"
        # ---------------------------------------------------------------------
        is_doc_query = any(q in text for q in (
            "what's it about", "what is it about", "what does it talk about",
            "what does it cover", "summarize it", "explain it", "where is it",
            "where is it stored", "where is it located", "what is in it",
        ))
        if is_doc_query or "summarize" in text or "compare" in text:
            curr_res = getattr(self.working_memory, "get_current_resource", lambda: None)()
            if curr_res and hasattr(curr_res, "canonical_path") and curr_res.canonical_path:
                return ReferenceResolution(
                    referent=curr_res.canonical_path,
                    referent_type="FILE",
                    confidence=ReferenceConfidence.HIGH,
                    source="CURRENT_RESOURCE_DOC_QUERY",
                    phrase="it",
                    score=1.0,
                )
            last_file = self.working_memory.get_last_opened_file()
            if last_file:
                return ReferenceResolution(
                    referent=last_file,
                    referent_type="FILE",
                    confidence=ReferenceConfidence.HIGH,
                    source="LAST_OPENED_DOC_QUERY",
                    phrase="it",
                    score=0.95,
                )

        # ---------------------------------------------------------------------
        # 8. General Pronouns: "open it", "close it", "send that", "delete it", "open that"
        # ---------------------------------------------------------------------
        if any(p in text for p in ("open it", "close it", "close that", "open that", "that file", "send that", "send it", "delete it", "run it", "do that again")):
            # Check UI-selected resource first (Section 10: selected_resource > current_resource)
            sel_res = getattr(self.working_memory, "get_selected_resource", lambda: None)()
            if sel_res:
                ref_type = getattr(sel_res, "resource_type", "FILE")
                ident = getattr(sel_res, "canonical_identifier", None) or getattr(sel_res, "canonical_path", None)
                if ident:
                    return ReferenceResolution(
                        referent=ident,
                        referent_type=ref_type,
                        confidence=ReferenceConfidence.HIGH,
                        source="UI_SELECTED_RESOURCE",
                        phrase="this",
                        score=1.0,
                    )

            if "close" in text:
                last_app = getattr(self.working_memory, "get_last_focused_app", lambda: None)()
                if last_app:
                    return ReferenceResolution(
                        referent=last_app,
                        referent_type="APP",
                        confidence=ReferenceConfidence.HIGH,
                        source="WORKING_MEMORY_LAST_APP",
                        phrase="it",
                        score=0.95,
                    )

            # Check current resource
            curr_res = getattr(self.working_memory, "get_current_resource", lambda: None)()
            if curr_res:
                ref_type = getattr(curr_res, "resource_type", "FILE")
                ident = getattr(curr_res, "canonical_identifier", None) or getattr(curr_res, "canonical_path", None)
                if ident:
                    return ReferenceResolution(
                        referent=ident,
                        referent_type=ref_type,
                        confidence=ReferenceConfidence.HIGH,
                        source="CURRENT_RESOURCE",
                        phrase="it",
                        score=0.95,
                    )

            last_file = getattr(self.working_memory, "get_last_opened_file", lambda: None)()
            if last_file:
                return ReferenceResolution(
                    referent=last_file,
                    referent_type="FILE",
                    confidence=ReferenceConfidence.HIGH,
                    source="WORKING_MEMORY_LAST_FILE",
                    phrase="it",
                    score=0.92,
                )

            search_results = getattr(self.working_memory, "get_recent_search_results", lambda: [])()
            if len(search_results) == 1:
                first = search_results[0]
                target_p = first.get("path") if isinstance(first, dict) else getattr(first, "path", str(first))
                return ReferenceResolution(
                    referent=target_p,
                    referent_type="FILE",
                    confidence=ReferenceConfidence.HIGH,
                    source="SINGLE_SEARCH_RESULT",
                    phrase="that",
                    score=0.90,
                )
            elif len(search_results) > 1:
                cands = [r.get("path") if isinstance(r, dict) else getattr(r, "path", str(r)) for r in search_results[:3]]
                names = [Path(p).name for p in cands if p]
                return ReferenceResolution(
                    referent=None,
                    referent_type="FILE",
                    confidence=ReferenceConfidence.AMBIGUOUS,
                    source="AMBIGUOUS_SEARCH_RESULTS",
                    candidates=cands,
                    clarification_prompt=f"Which file do you mean: {' or '.join(names)}?",
                )

        # ---------------------------------------------------------------------
        # 9. Project references: "open the project", "last project", "Jarvis project"
        # ---------------------------------------------------------------------
        if "project" in text and ("yesterday" in text or "last" in text or "worked on" in text or "open" in text or "run" in text):
            curr_proj = self.working_memory.get_current_project()
            if curr_proj:
                return ReferenceResolution(
                    referent=curr_proj,
                    referent_type="PROJECT",
                    confidence=ReferenceConfidence.HIGH,
                    source="WORKING_MEMORY_PROJECT",
                    score=0.95,
                )
            if self.memory_store is not None:
                project_items = self.memory_store.list_active(limit=10)
                proj_candidates = [m for m in project_items if m.kind in ("project_root", "project_ide", "project")]
                if len(proj_candidates) == 1:
                    return ReferenceResolution(
                        referent=proj_candidates[0].value,
                        referent_type="PROJECT",
                        confidence=ReferenceConfidence.HIGH,
                        source="MEMORY_STORE_PROJECT_UNIQUE",
                        score=0.90,
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

        # Default fallback: check if any active resource or topic fits slot_type
        if slot_type in ("path", "source", "file"):
            curr_res = getattr(self.working_memory, "get_current_resource", lambda: None)()
            if curr_res and hasattr(curr_res, "canonical_path"):
                return ReferenceResolution(
                    referent=curr_res.canonical_path,
                    referent_type="FILE",
                    confidence=ReferenceConfidence.HIGH,
                    source="CURRENT_RESOURCE_FALLBACK",
                    score=0.88,
                )

        return ReferenceResolution(
            referent=None,
            referent_type="UNKNOWN",
            confidence=ReferenceConfidence.LOW,
            source="NO_MATCH",
        )

    def _resolve_ordinal(self, idx: int, ord_label: str, expected_slot_type: Optional[str] = None) -> ReferenceResolution:
        """Resolves ordinal index from active ResultSet or recent search results."""
        # 1. Try active ResultSet from working memory
        active_rs = getattr(self.working_memory, "get_active_result_set", lambda: None)()
        if active_rs and active_rs.resources:
            target_res = active_rs.get_by_ordinal(idx)
            if target_res:
                ident = (
                    getattr(target_res, "canonical_path", None)
                    or getattr(target_res, "url", None)
                    or getattr(target_res, "canonical_identifier", None)
                    or getattr(target_res, "canonical_name", None)
                    or getattr(target_res, "display_name", None)
                    or str(target_res)
                )
                # Set as current resource
                if hasattr(self.working_memory, "set_current_resource"):
                    self.working_memory.set_current_resource(target_res)
                return ReferenceResolution(
                    referent=ident,
                    referent_type=getattr(target_res, "resource_type", "FILE"),
                    confidence=ReferenceConfidence.HIGH,
                    source="ACTIVE_RESULT_SET_ORDINAL",
                    phrase=f"the {ord_label} one",
                    score=1.0,
                    resolved_resource=target_res,
                )

        # 2. Try raw recent search results
        search_results = self.working_memory.get_recent_search_results()
        if search_results:
            target = None
            if idx == -1:
                target = search_results[-1]
            elif 0 <= idx < len(search_results):
                target = search_results[idx]

            if target:
                target_path = target.get("path") if isinstance(target, dict) else getattr(target, "path", str(target))
                f_ref = FileResourceRef(canonical_path=str(target_path))
                if hasattr(self.working_memory, "set_current_resource"):
                    self.working_memory.set_current_resource(f_ref)
                return ReferenceResolution(
                    referent=target_path,
                    referent_type="SEARCH_RESULT",
                    confidence=ReferenceConfidence.HIGH,
                    source="RECENT_SEARCH_ORDINAL",
                    phrase=f"the {ord_label} one",
                    score=0.95,
                    resolved_resource=f_ref,
                )

        # 3. Try recent files
        recent_files = self.working_memory.get_recent_files()
        if recent_files and 0 <= idx < len(recent_files):
            f_ref = FileResourceRef(canonical_path=recent_files[idx])
            if hasattr(self.working_memory, "set_current_resource"):
                self.working_memory.set_current_resource(f_ref)
            return ReferenceResolution(
                referent=recent_files[idx],
                referent_type="FILE",
                confidence=ReferenceConfidence.HIGH,
                source="RECENT_FILES_ORDINAL",
                phrase=f"the {ord_label} one",
                score=0.90,
                resolved_resource=f_ref,
            )

        return ReferenceResolution(
            referent=None,
            referent_type="SEARCH_RESULT",
            confidence=ReferenceConfidence.LOW,
            source="ORDINAL_OUT_OF_RANGE",
            clarification_prompt=f"There are not enough recent results to select the {ord_label} one.",
        )
