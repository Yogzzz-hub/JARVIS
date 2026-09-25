"""Deterministic Slot Extractor Aligned with Capability Definitions and Typed Schemas."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jarvis.core.capabilities.models import CapabilityCategory, CapabilityDefinition
from jarvis.core.capabilities.typed_slots import (
    ApplicationRef,
    ContactRef,
    DeviceRef,
    FolderRef,
    Ordinal,
    Percentage,
    ResourceRef,
)
from jarvis.core.context.models import ReferenceConfidence
from jarvis.core.router.slots import (
    FOLDER_ALIASES,
    collapse_spaced_letters,
    parse_app_name,
    parse_duration_seconds,
    parse_folder_path,
    parse_integer,
    parse_percentage,
    resolve_correction,
)

KNOWN_EXTENSIONS = ("pdf", "docx", "txt", "xlsx", "pptx", "zip", "mp3", "mp4", "jpg", "png", "json", "csv")


def extract_ordinal_slots(text: str) -> Tuple[Optional[int], Optional[List[int]]]:
    """Extracts ordinal numbers (1, 2, 3, -1 for last) or list of ordinals."""
    lowered = text.casefold()

    # Multi-ordinal comparison: 'compare the first one with the third one'
    ords = []
    if "first" in lowered or "1st" in lowered:
        ords.append(1)
    if "second" in lowered or "2nd" in lowered:
        ords.append(2)
    if "third" in lowered or "3rd" in lowered:
        ords.append(3)
    if "fourth" in lowered or "4th" in lowered:
        ords.append(4)
    if "fifth" in lowered or "5th" in lowered:
        ords.append(5)
    if len(ords) >= 2:
        return None, ords

    # Explicit number in list: 'item number 1 from the list' or 'number 2'
    m_num = re.search(r"\bitem\s+number\s+(\d+)\b", lowered)
    if m_num:
        return int(m_num.group(1)), None

    m_num2 = re.search(r"\bnumber\s+(\d+)\b", lowered)
    if m_num2:
        return int(m_num2.group(1)), None

    if re.search(r"\b(?:last\s+one|last\s+result|final\s+one)\b", lowered):
        return -1, None
    if re.search(r"\b(?:first\s+one|first\s+result|1st\s+one)\b", lowered):
        return 1, None
    if re.search(r"\b(?:second\s+one|second\s+result|2nd\s+one)\b", lowered):
        return 2, None
    if re.search(r"\b(?:third\s+one|third\s+result|3rd\s+one)\b", lowered):
        return 3, None
    if re.search(r"\b(?:fourth\s+one|fourth\s+result|4th\s+one)\b", lowered):
        return 4, None
    if re.search(r"\b(?:fifth\s+one|fifth\s+result|5th\s+one)\b", lowered):
        return 5, None

    return None, None


def extract_pronoun_and_referent(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extracts pronoun or context referent from text."""
    lowered = text.casefold()

    # Window management referents
    if any(w in lowered for w in ("close it", "minimize it", "maximize it", "restore it")):
        return None, "active_window"
    if "show its folder" in lowered or "open its folder" in lowered:
        return None, "parent_dir"

    # Pronoun phrases
    if "that pdf" in lowered:
        return "that PDF", None
    if "that one" in lowered:
        return "that one", None
    if "that file" in lowered:
        return "that", None
    if re.search(r"\bthat\b", lowered):
        return "that", None
    if re.search(r"\bthis\b", lowered):
        return "this", None
    if re.search(r"\bit\b", lowered):
        return "it", None

    return None, None


def extract_folder_slot(text: str) -> Optional[FolderRef]:
    """Extracts folder name from text, handling ASR variants like 'down loads'."""
    collapsed = collapse_spaced_letters(text).casefold()
    for alias in FOLDER_ALIASES:
        if re.search(rf"\b{alias}\b", collapsed):
            if "download" in alias:
                return FolderRef("Downloads")
            elif "document" in alias:
                return FolderRef("Documents")
            elif "desktop" in alias:
                return FolderRef("Desktop")
            elif "picture" in alias or "photo" in alias:
                return FolderRef("Pictures")
            elif "music" in alias:
                return FolderRef("Music")
            elif "video" in alias:
                return FolderRef("Videos")
    return None


def extract_extension_slot(text: str) -> Optional[str]:
    """Extracts file extension constraint from text."""
    lowered = text.casefold()
    for ext in KNOWN_EXTENSIONS:
        if re.search(rf"\b{ext}\b", lowered):
            return ext
    return None


def extract_messaging_slots(text: str) -> Tuple[Optional[ContactRef], Optional[str]]:
    """Extracts contact recipient and message body from natural conversational phrasing."""
    resolved_t = resolve_correction(text)
    clean = resolved_t.strip()

    # 1. "say/send/tell <msg> to <recipient> (in/on whatsapp)?"
    m1 = re.match(
        r"^(?:say|send|tell)\s+(?P<message>(?!whatsapp|message|this|the|a\s+message).+?)\s+to\s+(?P<recipient>[a-zA-Z0-9_\-\s]+?)(?:\s+(?:in|on)\s+whatsapp)?$",
        clean,
        re.I,
    )
    if m1:
        rec = m1.group("recipient").strip()
        msg = m1.group("message").strip().strip('"\'')
        if rec and msg and rec.lower() not in ("me", "him", "her", "them", "if", "the", "a"):
            return ContactRef(rec), msg

    # 2. "tell/text/message <recipient> (in/on whatsapp)? (saying |that )?<message>"
    m2 = re.match(
        r"^(?:tell|text|message)\s+(?P<recipient>[a-zA-Z0-9_\-]+)(?:\s+(?:in|on)\s+whatsapp)?\s+(?:saying\s+|that\s+|:\s*)?(?P<message>.+?)(?:\s+(?:in|on)\s+whatsapp)?$",
        clean,
        re.I,
    )
    if m2:
        rec = m2.group("recipient").strip()
        msg = m2.group("message").strip().strip('"\'')
        if rec and msg and rec.lower() not in ("me", "him", "her", "them", "if", "the", "a"):
            return ContactRef(rec), msg

    # 3. "whatsapp <recipient> <message>" or "(send )?whatsapp (message )?to <recipient> (saying )?<message>"
    m3 = re.match(
        r"^(?:(?:send(?: a)? )?whatsapp (?:message )?to |whatsapp )(?P<recipient>[a-zA-Z0-9_\-\s]+?)(?:\s+(?:saying|that|:)\s+|\s*:\s*|\s+)(?P<message>.+)$",
        clean,
        re.I,
    )
    if m3:
        rec = m3.group("recipient").strip()
        msg = m3.group("message").strip().strip('"\'')
        if rec and msg:
            return ContactRef(rec), msg

    # Fallback heuristic
    rec_val = None
    msg_val = None
    m_rec = re.search(r"\b(?:to|message)\s+([a-zA-Z0-9_\-\s]+?)(?:\s+(?:in|on)\s+whatsapp|\s+saying|\s+that|$)", resolved_t, re.I)
    if m_rec:
        rec_cand = m_rec.group(1).strip()
        if rec_cand and rec_cand.lower() not in ("whatsapp", "the", "a", "me", "him", "her", "them"):
            rec_val = ContactRef(rec_cand)

    m_msg = re.search(r"\b(?:saying|that|with message)\s+(.+)$", text, re.I)
    if m_msg:
        msg_val = m_msg.group(1).strip()

    return rec_val, msg_val


def extract_slots(
    capability: CapabilityDefinition,
    utterance: str,
    working_memory: Optional[Any] = None,
    reference_resolver: Optional[Any] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Extracts required and optional slots for a capability from natural language.
    Returns:
        (extracted_slots_dict, missing_required_slots_list)
    """
    text = collapse_spaced_letters(utterance.strip())
    lowered = text.casefold()
    slots: Dict[str, Any] = {}

    # Extract ordinals if present
    single_ord, multi_ords = extract_ordinal_slots(text)
    if single_ord is not None:
        slots["ordinal"] = Ordinal(single_ord)
    if multi_ords is not None:
        slots["ordinals"] = multi_ords

    # Extract pronouns / referents if present
    pronoun, referent = extract_pronoun_and_referent(text)
    if pronoun:
        slots["pronoun"] = pronoun
    if referent:
        slots["referent"] = referent
        if referent == "parent_dir":
            slots["name"] = ApplicationRef("explorer")


    # Extract folder if present
    f_slot = extract_folder_slot(text)
    if f_slot:
        slots["folder"] = f_slot

    # Extract extension if present
    ext_slot = extract_extension_slot(text)
    if ext_slot:
        slots["extension"] = ext_slot

    # Check for pronoun or contextual reference in working memory
    has_pronoun = any(re.search(rf"\b{p}\b", lowered) for p in ("it", "that", "this", "them", "first one", "last one", "same folder"))
    resolved_referent = None
    if has_pronoun and reference_resolver:
        try:
            res = reference_resolver.resolve(text)
            if res and res.confidence == ReferenceConfidence.HIGH and res.referent:
                resolved_referent = res.referent
        except Exception:
            pass

    # Extract messaging slots if capability belongs to WHATSAPP or GOOGLE messaging
    if any(s in capability.required_slots for s in ("recipient", "message")):
        msg_rec, msg_body = extract_messaging_slots(text)
        if msg_rec and "recipient" not in slots:
            slots["recipient"] = msg_rec
        if msg_body and "message" not in slots:
            slots["message"] = msg_body

    # Extract standard capability slots
    for slot_name in capability.required_slots + capability.optional_slots:
        val = None

        if slot_name == "percent":
            # Extract number followed by % or percent or standalone number, respecting correction
            val = parse_percentage(text)

        elif slot_name in ("name", "package_name"):
            if resolved_referent and capability.category in (CapabilityCategory.APP, CapabilityCategory.WINDOWS):
                val = ApplicationRef(str(resolved_referent))
            elif referent == "parent_dir":
                val = ApplicationRef("explorer")
            else:
                # Handle negations e.g. "open Calculator but don't open Chrome"
                # Strip out negated clauses first
                pos_text = text
                neg_match = re.search(r"\b(?:but\s+)?(?:don'?t|do\s+not|never)\s+(?:open|launch|run)\s+([a-zA-Z0-9_\s]+)", pos_text, re.I)
                if neg_match:
                    pos_text = pos_text[:neg_match.start()] + pos_text[neg_match.end():]

                val = parse_app_name(pos_text)
                if val in ("", "it", "that", "this", "them", "is", "installed", "on this machine"):
                    val = None

                # Slot-guided reference resolution fallback for pronoun / active topic / failure recovery
                if not val and reference_resolver and has_pronoun:
                    try:
                        res_slot = reference_resolver.resolve_for_slot(text, expected_slot_type="package" if slot_name == "package_name" or "install" in capability.id else "app", intent=capability.id)
                        if res_slot and res_slot.referent and res_slot.confidence == ReferenceConfidence.HIGH:
                            val = ApplicationRef(str(res_slot.referent))
                    except Exception:
                        pass

        elif slot_name in ("path", "source", "directory"):
            if resolved_referent and capability.category in (CapabilityCategory.FILE, CapabilityCategory.PHONE):
                val = str(resolved_referent)
            else:
                # For move/copy-style capabilities the "to <folder>" clause is the destination and must
                # never be taken as the source ("move the invoice to documents" is not "move Documents").
                src_text = text
                if slot_name in ("path", "source") and "destination" in (capability.required_slots + capability.optional_slots):
                    src_text = re.sub(r"\s+(?:to|into|onto|as)\s+.*$", "", text, flags=re.IGNORECASE)
                val = extract_folder_slot(src_text)
                if not val:
                    # Check windows absolute path e.g. C:/ or C:\
                    m = re.search(r'([a-zA-Z]:[\\/][^"\'<>|*?]+)', src_text)
                    if m:
                        val = m.group(1).strip()
                if not val and reference_resolver and has_pronoun:
                    try:
                        res_slot = reference_resolver.resolve_for_slot(text, expected_slot_type="file", intent=capability.id)
                        if res_slot and res_slot.referent and res_slot.confidence == ReferenceConfidence.HIGH:
                            val = str(res_slot.referent)
                    except Exception:
                        pass

        elif slot_name in ("destination", "new_name"):
            m_to = re.search(r"\b(?:to|into|as)\s+([a-zA-Z0-9_./\\-]+)", text, re.IGNORECASE)
            if m_to:
                cand = m_to.group(1).strip()
                cand_lower = cand.lower()
                if cand_lower in FOLDER_ALIASES:
                    val = FolderRef(FOLDER_ALIASES[cand_lower])
                elif cand_lower in ("phone", "android", "mobile", "cell"):
                    val = DeviceRef("phone")
                else:
                    val = cand

        elif slot_name in ("query", "semantic_query", "prompt"):
            # Clean common question / query preambles
            t = text
            t = re.sub(r"^(?:search the web for|search web for|search for|look up|explain to me|tell me about|explain|play on youtube|play|watch on youtube|watch)\s+", "", t, flags=re.IGNORECASE)
            t = re.sub(r"\s+(?:on youtube|online|on the web|in india|news)$", "", t, flags=re.IGNORECASE)
            val = t.strip() if t.strip() else None

        elif slot_name == "text":
            t = text
            t = re.sub(r"^(?:capture note|note down that|note down|save note|write down|type|dictate)\s*:?\s*", "", t, flags=re.IGNORECASE)
            val = t.strip() if t.strip() else None

        elif slot_name == "recipient":
            if "recipient" not in slots:
                resolved_t = resolve_correction(text)
                m_rec = re.search(r"\b(?:to|message)\s+([a-zA-Z0-9_\-\s]+?)(?:\s+(?:in|on)\s+whatsapp|\s+saying|\s+that|$)", resolved_t, re.I)
                if m_rec:
                    rec_cand = m_rec.group(1).strip()
                    if rec_cand and rec_cand.lower() not in ("whatsapp", "the", "a", "me"):
                        val = ContactRef(rec_cand)

        elif slot_name == "message":
            if "message" not in slots:
                m_msg = re.search(r"\b(?:saying|that|with message)\s+(.+)$", text, re.IGNORECASE)
                if m_msg:
                    val = m_msg.group(1).strip()

        elif slot_name == "action":
            if any(w in lowered for w in ("pause", "stop")):
                val = "pause"
            elif any(w in lowered for w in ("play", "resume")):
                val = "play"
            elif "next" in lowered:
                val = "next"
            elif "prev" in lowered:
                val = "prev"
            elif "mute" in lowered:
                val = "mute"
            elif "pair" in lowered or "qr" in lowered:
                val = "pair"
            elif "connect" in lowered:
                val = "connect"
            elif "disconnect" in lowered:
                val = "disconnect"

        elif slot_name == "minutes":
            val = parse_duration_seconds(lowered)
            if val:
                val = val // 60

        elif slot_name == "limit":
            m_lim = re.search(r"\b(\d+)\b", lowered)
            val = int(m_lim.group(1)) if m_lim else 100

        elif slot_name == "filter":
            if "urgent" in lowered:
                val = "urgent"
            elif "unread" in lowered or "new" in lowered:
                val = "unread"
            elif "all" in lowered or "recent" in lowered:
                val = "all"
            else:
                val = "needs_reply"

        if val is not None and slot_name not in slots:
            slots[slot_name] = val

    # Verify which required slots are missing
    missing_required = [s for s in capability.required_slots if s not in slots or slots[s] is None]

    return slots, missing_required
