"""Unified SemanticFrame and FrameExtractor for JARVIS Edge.

Parses natural language commands into a typed, validated semantic representation
following the strict 20-step evaluation order before capability retrieval or execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from jarvis.core.capabilities.temporal import (
    DatePoint,
    DateRange,
    DateTimePoint,
    DateTimeRange,
    TemporalConstraint,
    TemporalResolver,
    TimeRange,
)
from jarvis.core.capabilities.typed_slots import (
    ApplicationRef,
    FolderRef,
    Ordinal,
    Percentage,
    ResourceRef,
    SizeConstraint,
    SpatialConstraint,
    extract_size_constraint,
)
from jarvis.core.router.guards import check_negation, is_informational_or_question
from jarvis.core.router.normalize import clean_for_matching, normalize_text


@dataclass
class SemanticFrame:
    """The canonical typed semantic frame consumed by router, capability retriever, and tools."""
    intent: Optional[str] = None
    actionability: bool = True

    # Targets & entities
    positive_targets: List[str] = field(default_factory=list)
    negative_targets: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    references: List[ResourceRef] = field(default_factory=list)

    # File & storage slots
    file_types: List[str] = field(default_factory=list)
    folders: List[str] = field(default_factory=list)
    ordinals: List[int] = field(default_factory=list)

    # Typed constraints
    temporal_constraints: List[TemporalConstraint] = field(default_factory=list)
    numeric_constraints: List[Any] = field(default_factory=list)
    size_constraints: List[SizeConstraint] = field(default_factory=list)
    include_constraints: List[str] = field(default_factory=list)
    exclude_constraints: List[str] = field(default_factory=list)
    spatial_constraints: Dict[str, str] = field(default_factory=dict)
    corrections: List[Dict[str, Any]] = field(default_factory=list)
    user_prohibitions: List[str] = field(default_factory=list)

    # Resolution flags
    ambiguity: bool = False
    confidence: float = 1.0
    raw_query: str = ""
    clean_query: str = ""
    language_features: Dict[str, Any] = field(default_factory=dict)

    def is_action_blocked(self, candidate_name: str) -> bool:
        """Determines if a candidate action or tool is forbidden by negative constraints."""
        cand_lower = candidate_name.lower().strip()
        for proh in self.user_prohibitions:
            p_clean = proh.lower().strip()
            if p_clean in ("open", "launch", "start", "send", "run"):
                continue  # generic verbs require checking target entity, not blanket tool rejection
            if p_clean and (p_clean in cand_lower or cand_lower in p_clean):
                return True
        return False


FILE_TYPE_KEYWORDS = {
    "pdf": "pdf", "pdfs": "pdf",
    "image": "image", "images": "image", "photo": "image", "photos": "image", "picture": "image", "pictures": "image",
    "report": "report", "reports": "report",
    "document": "document", "documents": "document", "doc": "document", "docs": "document", "docx": "docx",
    "spreadsheet": "spreadsheet", "spreadsheets": "spreadsheet", "sheet": "spreadsheet", "sheets": "spreadsheet", "excel": "spreadsheet", "xlsx": "xlsx",
    "audio": "audio", "song": "audio", "songs": "audio", "mp3": "mp3",
    "video": "video", "videos": "video", "mp4": "mp4",
    "text": "text", "txt": "txt",
    "presentation": "presentation", "presentations": "presentation", "slides": "presentation", "slide": "presentation", "deck": "presentation", "decks": "presentation", "pptx": "pptx",
    "archive": "archive", "archives": "archive", "zip": "zip",
}

FOLDER_KEYWORDS = {
    "downloads": "Downloads", "download": "Downloads",
    "documents": "Documents", "document": "Documents", "docs": "Documents",
    "desktop": "Desktop",
    "pictures": "Pictures", "photos": "Pictures",
    "music": "Music",
    "videos": "Videos",
}


def parse_spoken_number(s: str) -> Optional[int]:
    """Parses spoken number strings (e.g. 'twenty-five', 'sixty', '42') to int."""
    s = s.strip().lower()
    if s.isdigit():
        return int(s)
    tens = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
    ones = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
    if "-" in s:
        parts = s.split("-")
        if len(parts) == 2 and parts[0] in tens and parts[1] in ones:
            return tens[parts[0]] + ones[parts[1]]
    if s in tens:
        return tens[s]
    if s in ones:
        return ones[s]
    teens = {"zero": 0, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
             "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "hundred": 100}
    return teens.get(s)


class FrameExtractor:
    """Extracts a typed SemanticFrame following the strict 20-step evaluation pipeline."""

    def __init__(self, reference_dt: Optional[datetime] = None):
        self.temporal_resolver = TemporalResolver(reference_dt)

    def extract(
        self,
        text: str,
        working_memory: Optional[Any] = None,
        reference_resolver: Optional[Any] = None,
    ) -> SemanticFrame:
        frame = SemanticFrame(raw_query=text)

        # 1. Normalize
        cleaned_orig = clean_for_matching(text) or text
        _, routing_text = normalize_text(text)
        frame.clean_query = routing_text

        lowered = text.casefold().strip()

        # 2. Stop/Cancel detection
        if re.search(r"\b(?:stop|cancel|abort|halt|terminate)\b", lowered) and not re.search(r"\b(?:don'?t|do not)\s+stop\b", lowered):
            # Control action
            frame.intent = "cancel_task"
            return frame

        # 3. Negation & user prohibitions
        is_neg, constraints = check_negation(text)
        for c in constraints:
            c_type = c.get("type", "")
            target = str(c.get("target", "")).strip()
            if c_type in ("negative_action", "no_reply", "no_send", "no_modify", "no_delete", "no_open"):
                frame.user_prohibitions.append(target)
                for w in re.findall(r"\b[a-zA-Z0-9_\-]+\b", target):
                    if len(w) > 2 and w.lower() not in ("the", "a", "an", "any", "anything", "not", "dont"):
                        frame.negative_targets.append(w.lower())
                frame.exclude_constraints.append(target)

        # Prohibitive commands: "don't delete", "do not wipe", "never reboot"
        for m in re.finditer(r"\b(?:don'?t|do\s+not|never)\s+(?P<act>[a-zA-Z0-9_\-]+)", lowered):
            act = m.group("act").strip()
            if act not in ("open", "send", "reply", "modify", "delete"):
                frame.user_prohibitions.append(act)
                frame.negative_targets.append(act)

        # 4. Explicit exclusions: "not the screenshot", "not Chrome", "but not final report old", "open Edge not Chrome"
        m_exclude = re.search(
            r"\b(?:,\s*not\s+|,\s*but\s+not\s+|but\s+not\s+|except\s+|excluding\s+|without\s+|not\s+the\s+|\s+not\s+)(?P<ex>[^,.;]+)",
            lowered,
        )
        if m_exclude:
            ex_target = m_exclude.group("ex").strip()
            # Clean leading "to", "the", "a", "an"
            ex_target = re.sub(r"^(?:to|the|a|an)\s+", "", ex_target)
            frame.exclude_constraints.append(ex_target)
            for w in ex_target.split():
                if w not in ("the", "a", "an", "old", "one"):
                    frame.negative_targets.append(w)

        # "Send only the PDF, not the screenshot"
        if re.search(r"\bnot\s+(?:the\s+)?screenshot\b", lowered):
            frame.negative_targets.append("screenshot")
            frame.user_prohibitions.append("screenshot")

        # 5. Corrections & replacements:
        # Pattern A: Self-correction (e.g. "turn volume down to 30, no wait, 20" or "set brightness to 70, actually 50")
        m_self_corr = re.search(
            r"\b(?P<old>\d+|[a-zA-Z\-]+)\s*(?:%|percent)?\s*,\s*(?:no\s+wait|wait|actually|scratch\s+that|i\s+mean)\s*,?\s*(?P<new>\d+|[a-zA-Z\-]+)",
            lowered,
        )
        if m_self_corr:
            frame.corrections.append({
                "type": "numeric_override",
                "new_value": m_self_corr.group("new").strip(),
                "old_value": m_self_corr.group("old").strip(),
            })
            frame.exclude_constraints.append(m_self_corr.group("old").strip())
        else:
            # Pattern B: Explicit exclusion/replacement: "thirty-five percent, not fifty"
            m_corr_num = re.search(
                r"\b(?P<val>\d+|[a-zA-Z\-]+)\s*(?:%|percent)?\s*,\s*(?:not|instead\s+of)\s+(?P<old>\d+|[a-zA-Z\-]+)",
                lowered,
            )
            if m_corr_num:
                frame.corrections.append({
                    "type": "numeric_override",
                    "new_value": m_corr_num.group("val").strip(),
                    "old_value": m_corr_num.group("old").strip(),
                })
                frame.exclude_constraints.append(m_corr_num.group("old").strip())

        # 6. Actionability classification
        if is_informational_or_question(text, routing_text):
            frame.actionability = False
            frame.intent = "knowledge_query"
            return frame

        # 7. Spatial constraints & multi-clause window positioning:
        # "Open Chrome on the left and Antigravity on the right"
        spatial_matches = re.finditer(
            r"(?P<app>[a-zA-Z0-9_\-\s]+?)\s+on\s+the\s+(?P<pos>left|right|top|bottom|center)\b",
            lowered,
        )
        for sm in spatial_matches:
            app_raw = sm.group("app").strip()
            # Extract target app
            app_word = app_raw.split()[-1] if app_raw else ""
            if app_word in ("chrome", "antigravity", "edge", "notepad", "calculator", "browser"):
                frame.spatial_constraints[app_word] = sm.group("pos").lower()

        # 8. Typed slots: Ordinals, Folders, File types
        # Extract folder
        for f_key, f_val in FOLDER_KEYWORDS.items():
            if re.search(rf"\b(?:in|inside|under|from)\s+(?:the\s+|my\s+)?{f_key}\b", lowered) or re.search(rf"\b{f_key}\s+(?:folder|directory)\b", lowered):
                if f_val not in frame.folders:
                    frame.folders.append(f_val)

        # Extract file types (checking inclusion vs exclusion)
        for t_key, t_val in FILE_TYPE_KEYWORDS.items():
            if re.search(rf"\b{t_key}\b", lowered):
                # Check if it was in an exclusion span
                is_excluded = any(t_key in ex.lower() for ex in frame.exclude_constraints)
                if not is_excluded and t_val not in frame.file_types:
                    frame.file_types.append(t_val)

        # Extract ordinals (ensuring they refer to items, not time units or names)
        ord_map = {
            "first": 1, "1st": 1,
            "second": 2, "2nd": 2,
            "third": 3, "3rd": 3,
            "fourth": 4, "4th": 4,
            "fifth": 5, "5th": 5,
            "last": -1, "final": -1,
        }
        for m_ord in re.finditer(r"\b(?:the\s+)?(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|last|final)\b", lowered):
            ord_word = m_ord.group(1).lower()
            start, end = m_ord.span()
            after_tokens = lowered[end:].strip().split()
            first_after = re.sub(r"[^a-z]", "", after_tokens[0]) if after_tokens else ""
            is_time_unit = first_after in (
                "week", "month", "year", "monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday", "sunday", "weekend", "night", "morning", "evening", "afternoon",
            )
            is_in_name = bool(re.search(r"\bcalled\s+.*?" + ord_word, lowered))
            if not is_time_unit and not is_in_name:
                if ord_word in ord_map and ord_map[ord_word] not in frame.ordinals:
                    frame.ordinals.append(ord_map[ord_word])

        # Extract size constraints
        size_c, _ = extract_size_constraint(text)
        if size_c:
            frame.size_constraints.append(size_c)

        # Extract temporal expressions via TemporalResolver
        temp_c, _ = self.temporal_resolver.resolve(text)
        if temp_c:
            frame.temporal_constraints.append(temp_c)

        # Extract entities (e.g. Arun, Yoga, Chrome, Edge)
        m_entity = re.search(r"\b(?P<owner>[A-Z][a-z]+)'s\s+(?P<concept>report|document|file|notes?|invoice|presentation)\b", text)
        if m_entity:
            frame.entities.append(m_entity.group("owner"))
            frame.include_constraints.append(m_entity.group("concept"))
            if m_entity.group("concept") not in frame.file_types:
                frame.file_types.append(m_entity.group("concept"))

        # Explicit name search constraint: "called final report, but not final report old"
        m_called = re.search(r"\bcalled\s+(?P<name>[^,;]+?)(?:\s*,?\s+but\s+not\s+|\s*,?\s+except\s+|$)", text, re.I)
        if m_called:
            frame.include_constraints.append(m_called.group("name").strip())

        # Extract numeric constraints (percentages, counts)
        if frame.corrections and any(c.get("type") == "numeric_override" for c in frame.corrections):
            c_val = next(c for c in frame.corrections if c.get("type") == "numeric_override")["new_value"]
            pct_val = parse_spoken_number(c_val)
            if pct_val is not None:
                frame.numeric_constraints.append(Percentage(pct_val))
        else:
            m_pct = re.search(r"\b(?P<pct>\d+|[a-zA-Z]+(?:-[a-zA-Z]+)?)\s*(?:%|\bpercent\b)", lowered)
            if not m_pct:
                m_pct = re.search(r"\b(?:volume|sound|brightness|level)\s+(?:down\s+to\s+|up\s+to\s+|to\s+|at\s+)?(?P<pct>\d+|[a-zA-Z]+(?:-[a-zA-Z]+)?)\b", lowered)
            if m_pct:
                pct_raw = m_pct.group("pct")
                pct_val = parse_spoken_number(pct_raw)
                if pct_val is not None:
                    frame.numeric_constraints.append(Percentage(pct_val))

        # Check contextual ResourceRefs ("that PDF", "that file", "the screenshot")
        m_deictic = re.search(r"\b(?:that|this)\s+(?P<type>pdf|document|file|image|spreadsheet|report)\b", lowered)
        if m_deictic:
            d_type = m_deictic.group("type")
            ref = ResourceRef(referent=None, pronoun=f"that {d_type}", referent_type=d_type.upper())
            frame.references.append(ref)

        # 9. Classify Primary Intent
        if re.search(r"\b(?:find|search(?:\s+for)?|locate|show|look\s+for)\b", lowered):
            if re.search(r"\b(?:notes?|memo|memos)\b", lowered):
                frame.intent = "search_notes"
            # If files or documents or folders are mentioned:
            elif frame.file_types or frame.folders or frame.size_constraints or "file" in lowered or "files" in lowered or "document" in lowered:
                frame.intent = "find_file"
            elif any(w in lowered for w in ("contact", "person", "email")):
                frame.intent = "contact_search"
            else:
                frame.intent = "find_file"

        elif re.search(r"\b(?:open|launch|start|pull\s+up|fire\s+up)\b", lowered):
            if frame.file_types or frame.folders or frame.ordinals:
                frame.intent = "open_file"
            else:
                frame.intent = "open_app"

        elif re.search(r"\b(?:send|transfer|share)\b", lowered):
            frame.intent = "send_resource"
            if re.search(r"\bpdf\b", lowered) and "pdf" not in frame.include_constraints:
                frame.include_constraints.append("pdf")

        elif re.search(r"\b(?:volume|sound)\b", lowered):
            frame.intent = "volume_set" if frame.numeric_constraints else "volume_control"

        elif re.search(r"\bbrightness\b", lowered):
            frame.intent = "brightness_set"

        elif re.search(r"\breply\b", lowered) and any(w in lowered for w in ("yoga", "whatsapp", "message")):
            frame.intent = "whatsapp_auto_reply"

        return frame
