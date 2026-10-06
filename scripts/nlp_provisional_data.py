"""Separate AI-assisted development artifacts; never edit frozen or human data."""
from __future__ import annotations
import copy
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from scripts.stage25_admit import read_jsonl
from scripts.stage25_freeze import FILES, MANIFEST, verify
from scripts.stage25_gold_data import OUT, ROOT, COARSE, SLOTS
from scripts.tanglish_stage24_ontology import ACTION_FAMILY
from scripts.unified_nlp_audit import AuditStore

DEST = ROOT / "data/nlp_provisional"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def immutable(path, raw):
    path = Path(path)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("Refusing to replace locked artifact: " + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)


def normalize(text):
    # Deliberately preserve case, punctuation, identifiers and lexical order.
    return " ".join(text.split())


def authored_rows():
    # Authored semantic task families, not inference dictionaries or phrase patches.
    # Each tuple: family/domain/action/resource/English object/Tanglish object/slot/capability.
    specs = [
        ("app_launch", "PC", "OPEN", "AppRef", "Chrome", "Chrome", "application", "app.open"),
        ("app_close", "PC", "CLOSE", "AppRef", "Notepad", "Notepad", "application", "app.close"),
        ("file_open", "FILES", "OPEN", "FileRef", "design.pdf", "design.pdf", "file", "file.open"),
        ("file_delete", "FILES", "DELETE", "FileRef", "old_notes.txt", "old_notes.txt", "file", "file.delete"),
        ("file_find", "FILES", "FIND", "FileRef", "budget.xlsx", "budget.xlsx", "file", "file.find"),
        ("folder_list", "FILES", "LIST", "FolderRef", "Downloads", "Downloads", "folder", "file.list"),
        ("file_copy", "FILES", "COPY", "FileRef", "config.yaml", "config.yaml", "file", "file.copy"),
        ("file_move", "FILES", "MOVE", "FileRef", "slides.pptx", "slides.pptx", "file", "file.move"),
        ("file_rename", "FILES", "RENAME", "FileRef", "draft.md", "draft.md", "file", "file.rename"),
        ("file_summary", "FILES", "SUMMARIZE", "FileRef", "paper.pdf", "paper.pdf", "file", None),
        ("web_search", "BROWSER", "SEARCH", "WebQueryRef", "Docker networking", "Docker networking", "query", "rag.search_web"),
        ("url_open", "BROWSER", "NAVIGATE", "URLRef", "https://github.com/example/repo", "https://github.com/example/repo", "URL", "browser.open_url"),
        ("project_run", "IDE", "RUN", "ProjectRef", "FastAPI backend", "FastAPI backend", "project", "workflow.run_project"),
        ("project_status", "IDE", "CHECK", "ProjectRef", "Next.js frontend", "Next.js frontend", "project", None),
        ("project_restart", "IDE", "RESTART", "ProjectRef", "React dashboard", "React dashboard", "project", None),
        ("project_inspect", "IDE", "INSPECT", "ProjectRef", "Postgres service", "Postgres service", "project", None),
        ("automation_run", "AUTOMATIONS", "RUN", "WorkflowRef", "daily backup", "daily backup", "workflow", "automation.run"),
        ("automation_stop", "AUTOMATIONS", "STOP", "WorkflowRef", "nightly sync", "nightly sync", "workflow", None),
        ("voice_mute", "CONTROL", "MUTE", "Volume", "microphone", "microphone", "device", None),
        ("voice_resume", "CONTROL", "RESUME", "ServiceRef", "voice listener", "voice listener", "resource_type", None),
        ("system_check", "PC", "CHECK", "SystemStatusRef", "system memory", "system memory", "resource_type", "system.info"),
        ("screen_capture", "PC", "CAPTURE", "ScreenshotRef", "screen", "screen", "resource_type", "windows.screenshot"),
        ("gmail_read", "GMAIL", "READ", "MessageRef", "unread Gmail messages", "Gmail unread mails", "resource_type", "google.read_emails"),
        ("gmail_find", "GMAIL", "FIND", "MessageRef", "recruiter email", "recruiter mail", "query", "google.read_emails"),
        ("gmail_send", "GMAIL", "SEND", "MessageRef", "status email", "status mail", "message_content", "google.gmail_send"),
        ("gmail_summary", "GMAIL", "SUMMARIZE", "MessageRef", "Gmail thread", "Gmail thread", "resource_type", None),
        ("whatsapp_read", "WHATSAPP", "READ", "MessageRef", "latest WhatsApp messages", "WhatsApp latest msgs", "resource_type", "whatsapp.read"),
        ("whatsapp_send", "WHATSAPP", "SEND", "MessageRef", "meeting update", "meeting update", "message_content", "whatsapp.send"),
        ("whatsapp_reply", "WHATSAPP", "REPLY", "MessageRef", "WhatsApp message", "WhatsApp msg", "resource_type", "whatsapp.send"),
        ("whatsapp_summary", "WHATSAPP", "SUMMARIZE", "MessageRef", "WhatsApp conversation", "WhatsApp chat", "resource_type", None),
        ("calendar_create", "CALENDAR", "CREATE", "CalendarEventRef", "calendar appointment", "calendar appointment", "resource_type", "google.calendar_create"),
        ("calendar_cancel", "CALENDAR", "CANCEL", "CalendarEventRef", "calendar appointment", "calendar appointment", "resource_type", None),
        ("drive_find", "DRIVE", "FIND", "FileRef", "Drive presentation", "Drive presentation", "query", "google.drive_search"),
        ("drive_upload", "DRIVE", "UPLOAD", "FileRef", "quarterly.csv", "quarterly.csv", "file", "google.drive_upload"),
        ("drive_download", "DRIVE", "DOWNLOAD", "FileRef", "Drive archive.zip", "Drive archive.zip", "file", "google.drive_download"),
        ("media_play", "MEDIA", "PLAY", "MediaRef", "demo.mp4", "demo.mp4", "file", None),
        ("media_pause", "MEDIA", "PAUSE", "MediaRef", "music player", "music player", "resource_type", None),
        ("volume_set", "PC", "SET", "Volume", "volume", "volume", "resource_type", "windows.volume_set"),
        ("file_share", "FILES", "SHARE", "FileRef", "architecture.pdf", "architecture.pdf", "file", "whatsapp.send"),
        ("attachment_forward", "WHATSAPP", "FORWARD", "FileRef", "invoice.pdf", "invoice.pdf", "file", "whatsapp.send"),
    ]
    for family, domain, action, resource, en, mixed, slot, capability in specs:
        # All variants, names, scripts and mild noise from a task stay together.
        for state in ("COMMAND", "NEGATED_COMMAND", "STATUS_QUERY", "CORRECTION", "REFERENCE"):
            for language in ("ENGLISH", "MIXED"):
                obj = en if language == "ENGLISH" else mixed
                for style in range(3):
                    recipient = "Leela" if action in {"SEND", "SHARE", "FORWARD", "REPLY"} else None
                    verb = action.lower()
                    base = f"{verb} {obj}" if language == "ENGLISH" else f"{obj} {verb} pannu"
                    if recipient:
                        base += f" to {recipient}" if language == "ENGLISH" else f" {recipient} ku"
                    if state == "NEGATED_COMMAND":
                        base = "do not " + base if language == "ENGLISH" else base.replace("pannu", "pannadha")
                    elif state == "STATUS_QUERY":
                        base = f"did you {verb} {obj}?" if language == "ENGLISH" else f"{obj} {verb} aacha?"
                    elif state == "CORRECTION":
                        if recipient:
                            base = base.replace(recipient, "Kiran") + (f", actually to {recipient}" if language == "ENGLISH" else f", illa {recipient} ku")
                        else:
                            old_action = "read" if action == "OPEN" else "open"
                            base = f"{old_action} {obj}, no {verb} it only" if language == "ENGLISH" else f"{obj} {old_action} venam, {verb} mattum pannu"
                    elif state == "REFERENCE":
                        base = f"{verb} that" if language == "ENGLISH" else f"atha {verb} pannu"
                    text = ("please " + base if style == 1 and language == "ENGLISH" else "bro " + base if style == 1 else base + (" when you have a moment" if language == "ENGLISH" else " enaku" ) if style == 2 else base)
                    speech = "COMMAND" if state == "REFERENCE" else state
                    slots = []
                    if obj in text:
                        left = text.index(obj)
                        slots.append({"slot":slot,"start":left,"end":left+len(obj),"surface":obj,"value":obj,"source":"TEXT"})
                    if recipient and recipient in text:
                        left = text.rindex(recipient)
                        slots.append({"slot":"recipient","start":left,"end":left+len(recipient),"surface":recipient,"value":recipient,"source":"TEXT"})
                    correction = []
                    if state == "CORRECTION":
                        if recipient:
                            left = text.index("Kiran")
                            correction = [{"superseded":{"slot":"recipient","start":left,"end":left+5,"surface":"Kiran","value":"Kiran","source":"TEXT","status":"SUPERSEDED"},"active_slot":"recipient"}]
                        else:
                            correction = [{"superseded_action":"READ" if action=="OPEN" else "OPEN","active_action":action}]
                    frame = {"domain":domain,"action_concept":action,"action_family":ACTION_FAMILY[action],"speech_act":speech,"coarse_speech_act":COARSE[speech],"object_type":resource,"object_ref":None,"target":None,"sender":None,"recipient":{"type":"ContactRefCandidate","name":recipient} if recipient and state != "REFERENCE" else None,"source":None,"destination":None,"content":obj if slot=="message_content" and state != "REFERENCE" else None,"query":obj if slot=="query" and state != "REFERENCE" else None,"temporal":{},"quantity":None,"ordinal":None,"attributes":{},"slots":slots,"negations":[{"scope":"ACTION"}] if state=="NEGATED_COMMAND" else [],"corrections":correction,"references":[{"kind":"selected_resource","source":"TEXT","text_span":None,"type":resource}] if state=="REFERENCE" else [],"context_refs":["selected_resource"] if state=="REFERENCE" else [],"include_constraints":[],"exclude_constraints":[],"should_execute":state in {"COMMAND","CORRECTION","REFERENCE"},"context_required":state=="REFERENCE","confidence":None}
                    context = {"selected_resource":{"type":resource,"name":obj}} if state=="REFERENCE" else None
                    identifier = hashlib.sha256((family+state+language+str(style)).encode()).hexdigest()[:20]
                    row = {"id":"authored_"+identifier,"text":text,"raw_text":text,"normalized_text":normalize(text),"language":language,"frame":frame,"working_context":context,"family":"authored:"+family,"provenance":"SYNTHETIC_AUTHORED_PROVISIONAL","capability_gold":capability}
                    yield row
                    if style == 0:
                        noisy = "um " + text.replace("please ", "").replace(" pannu", " panu")
                        child = copy.deepcopy(row)
                        child.update(id=row["id"]+"_asr",text=noisy,raw_text=noisy,normalized_text=normalize(noisy),language="ASR",base_language=language)
                        # Prefix changes all character spans by three. No names or identifiers changed.
                        for sl in child["frame"]["slots"]:
                            sl["start"] += 3; sl["end"] += 3
                        for c in child["frame"]["corrections"]:
                            if "superseded" in c:
                                c["superseded"]["start"] += 3; c["superseded"]["end"] += 3
                        # Light-verb spelling variation may shorten text before a recipient.
                        for sl in child["frame"]["slots"]:
                            pos = noisy.rfind(sl["surface"])
                            sl["start"],sl["end"] = pos,pos+len(sl["surface"])
                        for c in child["frame"]["corrections"]:
                            if "superseded" in c:
                                old=c["superseded"];pos=noisy.index(old["surface"]);old["start"],old["end"]=pos,pos+len(old["surface"])
                        yield child
    for family, texts in {
        "unclear_object": ("do something with it", "atha ethavathu pannu"),
        "unsupported_finance": ("predict tomorrow's stock price exactly", "stock exact future price sollu"),
        "unsupported_physical": ("repair the kitchen sink", "kitchen sink repair pannu"),
        "unclear_recipient": ("send it to the person", "yaaruko atha anupu"),
        "casual_weather": ("the weather was lovely yesterday", "nethu weather nalla irunthuchu"),
        "acknowledgement": ("okay thanks", "seri nandri"),
        "unsupported_time": ("make time go backwards", "time reverse pannu"),
        "vague_reference": ("the other one maybe", "innoru one pola"),
    }.items():
        for i,text in enumerate(texts):
            frame={k:None for k in ("action_concept","action_family","object_type","object_ref","target","recipient","sender","source","destination","content","query","quantity","ordinal","confidence")}
            frame.update(domain="GENERAL",speech_act="AMBIGUOUS",coarse_speech_act="UNCERTAIN",temporal={},attributes={},slots=[],negations=[],corrections=[],references=[],context_refs=[],include_constraints=[],exclude_constraints=[],should_execute=False,context_required=False)
            yield {"id":"unknown_"+family+str(i),"text":text,"raw_text":text,"normalized_text":normalize(text),"language":"ENGLISH" if i==0 else "MIXED","frame":frame,"working_context":None,"family":"unknown:"+family,"provenance":"SYNTHETIC_AUTHORED_PROVISIONAL","capability_gold":None}


def split_rows(rows):
    """Union isolation/construction families and exact normalized duplicates."""
    parent={}
    def find(x):
        parent.setdefault(x,x)
        if parent[x]!=x: parent[x]=find(parent[x])
        return parent[x]
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[max(a,b)]=min(a,b)
    for row in rows:
        family=row["family"]
        if row.get("construction_family"): union(family,"construction:"+row["construction_family"])
        union(family,"text:"+normalize(row["text"]).casefold())
    result={k:[] for k in ("TRAIN","DEV","TEST","PROVISIONAL_HOLDOUT")}
    for row in rows:
        family=find(row["family"])
        bucket=int(hashlib.sha256(("provisional-v1:"+family).encode()).hexdigest()[:8],16)%100
        partition="TRAIN" if bucket<65 else "DEV" if bucket<80 else "TEST" if bucket<90 else "PROVISIONAL_HOLDOUT"
        result[partition].append({**row,"split_family":family})
    groups={key:{r["split_family"] for r in group} for key,group in result.items()}
    assert all(not groups[a]&groups[b] for a in groups for b in groups if a!=b)
    assert all(result.values()),"Empty partition"
    return result


def prepare():
    assert verify()==[],"Frozen evidence mismatch"
    store=AuditStore();ai=store.precheck()
    assert Counter(r["ai_precheck_status"] for r in ai.values())=={"LIKELY_APPROVE":738,"MANUAL_REVIEW":10,"LIKELY_REJECT":2}
    source={r["id"]:r for r in read_jsonl(FILES["corpus"])}
    accepted=sorted(key for key,v in ai.items() if v["ai_precheck_status"]=="LIKELY_APPROVE")
    excluded=sorted(set(ai)-set(accepted))
    rows=[]
    for key in accepted:
        row=copy.deepcopy(source[key]);row["family"]=row["isolation_group"]
        row.update(raw_text=row["text"],normalized_text=normalize(row["text"]),provenance="AI_PRECHECK_ACCEPTED",capability_gold=None)
        rows.append(row)
    rows.extend(authored_rows())
    ids=[r["id"] for r in rows];assert len(ids)==len(set(ids))
    for row in rows:
        for sl in row["frame"]["slots"]:
            if sl["source"]=="TEXT": assert row["text"][sl["start"]:sl["end"]]==sl["surface"],row["id"]
    split=split_rows(rows)
    manifest={"status":"AI_ASSISTED_PROVISIONAL","human_audit":"DEFERRED_NOT_COMPLETED","production_acceptance":"NOT_HUMAN_VALIDATED","source_frozen_manifest":str(MANIFEST.relative_to(ROOT)),"source_frozen_manifest_sha256":sha(MANIFEST),"source_queue_sha256":sha(FILES["audit_queue"]),"ai_precheck_sha256":sha(OUT/"ai_precheck_auxiliary.json"),"external_precheck_sha256":json.loads((OUT/"ai_precheck_auxiliary.json").read_text(encoding="utf-8"))["source_sha256"],"accepted_row_ids":accepted,"excluded_row_ids":excluded,"excluded_provenance":{k:"AI_PRECHECK_MANUAL_REVIEW" if ai[k]["ai_precheck_status"]=="MANUAL_REVIEW" else "AI_PRECHECK_REJECTED" for k in excluded},"human_approval_inferred":False,"family_leakage":0,"split_policy":"union construction/isolation families and exact duplicates; hash components 65/15/10/10","splits":{}}
    # Content-derived run directory makes preparation repeatable without replacing evidence.
    fingerprint=hashlib.sha256(canonical({"manifest":manifest,"rows":rows})).hexdigest()
    directory=DEST/fingerprint
    for key,group in split.items():
        path=directory/(key+".jsonl")
        immutable(path,"".join(json.dumps(r,ensure_ascii=False)+"\n" for r in group).encode())
        manifest["splits"][key]={"file":path.name,"sha256":sha(path),"rows":len(group),"families":len({r["split_family"] for r in group}),"languages":dict(Counter(r["language"] for r in group))}
    raw=canonical(manifest);digest=hashlib.sha256(raw).hexdigest()
    immutable(directory/("stage25_ai_provisional_manifest_"+digest+".json"),raw)
    immutable(directory/"excluded_flagged_12.jsonl","".join(json.dumps({**store.by_id[k],"provenance":manifest["excluded_provenance"][k],"review_status":"HUMAN_REVIEW_DEFERRED"},ensure_ascii=False)+"\n" for k in excluded).encode())
    # Timestamp is auxiliary, outside the deterministic content-addressed manifest.
    timestamp=directory/"created.json"
    if not timestamp.exists(): immutable(timestamp,canonical({"created_utc":datetime.now(timezone.utc).isoformat(),"manifest_sha256":digest}))
    print(json.dumps({"directory":str(directory),"manifest_sha256":digest,"splits":manifest["splits"]},indent=2))
    return directory,manifest


if __name__=="__main__": prepare()
