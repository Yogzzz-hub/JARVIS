"""Stage 2.5 Tamil/Tanglish candidate corpus and admission checks.

This module builds *candidates*, never labels generated text as reviewed gold.
It does not read the original TEST or sealed HOLDOUT and invokes no tools.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.tanglish_stage24_ontology import ACTION_FAMILY

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "tanglish" / "generated" / "stage25"
SLOTS = frozenset("application contact recipient sender file folder file_type resource_type query message_content URL source destination device browser browser_tab ordinal count number quantity percentage date time date_range time_range attachment project workflow include_constraint exclude_constraint selected_resource quoted_resource spatial_relation".split())
SPEECH = frozenset("COMMAND NEGATED_COMMAND CORRECTION META_CONTROL QUESTION STATUS_QUERY CAPABILITY_QUERY STATEMENT HYPOTHETICAL CHAT ACKNOWLEDGEMENT CONFIRMATION AMBIGUOUS".split())
NON_EXEC = SPEECH - {"COMMAND", "CORRECTION", "META_CONTROL"}
COARSE = {act: ("UNCERTAIN" if act == "AMBIGUOUS" else "ACTION_ORIENTED" if act in {"COMMAND", "NEGATED_COMMAND", "CORRECTION", "META_CONTROL"} else "NON_ACTION") for act in SPEECH}
AFFORDANCES = {
    "SEND": {"MessageRef", "FileRef", "TextResource", "MediaRef"},
    "SHARE": {"MessageRef", "FileRef", "TextResource", "MediaRef"},
    "FORWARD": {"MessageRef", "FileRef", "MediaRef"},
    "RUN": {"ProjectRef", "ExecutableRef", "ScriptRef", "WorkflowRef"},
    "INCREASE": {"Volume", "Brightness", "NumericSetting"},
    "DECREASE": {"Volume", "Brightness", "NumericSetting"},
    "SET": {"Volume", "Brightness", "NumericSetting", "ModeRef"},
    "NAVIGATE": {"URLRef", "BrowserPageRef", "BrowserTabRef", "RouteRef"},
    "CONVERT": {"FileRef", "TextResource", "MediaRef"},
    "SWITCH": {"BrowserTabRef", "AppRef", "ModeRef"},
    "SELECT": {"FileRef", "BrowserTabRef", "MessageRef"},
    "CAPTURE": {"ScreenshotRef", "CameraRef"},
    "PLAY": {"AudioRef", "MediaRef"},
    "SHOW": {"FileRef", "MediaRef", "MessageRef", "MetricRef", "BrowserPageRef"},
    "LIST": {"FileRef", "FolderRef", "MessageRef", "CalendarEventRef"},
    "CHECK": {"ProjectRef", "FileRef", "AppRef", "MessageRef", "SystemStatusRef"},
    "RETRIEVE": {"DataRef", "FileRef", "MessageRef"},
    "PROVIDE": {"AnswerRef", "FileRef", "TextResource"},
    "SUMMARIZE": {"MessageRef", "TextResource", "FileRef"},
    "CREATE": {"CalendarEventRef", "FolderRef", "FileRef"},
    "UPLOAD": {"FileRef", "MediaRef"},
    "REPLACE": {"TextResource", "ContactRef"},
    "CHANGE": {"SettingRef", "TextResource", "ModeRef"},
    "READ": {"MessageRef", "FileRef", "TextResource"},
    "OPEN": {"FileRef", "AppRef", "URLRef", "MessageRef"},
    "RESTART": {"ProjectRef", "AppRef", "ServiceRef"},
    "CANCEL": {"WorkflowRef", "CalendarEventRef"},
    "COPY": {"FileRef", "FolderRef", "TextResource"},
    "MOVE": {"FileRef", "FolderRef"},
    "DELETE": {"FileRef", "FolderRef", "MessageRef"},
    "SEARCH": {"WebQueryRef", "FileRef", "MessageRef", "ProjectRef"},
    "CLOSE": {"AppRef", "FileRef", "BrowserTabRef"},
    "INSPECT": {"ProjectRef", "FileRef", "MessageRef"},
    "VERIFY": {"ProjectRef", "FileRef", "MessageRef"},
    "FIND": {"FileRef", "MessageRef", "WebQueryRef"},
    "EXPLAIN": {"AnswerRef", "TextResource", "ProjectRef"},
    "REPLY": {"MessageRef"},
    "WRITE": {"TextResource", "FileRef"},
    "ENTER": {"TextResource", "SettingRef"},
    "DOWNLOAD": {"FileRef", "MediaRef"},
    "ATTACH": {"FileRef", "MediaRef"},
    "RENAME": {"FileRef", "FolderRef"},
    "SAVE": {"FileRef", "TextResource"},
    "INSTALL": {"AppRef"},
    "UNINSTALL": {"AppRef"},
    "START": {"ProjectRef", "AppRef", "ServiceRef"},
    "STOP": {"ProjectRef", "AppRef", "ServiceRef"},
    "PAUSE": {"ProjectRef", "MediaRef", "WorkflowRef"},
    "RESUME": {"ProjectRef", "MediaRef", "WorkflowRef"},
    "MUTE": {"Volume", "MediaRef"},
    "UNMUTE": {"Volume", "MediaRef"},
    "FILTER": {"FileRef", "MessageRef"},
    "SORT": {"FileRef", "MessageRef"},
    "COMPARE": {"FileRef", "TextResource"},
    "CLICK": {"UIElementRef"},
    "CALL": {"ContactRef"},
}


def affordance(action: str, object_type: str | None, context: dict | None = None) -> str:
    if not action or not object_type:
        return "CONTEXT_REQUIRED"
    allowed = AFFORDANCES.get(action)
    if allowed is None:
        return "CONTEXT_REQUIRED"
    if object_type in allowed:
        return "VALID"
    if action == "RUN" and object_type == "FolderRef" and (context or {}).get("folder_has_project"):
        return "VALID"
    if action == "RUN" and object_type in {"FolderRef", "BrowserTabRef"}:
        return "CONTEXT_REQUIRED"
    return "INVALID"


def span(text: str, surface: str, value: Any, slot: str, *, occurrence: int = 0) -> dict:
    matches = list(re.finditer(re.escape(surface), text, re.IGNORECASE))
    if occurrence >= len(matches):
        raise ValueError(f"Missing {slot}={surface!r} in {text!r}")
    m = matches[occurrence]
    return {"slot": slot, "start": m.start(), "end": m.end(), "surface": text[m.start():m.end()], "value": value, "source": "TEXT"}


@dataclass(frozen=True)
class Pair:
    family: str
    tanglish: str
    tamil: str
    speech: str
    action: str | None
    object_type: str | None
    # Each tuple is (slot, Tanglish surface, Tamil surface, normalized value).
    slots: tuple[tuple[str, str, str, Any], ...] = ()
    negated: bool = False
    context_required: bool = False
    exclude: str | None = None
    superseded: tuple[str, str, str, Any] | None = None
    notes: str = ""
    working_context: dict | None = None
    context_key: str = "selected_resource"


# Hand-authored seed meanings. The Tamil realizations still need independent
# native-speaker review before Q2/Q3 admission. No public comments become labels.
PAIRS = [
    Pair("send_pdf_direct", "Naveen ku PDF anuppu", "நவீனுக்கு PDF-ஐ அனுப்பு", "COMMAND", "SEND", "FileRef", (("recipient", "Naveen", "நவீனு", "Naveen"), ("file_type", "PDF", "PDF", "PDF"))),
    Pair("send_pdf_negated", "Naveen ku PDF anuppadha", "நவீனுக்கு PDF-ஐ அனுப்பாதே", "NEGATED_COMMAND", "SEND", "FileRef", (("recipient", "Naveen", "நவீனு", "Naveen"), ("file_type", "PDF", "PDF", "PDF")), True),
    Pair("send_pdf_status", "Naveen ku PDF anupitiya?", "நவீனுக்கு PDF-ஐ அனுப்பினாயா?", "STATUS_QUERY", "SEND", "FileRef", (("recipient", "Naveen", "நவீனு", "Naveen"), ("file_type", "PDF", "PDF", "PDF"))),
    Pair("send_pdf_capability", "PDF anupa mudiyuma?", "PDF-ஐ அனுப்ப முடியுமா?", "CAPABILITY_QUERY", "SEND", "FileRef", (("file_type", "PDF", "PDF", "PDF"),)),
    Pair("send_pdf_statement", "Naveen PDF anupitan", "நவீன் PDF-ஐ அனுப்பினான்", "STATEMENT", "SEND", "FileRef", (("sender", "Naveen", "நவீன்", "Naveen"), ("file_type", "PDF", "PDF", "PDF"))),
    Pair("send_pdf_hypothetical", "PDF anupuna enna aagum?", "PDF-ஐ அனுப்பினால் என்ன ஆகும்?", "HYPOTHETICAL", "SEND", "FileRef", (("file_type", "PDF", "PDF", "PDF"),)),
    Pair("send_pdf_correct", "Arun ku anuppu... illa Naveen ku", "அருணுக்கு அனுப்பு... இல்லை நவீனுக்கு", "CORRECTION", "SEND", "MessageRef", (("recipient", "Naveen", "நவீனு", "Naveen"),), superseded=("recipient", "Arun", "அருணு", "Arun")),
    Pair("send_pdf_context", "atha Arun ku anuppu", "அதை அருணுக்கு அனுப்பு", "COMMAND", "SEND", "FileRef", (("recipient", "Arun", "அருணு", "Arun"),), context_required=True, working_context={"selected_resource": {"type": "FileRef", "selector": "second PDF"}, "previous_turns": {"TANGLISH": ["Naveen oda PDFs kaatu", "second one"], "TAMIL": ["நவீன் அனுப்பிய PDF-களை காட்டு", "இரண்டாவது"]}}),
    Pair("send_pdf_yesterday", "nethu Naveen anupuna second PDF ah Arun ku anuppu, screenshot venam", "நேற்று நவீன் அனுப்பிய இரண்டாவது PDF-ஐ அருணுக்கு அனுப்பு, screenshot வேண்டாம்", "COMMAND", "SEND", "FileRef", (("sender", "Naveen", "நவீன்", "Naveen"), ("ordinal", "second", "இரண்டாவது", 2), ("file_type", "PDF", "PDF", "PDF"), ("recipient", "Arun", "அருணு", "Arun"), ("date", "nethu", "நேற்று", "yesterday"), ("exclude_constraint", "screenshot", "screenshot", "screenshot")), exclude="screenshot"),
    Pair("send_file_share", "Naveen kitta file kudu", "நவீனுக்கு கோப்பை கொடு", "COMMAND", "SEND", "FileRef", (("recipient", "Naveen", "நவீனு", "Naveen"), ("resource_type", "file", "கோப்பை", "file"))),
    Pair("provide_answer", "answer kudu", "பதில் கொடு", "COMMAND", "PROVIDE", "AnswerRef", (("resource_type", "answer", "பதில்", "answer"),)),
    Pair("summary_messages", "Naveen chat summary kudu", "நவீன் உரையாடலைச் சுருக்கிச் சொல்லு", "COMMAND", "SUMMARIZE", "MessageRef", (("contact", "Naveen", "நவீன்", "Naveen"),)),
    Pair("convert_pdf", "PDF ah Word ku maathu", "PDF-ஐ Word கோப்பாக மாற்று", "COMMAND", "CONVERT", "FileRef", (("file_type", "PDF", "PDF", "PDF"), ("destination", "Word", "Word", "Word"))),
    Pair("switch_tab", "second tab ku maathu", "இரண்டாவது டேப்க்கு மாறு", "COMMAND", "SWITCH", "BrowserTabRef", (("ordinal", "second", "இரண்டாவது", 2), ("browser_tab", "tab", "டேப்", "tab"))),
    Pair("set_volume", "volume 50 ku maathu", "ஒலியை 50க்கு மாற்று", "COMMAND", "SET", "Volume", (("number", "50", "50", 50),)),
    Pair("replace_contact", "Arun ah Naveen nu maathu", "அருணை நவீனாக மாற்று", "COMMAND", "REPLACE", "ContactRef", (("contact", "Arun", "அருணை", "Arun"), ("recipient", "Naveen", "நவீனா", "Naveen"))),
    Pair("change_style", "sentence ah professional ah maathu", "வாக்கியத்தை தொழில்முறையாக மாற்று", "COMMAND", "CHANGE", "TextResource", (("resource_type", "sentence", "வாக்கியத்தை", "sentence"),)),
    Pair("select_file", "second file eduthu", "இரண்டாவது கோப்பை எடு", "COMMAND", "SELECT", "FileRef", (("ordinal", "second", "இரண்டாவது", 2), ("resource_type", "file", "கோப்பை", "file"))),
    Pair("capture_screen", "screenshot eduthu", "திரைப் படம் எடு", "COMMAND", "CAPTURE", "ScreenshotRef", (("resource_type", "screenshot", "திரைப் படம்", "screenshot"),)),
    Pair("retrieve_data", "database la data eduthu", "தரவுத்தளத்திலிருந்து தரவை எடு", "COMMAND", "RETRIEVE", "DataRef", (("source", "database", "தரவுத்தளத்திலிருந்து", "database"),)),
    Pair("play_song", "song podu", "பாட்டு போடு", "COMMAND", "PLAY", "AudioRef", (("resource_type", "song", "பாட்டு", "song"),)),
    Pair("set_volume_podu", "volume 50 podu", "ஒலியை 50க்கு வை", "COMMAND", "SET", "Volume", (("number", "50", "50", 50),)),
    Pair("create_calendar", "calendar la meeting podu", "காலெண்டரில் சந்திப்பு போடு", "COMMAND", "CREATE", "CalendarEventRef", (("destination", "calendar", "காலெண்டரில்", "calendar"),)),
    Pair("upload_file", "file upload podu", "கோப்பை பதிவேற்று", "COMMAND", "UPLOAD", "FileRef", (("resource_type", "file", "கோப்பை", "file"),)),
    Pair("list_files", "files kaatu", "கோப்புகளைக் காட்டு", "COMMAND", "LIST", "FileRef", (("resource_type", "files", "கோப்புகளைக்", "file"),)),
    Pair("show_photo", "photo kaatu", "படத்தைக் காட்டு", "COMMAND", "SHOW", "MediaRef", (("resource_type", "photo", "படத்தை", "photo"),)),
    Pair("show_message", "latest message kaatu", "கடைசி செய்தியைக் காட்டு", "COMMAND", "SHOW", "MessageRef", (("resource_type", "message", "செய்தியை", "message"),)),
    Pair("check_backend", "backend run aagudha paaru", "பேக்கெண்ட் ஓடுதா பாரு", "COMMAND", "CHECK", "ProjectRef", (("project", "backend", "பேக்கெண்ட்", "backend"),)),
    Pair("read_message", "message ah paaru", "செய்தியைப் பாரு", "COMMAND", "READ", "MessageRef", (("resource_type", "message", "செய்தியை", "message"),)),
    Pair("open_chrome", "Chrome open pannu", "Chrome-ஐ திற", "COMMAND", "OPEN", "AppRef", (("application", "Chrome", "Chrome", "Chrome"),)),
    Pair("restart_backend", "backend restart pannu", "பேக்கெண்டை மறுதொடக்கம் செய்", "COMMAND", "RESTART", "ProjectRef", (("project", "backend", "பேக்கெண்டை", "backend"),)),
    Pair("run_project", "project ah run pannu", "திட்டத்தை இயக்கு", "COMMAND", "RUN", "ProjectRef", (("project", "project", "திட்டத்தை", "project"),)),
    Pair("volume_decrease", "volume konjam kammi pannu", "ஒலியை கொஞ்சம் குறை", "COMMAND", "DECREASE", "Volume", (("quantity", "konjam", "கொஞ்சம்", "small_relative"),)),
    Pair("volume_increase", "volume konjam adhigam pannu", "ஒலியை கொஞ்சம் கூட்டு", "COMMAND", "INCREASE", "Volume", (("quantity", "konjam", "கொஞ்சம்", "small_relative"),)),
    Pair("negate_open", "atha open pannadha", "அதை திறக்காதே", "NEGATED_COMMAND", "OPEN", "FileRef", negated=True, context_required=True, working_context={"selected_resource": {"type": "FileRef", "selector": "current selection"}, "previous_turns": {"TANGLISH": ["file kaatu"], "TAMIL": ["கோப்பைக் காட்டு"]}}),
    Pair("polite_send_ambiguous", "PDF anupa mudiyuma?", "PDF-ஐ அனுப்ப முடியுமா?", "AMBIGUOUS", "SEND", "FileRef", (("file_type", "PDF", "PDF", "PDF"),)),
]


def build_row(pair: Pair, language: str) -> dict:
    text = pair.tanglish if language == "TANGLISH" else pair.tamil
    idx = 1 if language == "TANGLISH" else 2
    slots = [span(text, item[idx], item[3], item[0]) for item in pair.slots]
    if pair.context_required and pair.working_context:
        slot_name = {"active_app": "application", "current_project": "project", "browser_tab": "browser_tab"}.get(pair.context_key, "selected_resource")
        slots.append({"slot": slot_name, "start": None, "end": None, "surface": None, "value": pair.working_context[pair.context_key], "source": "CONTEXT", "reference": pair.context_key})
    values = {s["slot"]: s["value"] for s in slots}
    superseded = None
    if pair.superseded:
        old = pair.superseded
        superseded = span(text, old[idx], old[3], old[0])
        superseded["status"] = "SUPERSEDED"
    active = pair.speech in {"COMMAND", "CORRECTION", "META_CONTROL"} and not pair.negated
    frame = {
        "speech_act": pair.speech,
        "coarse_speech_act": COARSE[pair.speech],
        "action_family": ACTION_FAMILY[pair.action] if pair.action else None,
        "action_concept": pair.action,
        "domain": "GENERAL",
        "object_type": pair.object_type,
        "object_ref": (pair.working_context or {}).get(pair.context_key),
        "target": None,
        "recipient": {"type": "ContactRefCandidate", "name": values["recipient"]} if "recipient" in values else None,
        "sender": {"type": "ContactRefCandidate", "name": values["sender"]} if "sender" in values else None,
        "source": values.get("source"),
        "destination": values.get("destination"),
        "content": values.get("message_content"),
        "query": values.get("query"),
        "temporal": {k: values[k] for k in ("date", "time", "date_range", "time_range") if k in values},
        "quantity": values.get("quantity"),
        "ordinal": values.get("ordinal"),
        "attributes": {},
        "slots": slots,
        "negations": [{"scope": "ACTION"}] if pair.negated else [],
        "corrections": [{"superseded": superseded, "active_slot": pair.superseded[0]}] if superseded else [],
        "references": [{"kind": pair.context_key, "source": "CONTEXT", "text_span": None}] if pair.context_required else [],
        "context_refs": [pair.context_key] if pair.context_required else [],
        "include_constraints": [s["value"] for s in slots if s["slot"] == "include_constraint"],
        "exclude_constraints": [pair.exclude] if pair.exclude else [s["value"] for s in slots if s["slot"] == "exclude_constraint"],
        "should_execute": active,
        "context_required": pair.context_required,
        "confidence": None,
    }
    context = None
    if pair.working_context:
        context = {**pair.working_context, "previous_turns": pair.working_context["previous_turns"][language]}
    isolation_group = "send_pdf_minimal_pair" if pair.family.startswith("send_pdf_") else "volume_polysemy" if pair.family.startswith("volume_") or pair.family == "set_volume_podu" else pair.family
    return {"id": hashlib.sha256((pair.family + ":" + language).encode()).hexdigest()[:16], "family": pair.family, "isolation_group": isolation_group, "language": language, "text": text, "working_context": context, "frame": frame, "quality": "Q1", "provenance": "authored_stage25_candidate", "review_status": "UNREVIEWED"}


def validate_row(row: dict) -> list[str]:
    errors = []
    text, frame = row["text"], row["frame"]
    lang = row["language"]
    if lang not in {"TANGLISH", "TAMIL"} or not text.strip():
        errors.append("invalid_language_or_empty")
    has_tamil = bool(re.search(r"[\u0b80-\u0bff]", text))
    if (lang == "TAMIL") != has_tamil:
        errors.append("script_mismatch")
    if frame["speech_act"] not in SPEECH:
        errors.append("invalid_speech_act")
    elif frame.get("coarse_speech_act") != COARSE[frame["speech_act"]]:
        errors.append("invalid_coarse_speech_act")
    if ACTION_FAMILY.get(frame["action_concept"]) != frame["action_family"]:
        errors.append("invalid_action_family")
    if frame["action_concept"] is None:
        if frame["speech_act"] not in {"QUESTION", "CHAT", "ACKNOWLEDGEMENT", "CONFIRMATION", "AMBIGUOUS"} or frame["should_execute"]:
            errors.append("missing_action_for_actionable_speech")
    else:
        result = affordance(frame["action_concept"], frame["object_type"])
        if result == "INVALID":
            errors.append("invalid_affordance")
        if result == "CONTEXT_REQUIRED" and not frame["context_required"]:
            errors.append("unresolved_affordance")
    if frame["should_execute"] and (frame["speech_act"] in NON_EXEC or frame["negations"]):
        errors.append("unsafe_execution_label")
    if frame["speech_act"] == "NEGATED_COMMAND" and (not frame["negations"] or frame["should_execute"]):
        errors.append("negation_inconsistent")
    if frame["speech_act"] == "CORRECTION" and not frame["corrections"]:
        errors.append("correction_missing")
    if frame["context_required"] and not frame["references"]:
        errors.append("context_reference_missing")
    if frame["context_required"] and not all((row.get("working_context") or {}).get(key) for key in frame.get("context_refs", [])):
        errors.append("context_not_grounded")
    for slot in frame["slots"]:
        if slot["slot"] not in SLOTS:
            errors.append("unknown_slot")
        if slot["source"] == "TEXT":
            start, end = slot["start"], slot["end"]
            if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(text) or text[start:end] != slot["surface"]:
                errors.append("broken_span")
        elif slot["source"] == "CONTEXT":
            if slot.get("start") is not None or slot.get("end") is not None or slot.get("surface") is not None or not slot.get("reference"):
                errors.append("fabricated_context_span")
            if slot.get("reference") not in (row.get("working_context") or {}):
                errors.append("unresolved_context_slot")
        else:
            errors.append("invalid_slot_source")
        if slot["value"] is None:
            errors.append("invalid_slot_value")
    for role in ("recipient", "sender"):
        found = [s["value"] for s in frame["slots"] if s["slot"] == role]
        encoded = frame.get(role)
        if found and encoded != {"type": "ContactRefCandidate", "name": found[-1]}:
            errors.append("typed_reference_inconsistent")
    for role, frame_key in (("include_constraint", "include_constraints"), ("exclude_constraint", "exclude_constraints")):
        annotated = [s["value"] for s in frame["slots"] if s["slot"] == role]
        if annotated and not all(value in frame[frame_key] for value in annotated):
            errors.append("constraint_slot_inconsistent")
    for correction in frame["corrections"]:
        old = correction["superseded"]
        if not old or text[old["start"]:old["end"]] != old["surface"]:
            errors.append("broken_correction_span")
        if not any(s["slot"] == correction["active_slot"] and s["start"] > old["start"] for s in frame["slots"]):
            errors.append("correction_not_superseded")
        if any(s["slot"] == correction["active_slot"] and s["value"] == old["value"] for s in frame["slots"]):
            errors.append("correction_not_changed")
    for ref in frame["references"]:
        if ref["source"] == "CONTEXT" and ref["text_span"] is not None:
            errors.append("fabricated_context_span")
    asr = row.get("asr_pair")
    if asr:
        if not asr.get("clean_text") or not asr.get("noisy_text") or not asr.get("clean_frame") or not asr.get("noisy_frame"):
            errors.append("incomplete_asr_pair")
        elif asr.get("meaning_preserved"):
            if asr["noisy_text"] != text or asr["noisy_frame"] != frame:
                errors.append("asr_child_mismatch")
            safety = ("speech_act", "action_family", "action_concept", "object_type", "recipient", "sender", "source", "destination", "temporal", "quantity", "ordinal", "negations", "include_constraints", "exclude_constraints", "corrections", "references", "context_refs", "should_execute", "context_required")
            if any(asr["clean_frame"].get(k) != asr["noisy_frame"].get(k) for k in safety):
                errors.append("meaning_changing_asr_positive")
            if [(s["slot"], s["value"]) for s in asr["clean_frame"].get("slots", [])] != [(s["slot"], s["value"]) for s in asr["noisy_frame"].get("slots", [])]:
                errors.append("meaning_changing_asr_positive")
    return errors


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, rejected_build = [], []
    for pair in PAIRS:
        for lang in ("TANGLISH", "TAMIL"):
            try:
                rows.append(build_row(pair, lang))
            except (ValueError, KeyError) as exc:
                rejected_build.append({"family": pair.family, "language": lang, "reasons": ["build_error"], "detail": str(exc)})
    # Identical utterances with conflicting frames are quarantined, never used.
    by_text: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        by_text[(row["language"], row["text"].casefold())].append(row)
    collisions = {k for k, v in by_text.items() if len({json.dumps(r["frame"], sort_keys=True, ensure_ascii=False) for r in v}) > 1}
    accepted, rejected = [], list(rejected_build)
    for row in rows:
        reasons = validate_row(row)
        if (row["language"], row["text"].casefold()) in collisions:
            reasons.append("conflicting_identical_text")
        (rejected if reasons else accepted).append({**row, **({"reasons": reasons} if reasons else {})})
    for name, content in (("candidates.jsonl", accepted), ("rejected.jsonl", rejected)):
        (OUT / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in content), encoding="utf-8")
    grouped = defaultdict(dict)
    for row in accepted:
        grouped[row["family"]][row["language"]] = row
    relations = []
    for family, by_language in grouped.items():
        if set(by_language) == {"TANGLISH", "TAMIL"}:
            relations.append({"relation": "POSITIVE_CROSS_SCRIPT", "family": family, "left_id": by_language["TANGLISH"]["id"], "right_id": by_language["TAMIL"]["id"], "quality": "Q1", "review_status": "UNREVIEWED"})
    (OUT / "contrastive_candidates.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in relations), encoding="utf-8")
    (OUT / "manual_audit_queue.jsonl").write_text("".join(json.dumps({"row_id": r["id"], "language": r["language"], "text": r["text"], "frame": r["frame"], "reviewer": None, "reviewed_utc": None, "annotation_error": None, "critical_semantic_error": None, "naturalness": None}, ensure_ascii=False) + "\n" for r in accepted), encoding="utf-8")
    source_manifest = ROOT / "data" / "tanglish" / "dataset_manifest.json"
    summary = {
        "candidate_rows": len(rows) + len(rejected_build), "schema_valid_unreviewed": len(accepted), "rejected": len(rejected),
        "rejection_reasons": dict(Counter(reason for r in rejected for reason in r["reasons"])),
        "language": dict(Counter(r["language"] for r in accepted)),
        "speech_act": dict(Counter(r["frame"]["speech_act"] for r in accepted)),
        "action_concept": dict(Counter(r["frame"]["action_concept"] for r in accepted)),
        "slot": dict(Counter(s["slot"] for r in accepted for s in r["frame"]["slots"])),
        "family_count": len({r["family"] for r in accepted}),
        "cross_script_positive_candidates": len(relations),
        "quality_q2_q3": 0,
        "training_admitted": 0,
        "manual_audit_required": 750,
        "manual_audit_completed": 0,
        "target_gold_rows": 30000,
        "test_holdout_accessed": False,
        "source_manifest_sha256": hashlib.sha256(source_manifest.read_bytes()).hexdigest(),
        "candidate_sha256": hashlib.sha256((OUT / "candidates.jsonl").read_bytes()).hexdigest(),
        "rejected_sha256": hashlib.sha256((OUT / "rejected.jsonl").read_bytes()).hexdigest(),
    }
    (OUT / "manifest.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
