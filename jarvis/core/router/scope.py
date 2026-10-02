"""Scope of a consequential action: what exactly would be deleted, removed, installed, moved or sent.

A destructive or outward tool acts on ONE named thing. Its target is never:
- a universal quantifier: "everything", "all my files", "every app", "the whole drive", "ellam";
- a vague placeholder: "something", "stuff", "whatever";
- a pronoun nothing resolved: "it", "that one";
- a thing from another domain that only sounds like a file: "my emails", "my history", "all workflows", "my user account",
  "the photos on my phone".

Any of these asks instead of turning the words into a file or app name (Blind-10: "delete everything on my pc" became a
delete of a file called "everything on my pc"). Scoped commands still act: "delete temp_test.txt", "close all notepad
windows", "uninstall winrar".
"""
from __future__ import annotations

import re
from typing import Optional

# tool -> the argument that names what it acts on
TARGET_SLOT = {
    "send_whatsapp_message": "recipient", "reply_whatsapp_message": "recipient",
    "delete_file": "path", "move_file": "source", "rename_file": "source", "copy_file": "source", "batch_rename": "directory",
    "uninstall_software": "name", "install_software": "name", "update_software": "name", "close_app": "name",
    "localsend_file": "path", "android_push_file": "path", "compress_files": "path",
}
# the object of any action that must name something real: "open a file", "open the website", "type it there", "run it"
OBJECT_SLOT = {"open_app": "name", "open_file": "path", "open_website": "url", "dictate_text": "text", "capture_note": "content",
               "recall_facts": "query", "project_run": "project_name", "play_youtube": "query", "android_open_app": "app_name",
               "find_file": "query", "launch_workspace": "name", "close_app": "name"}
_EMPTY_OBJECT = re.compile(r"^(?:(?:a|an|the|my|some|that|this)\s+)?(?:file|files|document|website|site|page|app|application|program|"
                           r"thing|something|anything|it|that|this|there|here|it\s+there|that\s+there|one|stuff|write|"
                           r"remember|link|folder)$")
_FILE_ANTECEDENT = re.compile(r"\b(?:downloaded|saved|got|made|wrote|created|scanned|received|kept|put)\s+(?:my\s+|the\s+|a\s+|an\s+|that\s+)?"
                              r"(?P<x>[a-z][\w.-]*(?:\s+[a-z0-9][\w.-]*){0,3}?)\s*(?:last|yesterday|today|this|earlier|on|in|from|to|"
                              r",|and|but|where|which|that|somewhere)\b")
DESTRUCTIVE = {"delete_file", "move_file", "rename_file", "batch_rename", "uninstall_software", "close_app"}

_QUANT = re.compile(r"\b(?:everything|every\s*thing|all|every|entire|whole|each|anything|ellam|ellathayum|ellathaiyum|motham|"
                    r"everyone|everybody|the\s+lot)\b")
_VAGUE = re.compile(r"^(?:some|any|a|the|that|this|my)?\s*(?:something|anything|stuff|things?|whatever|some\s+(?:app|apps|file|files|"
                    r"program|software))$")
_PRONOUN = re.compile(r"^(?:it|that|this|them|those|these|that\s+one|this\s+one|the\s+one|one|that\s+1|this\s+1|the\s+other\s+one)$")
# nouns that belong to another capability, never to the file system / installer
_FOREIGN = re.compile(r"\b(?:e-?mails?|mails?|inbox|messages?|chats?|whats\s*app|history|histories|workflows?|shortcuts?|routines?|"
                      r"account|accounts|profile|contacts?|meetings?|events?|calendar|reminders?|notifications?|tabs?|bookmarks?|"
                      r"cookies|passwords?|apps|applications|programs|softwares?|windows\s+(?:folder|directory)|system\s*32|"
                      r"registry|drivers?)\b")
_ON_PHONE = re.compile(r"\b(?:on|in|from)\s+(?:my\s+|the\s+)?(?:phone|mobile|android)\b")
_FILE_LIKE = re.compile(r"\.[a-z0-9]{1,5}\b|[\\/]")
# "close all notepad windows", "close every chrome window": one app's windows, still one named app
_APP_WINDOWS = re.compile(r"^(?:all|every)\s+(?:the\s+|my\s+)?(?:open\s+)?(?P<app>[a-z0-9 .+-]+?)\s+(?:windows?|tabs?|instances?)$")


def _verdict(question: str) -> dict:
    return {"kind": "clarify", "question": question, "hard": True}


def _refuse(question: str, reason: str) -> dict:
    return {"kind": "refuse", "question": question, "reason": reason}


# where an on-screen / in-page target is named, per tool
CLICK_SLOTS = {"screen_click": ("target",), "ui_op": ("target", "option"), "browser_click": ("name", "text", "label"),
               "desktop_ui_click": ("name",), "android_tap_text": ("text",), "dialog_interaction": ("action",)}
TYPE_SLOTS = {"dictate_text": ("text",), "browser_type": ("text",), "android_input": ("text",), "ui_op": ("text", "value"),
              "text_op": ("text",), "browser_autofill": ("only",)}
_CAPTCHA = re.compile(r"\b(?:re)?captcha\b|\bi'?\s*a?m\s+not\s+a\s+robot\b|\brobot\s+(?:check|test|box)\b|\bhuman\s+verification\b")
_MONEY = re.compile(r"\b(?:buy|purchase|checkout|check\s+out|place\s+(?:the\s+)?order|order\s+now|pay|payment|pay\s+now|"
                    r"confirm\s+(?:the\s+)?(?:payment|purchase|order)|transfer|donate|subscribe\s+(?:and\s+)?pay|add\s+money)\b")
_MASS_DELETE = re.compile(r"\b(?:delete|remove|clear|erase|wipe|reset)\s+(?:all|everything|every)\b|\bfactory\s+reset\b")
_VAGUE_TARGET = re.compile(r"^(?:on\s+)?(?:it|that|this|here|there|them|that\s+one|this\s+one|something|the\s+thing|that\s+thing|"
                           r"(?:the|a|that|this)\s+(?:button|link|icon|thing|option|box|field))$")
_SECRET = re.compile(r"\b(?:passwords?|passcode|pin(?:\s+number|\s+code)?|otp|one[\s-]time\s+(?:password|code)|cvv|card\s+(?:number|details)|"
                     r"bank\s+(?:details|password)|upi\s+pin|aadhaa?r\s+number)\b")
_LOCK_BYPASS = re.compile(r"\b(?:unlock|bypass|get\s+(?:past|around|through)|skip|break|crack|disable)\b.{0,30}\b(?:lock\s*screen|screen\s+lock|"
                          r"lock|pin|pattern|password|passcode|face\s*id|fingerprint)\b|\bunlock\s+(?:my\s+|the\s+)?(?:phone|mobile|laptop|pc)\b")


def check_object(intent: str, slots: dict, text: str) -> Optional[dict]:
    """An action whose object is only 'a file', 'the website', 'it there', 'everything' has nothing to act on: ask."""
    key = OBJECT_SLOT.get(intent)
    if not key:
        return None
    raw_value = (slots or {}).get(key) or (slots or {}).get("text") or (slots or {}).get("content") or ""
    value = " ".join(str(raw_value).lower().split()).strip(" .")
    if intent == "project_run" and not value and re.fullmatch(r"(?:please\s+)?(?:run|start|launch)\s+(?:it|that|this)(?:\s+again)?", " ".join((text or "").lower().split())):
        return _verdict("Run what? Tell me the project or file.")
    if intent in ("open_app", "android_open_app") and re.search(r"\b(?:ideas?|tips?|advice|suggestions?|reasons?|examples?|jokes?|facts?|"
                                                             r"recipes?|quotes?|summary|explanation|plan|opinion|help\s+with)\b", value):
        return {"kind": "chat"}   # "give me 3 startup ideas", "give me medical advice for chest pain": an answer, not an app
    if intent == "find_file" and value in ("it", "that", "this", "them"):
        # "i downloaded my medical prescription last week, where is it": the thing was named earlier in the sentence
        m = _FILE_ANTECEDENT.search(" ".join((text or "").lower().split()))
        if m and not _EMPTY_OBJECT.match(m.group("x")):
            return {"kind": "reroute", "intent": "find_file", "slots": {**(slots or {}), "query": m.group("x").strip()}}
    if value and _EMPTY_OBJECT.match(value):
        last = value.split()[-1]
        if last in ("file", "files", "document", "website", "site", "page", "app", "application", "program", "link", "folder"):
            return _verdict(f"Which {last} exactly? Tell me its name.")
        return _verdict("What exactly? Tell me what you'd like me to act on.")
    return None


_COMPOSE = re.compile(r"^(?:my|a|an|the|some|me\s+a|me\s+an)\s+(?:\w+\s+){0,3}(?:assignment|homework|essay|letter|poem|story|stories|code|program|"
                      r"script|app|email(?!\s+(?:address|id))|report|article|song|lyrics|speech|resume|cv|cover\s+letter|thesis|paragraph|summary|caption|bio)\b")
_HARMFUL = re.compile(r"\b(?:malware|virus|ransomware|keylogger|trojan|spyware|phishing\s+(?:page|mail|email|site)|exploit\s+code|ddos)\b")


def check_typing(intent: str, slots: dict, text: str) -> Optional[dict]:
    """'write my college assignment' asks for something to be composed, not typed word for word; 'write malware' is
    refused in every form."""
    if intent not in ("dictate_text", "capture_note", "memos_create"):
        return None
    body = " ".join(str((slots or {}).get("text") or (slots or {}).get("content") or "").lower().split())
    if _HARMFUL.search(body) or _HARMFUL.search(" ".join((text or "").lower().split())):
        return _refuse("I won't write malware or anything meant to break into or harm systems.", "harmful")
    if intent == "dictate_text" and _COMPOSE.match(body):
        return {"kind": "chat"}
    return None


def check_creation(intent: str, slots: dict, text: str) -> Optional[dict]:
    """A reminder / note / to-do is only created by a creating sentence: "which reminders did i set", "clear all
    reminders", "what's on my todo" never become a new reminder whose text is the question."""
    if intent not in ("set_reminder", "capture_note", "memos_create", "quick_note"):
        return None
    low = " ".join((text or "").lower().split())
    lead = re.sub(r"^(?:(?:hey\s+)?jarvis\s*,?\s*|please\s+|can\s+you\s+|could\s+you\s+)+", "", low)
    if re.match(r"(?:what|which|show|list|read|tell\s+me|do\s+i\s+have|did\s+i|have\s+i|any|how\s+many)\b", lead) \
            and re.search(r"\breminders?\b", lead):
        return {"kind": "reroute", "intent": "list_reminders", "slots": {}}
    if re.match(r"(?:clear|delete|remove|cancel|erase|wipe|forget)\b", lead):
        return _verdict("I can't delete reminders or notes from here - which one did you mean, and should I just show them?")
    return None


def check_interaction(intent: str, slots: dict, text: str) -> Optional[dict]:
    """Clicks, taps and typing: never solve a CAPTCHA, spend money, mass-delete, type a secret or get past a lock screen;
    ask which element when the target is only 'it' / 'here' / 'the button'."""
    low = " ".join((text or "").lower().split())
    targets = " ".join(str((slots or {}).get(k) or "") for k in CLICK_SLOTS.get(intent, ())).lower().strip()
    typed = " ".join(str((slots or {}).get(k) or "") for k in TYPE_SLOTS.get(intent, ())).lower().strip()
    if intent in CLICK_SLOTS or intent in TYPE_SLOTS or intent in ("browser_op", "web_task", "computer_task"):
        if _CAPTCHA.search(targets) or _CAPTCHA.search(low):
            return _refuse("I don't solve or tick CAPTCHAs - that check is there for you to do yourself.", "captcha")
    if intent in CLICK_SLOTS:
        if _MONEY.search(targets) or (_MONEY.search(low) and not targets):
            return _refuse("That would spend money - I don't buy, order or pay for you. I can open the page and you click it "
                           "yourself.", "payment")
        if _MASS_DELETE.search(targets) or _MASS_DELETE.search(low):
            return _verdict("That button deletes things in bulk - I won't press it for you. Press it yourself if you're sure.")
        if targets and _VAGUE_TARGET.match(targets):
            return _verdict("Which one should I click? Tell me its label or what it looks like.")
    if intent in ("send_whatsapp_message", "reply_whatsapp_message", "send_whatsapp_bulk", "localsend_text", "gmail_create_draft",
                  "reply_whatsapp_all", "deliver_op") \
            and (_SECRET.search(" ".join(str(v) for v in (slots or {}).values()).lower()) or _SECRET.search(low)) \
            and not re.search(r"\b(?:don'?t|do\s+not|never|without)\b", low):
        return _refuse("I don't send passwords, PINs, OTPs, bank or card details in messages - share those yourself if you must.",
                       "secret")
    if re.search(r"\b(?:send|share|forward|anuppu|anupu|kudu)\b", low) and _SECRET.search(low) and intent not in ("generate_password",) \
            and not re.search(r"\b(?:don'?t|do\s+not|never)\b", low) or (intent == "generate_password" and re.search(r"\b(?:anuppu|anupu|send|share)\b", low)):
        return _refuse("I don't send passwords, PINs, OTPs, bank or card details - share those yourself if you must.", "secret")
    if intent in TYPE_SLOTS and (_SECRET.search(typed) or (_SECRET.search(low) and re.search(r"\b(?:type|enter|fill|put|write|input)\b", low))):
        return _refuse("I never type passwords, PINs, OTPs or card details - enter those yourself.", "secret")
    if intent in ("android_key", "phone_op", "android_input", "android_quick_action", "android_tap_text", "system_power_control") \
            and _LOCK_BYPASS.search(low):
        return _refuse("I can wake the phone, but I never unlock it or get past its lock - unlock it yourself.", "lock_screen")
    if intent in ("android_notifications", "gmail_list_recent", "read_whatsapp_messages", "phone_op", "describe_screen") \
            and re.search(r"\b(?:read|tell|show|get|check|copy|send)\b.*\b(?:otp|one[\s-]time\s+(?:password|code)|verification\s+code)\b", low):
        return _refuse("I don't read out or pass on one-time codes - check it yourself on the phone.", "otp")
    return None


def check_scope(intent: str, slots: dict, text: str) -> Optional[dict]:
    """A clarify verdict when the target is broad, vague, unresolved or from another domain; None when it is one thing."""
    key = TARGET_SLOT.get(intent)
    if not key:
        return None
    raw = str((slots or {}).get(key) or "").strip().lower()
    target = re.sub(r"^.*[\\/](?=[^\\/]*$)", "", raw) if not re.search(r"\.[a-z0-9]{1,5}$", raw) else raw
    target = re.sub(r"\s+", " ", target.replace("_", " " if not _FILE_LIKE.search(raw) else "_")).strip(" .")
    low = " ".join((text or "").lower().split())
    verb = intent.split("_")[0]
    if not target:
        return None
    if intent in ("send_whatsapp_message", "reply_whatsapp_message"):
        if re.search(r"\b(?:all|every|everyone|everybody)\b.*\b(?:groups?|e-?mails?|mails?|contacts|chats)\b|\ball\s+(?:groups?|my\s+groups?)\b|"
                     r"\b(?:e-?mails?|mails?)\b", target):
            return _verdict("Who exactly? I only message one person (or one named group) at a time, and email isn't WhatsApp.")
        return None
    m = _APP_WINDOWS.match(target)
    if intent == "close_app" and m:
        return {"kind": "reroute", "intent": "close_app", "slots": {**(slots or {}), "name": m.group("app").strip()}}
    if _PRONOUN.match(target):
        v = _verdict(f"Which one should I {verb}? I won't guess what 'it' means for that.")
        v["pronoun"] = True   # inside "find X, rename it ...", 'it' is the earlier step's result
        return v
    if _VAGUE.match(target):
        return _verdict(f"What exactly should I {verb}? Tell me the name.")
    if intent == "update_software" and _QUANT.search(target):
        return {"kind": "reroute", "intent": "update_software", "slots": {"name": ""}}   # "update every app": the tool's own 'all'
    if intent == "install_software" and target == "everything":
        return None   # "Everything" is a real search app; installing still asks for confirmation
    if _QUANT.search(target) and not _FILE_LIKE.search(target):
        what = re.sub(r"^(?:all|every|everything)\s+(?:of\s+)?", "", target) if not re.fullmatch(r"(?:everything|every\s*thing|ellam|ellathayum|all)(?:\s+(?:on|in|of)\b.*)?", target) \
            else "everything"
        what = re.sub(r"\bmy\b", "your", what) or "everything"
        return _verdict(f"That's {('all of ' + what) if what != 'everything' else 'everything'}, not one thing - I won't {verb} "
                        f"that in one go. Tell me exactly which one (or which folder and type) and I'll show you what it would "
                        f"touch first.")
    if intent in ("delete_file", "move_file", "rename_file", "copy_file", "compress_files", "localsend_file", "android_push_file") \
            and not _FILE_LIKE.search(target):
        if _ON_PHONE.search(target) or (_ON_PHONE.search(low) and intent == "delete_file"):
            return _verdict("Those are on your phone - I don't delete anything on the phone from here. Which file on this PC did you mean?")
        if _FOREIGN.search(target):
            return _verdict(f"'{target}' isn't a file on this PC, so I won't {verb} it as one. What exactly did you want done?")
    return None


def broad_in_text(text: str) -> bool:
    low = " ".join((text or "").lower().split())
    # "wipe my documents folder", "empty my downloads": a whole user folder (the recycle bin / trash / clipboard are fine)
    if re.search(r"\b(?:wipe|erase|empty|clear\s+out|clean\s+out|nuke|format)\s+(?:all\s+of\s+)?(?:my\s+|the\s+)?(?:whole\s+|entire\s+)?"
                 r"(?:documents|downloads|desktop|pictures|photos|music|videos|home|user|files)\b(?:\s+folder)?", low):
        return True
    # "delete my files", "every hour delete my files", "send all my photos to everyone"
    if re.search(r"\b(?:delete|remove|erase|trash)\s+(?:all\s+)?(?:of\s+)?my\s+(?:files|documents|photos|pictures|data|stuff|downloads|folders)\b", low):
        return True
    if re.search(r"\b(?:send|share|forward|post|upload)\b.*\b(?:everyone|everybody|all\s+(?:my\s+)?contacts|all\s+groups)\b", low) \
            and re.search(r"\ball\s+(?:my\s+)?(?:photos|pictures|files|documents|videos|contacts|data)\b|\b(?:everything|all\s+of\s+it)\b", low):
        return True
    return _broad_core(low)


def _broad_core(low: str) -> bool:
    """'delete everything', 'remove all my stuff': a destructive verb whose object is a universal quantifier."""
    if re.search(r"\b(?:delete|remove|erase|wipe|trash|uninstall|destroy)\s+(?:all\s+(?:of\s+)?)?(?:my\s+|the\s+)?"
                 r"(?:everything|every\s*thing|ellam|ellathayum|whatever|the\s+lot|every\s+(?:single\s+)?(?:file|document|photo|picture|app|program|"
                 r"folder|email|mail|chat|message|contact)|all\s+(?:my\s+|the\s+)?(?:files|data|stuff|documents|"
                 r"photos|pictures|apps|programs|folders|emails|mails|chats|messages|contacts))\b", low):
        return True
    return bool(re.search(r"\b(?:ellam|ellathayum|motham)\s+(?:delete|remove|erase|uninstall)", low))
