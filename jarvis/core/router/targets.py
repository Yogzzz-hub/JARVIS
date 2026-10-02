"""Is the thing a matched tool would act on a real target? Checked after matching, before anything runs.

A pattern can match the right verb and still capture the wrong object:

    "open the second menu item under File"   open_app("second menu item under file")  - a control, not an app
    "close only the dialog"                  close_app("only the dialog")             - a dialog, not an app
    "open the editor I installed earlier"    open_app("editor i installed earlier")   - a reference to an earlier action
    "find the textbox under the selected tab" find_file(...)                          - a control, not a file
    "find where this PDF discusses X"        find_file(...)                           - a question about content
    "remove the screenshot"                  delete_file("screenshot")                - which screenshot?

The verdict is one of: keep the route, re-route (to the tool that fits the object), resolve the reference from what
JARVIS really did (the action log), hand the request to the planner, or ask. Nothing is guessed.
"""
from __future__ import annotations

import re
from typing import Optional

APP_INTENTS = ("open_app", "close_app", "install_software", "uninstall_software", "update_software", "check_app_installed",
               "get_app_location")
FILE_CHANGE_INTENTS = ("delete_file", "move_file", "rename_file", "copy_file")

_UI = (r"(?:menu\s+items?|menus?|dialog(?:\s+box)?|dialogs|pop-?ups?|modal|message\s+box|buttons?|text\s*box(?:es)?|text\s+fields?|"
       r"input\s+fields?|fields?|controls?|drop-?downs?|combo\s*box(?:es)?|check\s*box(?:es)?|radio\s+buttons?|options?|toggles?|"
       r"sliders?|toolbars?|ribbon|sidebar|panel|pane|tab\s+(?:under|in|of)|selected\s+tab|links?\s+(?:on|in)\s+(?:the\s+)?(?:page|window))")
_DIALOG = r"(?:dialog(?:\s+box)?|pop-?up|modal|message\s+box|prompt\s+window|alert)"
_REF_WORDS = (r"(?:earlier|before|previously|previous|last\s+(?:time|one)|recently|just\s+now|the\s+one|we\s+\w+|i\s+(?:just\s+)?\w+ed|"
              r"you\s+\w+ed|that\s+one|new\s+version|old\s+version|stale|other\s+one|same\s+one)")
_GENERIC_APP = re.compile(r"^(?:the\s+|that\s+|this\s+|my\s+)?(?:app|application|program|software|package|tool|thing|it|one|editor|"
                          r"new\s+version(?:\s+of(?:\s+the)?)?(?:\s+app)?|version|executable|exe)s?$")
_REMOTE = (r"(?:google\s+drive|drive|one\s*drive|e-?mails?|mails?|gmail|inbox|meetings?|calendar|events?|urls?|links?|websites?|"
           r"web\s*pages?|pages?|official\s+(?:docs|documentation|site|website)|documentation|docs\s+online|online|internet|"
           r"browser|chrome|edge|firefox)")
_CONTENT_Q = re.compile(r"\b(?:where|paragraph|section|part|chapter|page|line|passage|sentence|place)s?\b.*\b(?:discuss|mention|talk|"
                        r"say|cover|explain|describe|define|refer)\w*|\b(?:conflicting|contradict\w*|inconsistent|disagree\w*|"
                        r"mismatch\w*)\b")
_BARE_FILE = re.compile(r"^(?:the\s+|that\s+|this\s+|my\s+|a\s+)?(?:(?:latest|last|new|newest|previous|old|other|current|second|first)\s+)?"
                        r"(?:screenshot|screen\s*shot|pdf|file|document|doc|image|photo|picture|pic|folder|attachment|report|"
                        r"video|download|it|that|this|them|one)s?$")

# what the owner did -> the tools that did it (to resolve "the X I installed earlier")
_DID = (
    (r"new\s+version|latest\s+version|updated\s+(?:app|one|version)", ("update_software", "install_software")),
    (r"install\w*", ("install_software",)),
    (r"updat\w*|upgrad\w*", ("update_software",)),
    (r"open\w*|launch\w*|start\w*|used?|using|ran|run", ("open_app",)),
    (r"clos\w*|quit\w*", ("close_app",)),
)


def _verdict(kind: str, **kw) -> dict:
    return {"kind": kind, **kw}


def _name_from_actions(phrase: str) -> Optional[str]:
    """'editor i installed earlier today' -> the name of the app JARVIS really installed most recently."""
    for verbs, tools in _DID:
        if re.search(rf"\b(?:{verbs})\b", phrase):
            try:
                from jarvis.core.action_log import get_action_log
                e = get_action_log().last(tools=tools)
            except Exception:
                e = None
            if e is not None and e.ok:
                name = e.args.get("name") or e.args.get("app") or ""
                if isinstance(name, str) and name.strip():
                    return name.strip()
            return ""
    return None


_FILE_DID = (
    (r"found|find|search\w*|looked\s+up", ("find_file",)),
    (r"open\w*|read|viewed|looked\s+at", ("open_file", "find_file")),
    (r"captur\w*|took|taken|screenshot\w*|snapp\w*", ("take_screenshot",)),
    (r"sav\w*|creat\w*|made|wrote|written", ("capture_note", "save_workspace", "take_screenshot")),
    (r"sent|shared", ("localsend_file", "android_push_file")),
)


def _path_from_actions(phrase: str) -> str:
    """'file we found earlier' -> the one file JARVIS really found / opened / captured most recently ('' if none)."""
    try:
        from jarvis.core.action_log import get_action_log
        log = get_action_log()
    except Exception:
        return ""
    for verbs, tools in _FILE_DID:
        if re.search(rf"\b(?:{verbs})\b", phrase):
            e = log.last(tools=tools)
            path = e.args.get("path") if e is not None and e.ok else ""
            return path.strip() if isinstance(path, str) else ""
    return ""


_FILE_WORDS = (r"file|document|doc|docx|pdf|report|folder|photo|image|picture|screenshot|video|song|music|spreadsheet|sheet|"
               r"presentation|slides|deck|notes?|resume|cv|invoice|receipt|certificate|zip|script|code|download|xlsx|pptx|csv|txt")
# a name / query that is really a whole command ("use the current logged-in session", "retry the read-only search")
_COMMAND_LIKE = re.compile(r"^(?:use|retry|try|make|do|send|keep|run|start|go|take|get|put|tell|show|give|let|bring|move|copy|paste|"
                           r"attach|upload|prepare|create|compare|summari[sz]e|repeat|redo|undo|click|type|press)\s+"
                           r"(?:the|a|an|my|this|that|it|me|your|another|some|all)\b")
_SENTENCE_SLOTS = {"save_workspace": "name", "launch_workspace": "name", "create_folder": "path", "search_notes": "query",
                   "search_web": "query", "find_file": "query", "knowledge_search": "question", "set_reply_language": "mode",
                   "localsend_text": "text"}

_CHANGE_VERB = re.compile(r"^(?:(?:please|now|then|and|also|just|jarvis|hey\s+jarvis|can\s+you|could\s+you)[\s,]+)*"
                          r"(?P<v>create|schedule|book|draft|compose|attach|upload|paste|insert|install|uninstall|delete|remove|"
                          r"rename|move|copy|save|store|submit|post|publish|reply|forward|make\s+(?:it|that|this)\s+(?!louder|quieter|"
                          r"brighter|dimmer|bigger|smaller|full)|extend|shorten|reschedule|postpone)\b(?!\s+(?:on|along|ahead|me\b))", re.I)


_READER = re.compile(r"^(?:get|read|list|check|find|search|show|recall|describe|summari[sz]e|diagnose|system_info|top_|connected|"
                     r"battery|network|wifi|volume_get|brightness_get|personal_briefing|morning_briefing|recent|command_history|"
                     r"android_status|android_notifications|rss|gmail_list|calendar_list|knowledge|document_qa|quick_answer|"
                     r"contact_info|microphone|speech|wake_word|git_status)|_(?:status|info|history|recent|processes)$")


def verb_mismatch(text: str, intent: str, read_only: bool) -> bool:
    """A command whose verb makes or changes something, matched to a tool that only reads (looks things up)."""
    m = _CHANGE_VERB.match(" ".join((text or "").split()))
    return bool(m and read_only and _READER.search(intent) and m.group("v").lower()[:4] not in intent.replace("_", " "))


_ANTECEDENT = re.compile(r"\b(?:need|want|get|download|grab|use|have|like|love)\s+(?:the\s+|a\s+|an\s+|my\s+)?"
                         r"(?P<x>[a-z][\w.+#-]*(?:\s+[a-z0-9][\w.+#-]*){0,2}?)\s+(?:for|to|on|so|because|,|and|but|which|that)\b")


# A consequential tool is only taken when the request says that kind of thing: "shrink this window" never closes it,
# "put the copied text on my phone" never pushes a file called "copied text".
_SEND = (r"send|tell|message|msg|text|reply|respond|forward|share|ping|whats\s*app|say|inform|ask|remind|wish|answer|dm|let\s+\w+\s+know|"
         r"(?:drop|shoot|fire\s+off|leave|write)\s+(?:\w+\s+){0,3}?(?:a|an)\s+(?:quick\s+|short\s+)?(?:message|msg|text|note|line)")
_GIVE = r"send|push|put|share|transfer|copy|move|throw|toss|chuck|fling|sling|drop|give|pass|beam|ship|upload|get|bring"
_CONSEQUENTIAL_VERBS = {
    "close_window": r"close|closing|quit|exit|shut|kill|terminate|end|dismiss|stop|x\s+out|get\s+rid\s+of",
    "close_app": r"close|closing|quit|exit|shut|kill|terminate|end|dismiss|stop|x\s+out|get\s+rid\s+of",
    "delete_file": r"delete|remove|erase|trash|bin|get\s+rid\s+of|wipe|clear|discard|destroy|scrap|throw\s+(?:away|out)|toss|junk|"
                   r"dump|(?:don'?t|do\s+not|no\s+longer)\s+need|not\s+needed",
    "empty_recycle_bin": r"(?:empty|clear|purge|clean|wipe|delete|flush)\b.*\b(?:recycle|bin|trash)",
    "move_file": r"move|put|drop|relocate|transfer|shift|file\s+(?:it|this|that)|organi[sz]e",
    "rename_file": r"rename|re-name|call|name|retitle|change\s+(?:the\s+|its\s+|it'?s\s+)?(?:file\s*)?name|(?:give|set)\s+"
                   r"(?:\w+\s+){0,3}?(?:a\s+)?new\s+name",
    "install_software": r"install|set\s*up|setup|get|download|add|grab|need|want",
    "uninstall_software": r"uninstall|remove|delete|get\s+rid\s+of",
    "send_whatsapp_message": _SEND, "send_whatsapp_bulk": _SEND, "reply_whatsapp_message": _SEND,
    "reply_whatsapp_all": _SEND,
    "android_push_file": _GIVE, "localsend_file": _GIVE, "localsend_text": _GIVE,
    "system_power_control": r"shut\s*down|shutdown|restart|reboot|sleep|hibernate|lock|log\s*(?:off|out)|sign\s*out|power|turn\s+off",
}


_DETERMINERS = frozenset("the a an this that these those my your his her their our its whose which last new any each every".split())


def _verb_said(verbs: str, text: str) -> bool:
    """A verb of the family used as a verb: "the message says ..." has the noun 'message', not the verb."""
    for m in re.finditer(rf"\b(?:{verbs})(?:ed|d|ing)?\b", text):
        before = text[:m.start()].split()[-1:]
        if before and before[0].strip(",.") in _DETERMINERS:
            continue
        return True
    return False


def missing_consequential_verb(intent: str, text: str, normalized: str = "") -> bool:
    verbs = _CONSEQUENTIAL_VERBS.get(intent)
    if not verbs:
        return False
    from jarvis.core.router.normalize import correct_command_typos
    low = (text or "").lower()
    if intent in ("close_window", "close_app", "delete_file", "uninstall_software") and \
            re.search(r"\b(?:re-?open|restore|undo|bring\s+back|recover|undelete|un-?close|reinstall)\b", low):
        return True       # "reopen the last closed window": the verb asks for the opposite of closing
    asked = re.sub(r"^\W*(?:(?:hey|ok|okay|um+|uh+|so|quick\s+question)\W+)*(?:jarvis\W+)?", "", low)
    if re.match(r"(?:where|what|which|who|when|how|why|is|are|was|were|has|have|had|did|does|do)\b|where's|what's", asked) \
            and not re.search(rf"\b(?:{verbs})\b", low):
        return True       # "where's zotero installed": a question; "installed" / "closed" there is a state, not the verb
    # the same typo repair the router used to pick the tool ("clsoe discord", "dleete notes.txt")
    if _verb_said(verbs, low):
        return False
    # the router's typo repair counts only for the command verb near the start ("clsoe discord"), never for a word deep
    # in the sentence it may have "repaired" ("use sharex" -> "use share")
    for t in ((normalized or "").lower(), correct_command_typos(" ".join(low.split()))):
        if _verb_said(verbs, " ".join(t.split()[:3])):
            return False
    return True


def check_target(intent: str, slots: dict, text: str, normalized: str = "") -> Optional[dict]:
    """None when the route can run as it is; otherwise a verdict: reroute / rematch / planner / clarify."""
    slots = slots or {}
    low = " ".join((text or "").lower().replace("’", "'").split())
    from jarvis.core.router.scope import check_creation, check_interaction, check_object, check_scope, check_typing
    if intent in APP_INTENTS:
        name = str(slots.get("name") or slots.get("app") or "").strip().lower()
        if name in ("it", "that", "this", "them", "one", "that one", "this one") and (" " + name) in low:
            # "i need calculator for college, can you install it": the app was named earlier in the same sentence
            m = _ANTECEDENT.search(low[: low.rfind(" " + name)] + " ,")
            if m and not re.fullmatch(r"(?:it|that|this|them|one|you|me|help|something|anything)", m.group("x")):
                return _verdict("reroute", intent=intent, slots={**slots, "name": m.group("x").strip()})
    scoped = check_interaction(intent, slots, low) or check_typing(intent, slots, low) or check_scope(intent, slots, low) \
        or check_creation(intent, slots, low) or check_object(intent, slots, low)
    if scoped:
        return scoped   # "delete everything", "uninstall that one", "delete my history": never one guessed name
    if intent in ("reply_whatsapp_message", "send_whatsapp_message") and \
            re.search(r"\b(?:who|whom|which)\s+(?:messaged|texted|wrote|sent|replied|called|pinged)\b",
                      str(slots.get("recipient") or "").lower()):
        # "reply to eevryone who messaged me today": a description of several people, not one contact
        return _verdict("clarify", question="Do you mean everyone who messaged you (direct chats only)? Say 'reply to "
                                            "everyone who messaged me today' and I'll draft them for you to check.")
    if missing_consequential_verb(intent, low, normalized):
        return _verdict("clarify", question="I'm not sure what you want done - I won't " + intent.split("_")[0] +
                                            " anything unless you say so. What should I do?")
    if intent in ("android_push_file", "localsend_file") and not str(slots.get("path") or "").strip() \
            and re.search(r"\b(?:text|message|note|clipboard|selection|selected|copied)\b", low):
        return _verdict("reroute", intent="localsend_text", slots={"text": "", "from_selection": bool(re.search(r"\bselect", low))})
    if intent in ("android_push_file", "localsend_file") and re.fullmatch(
            r"(?:the\s+|my\s+|this\s+|that\s+)?(?:copied\s+text|clipboard(?:\s+text)?|text(?:\s+i\s+copied)?|selection|selected\s+text)",
            str(slots.get("path") or "").strip().lower()):
        # text, not a file: the phone gets the clipboard text
        return _verdict("reroute", intent="localsend_text", slots={"text": ""})
    key = _SENTENCE_SLOTS.get(intent)
    value = str(slots.get(key) or "").strip().lower() if key else ""
    if intent == "localsend_text" and value and _COMMAND_LIKE.match(value) and \
            re.search(r"\b(?:copied|selected|clipboard|selection|highlighted)\b", value):
        # "put this copied text on my phone": the copied / selected text - never the command itself
        return _verdict("reroute", intent="localsend_text",
                        slots={"text": "", "from_selection": bool(re.search(r"\b(?:selected|selection|highlighted)\b", value))})
    if value and _COMMAND_LIKE.match(value) and not (intent == "search_web" and value.startswith(("show", "tell"))):
        return _verdict("planner", reason="the whole command was taken as a name or a query")
    if intent in APP_INTENTS:
        name = str(slots.get("name") or slots.get("app") or "").strip().lower()
        if not name:
            return None
        if name in ("it", "that", "this", "them", "one", "that one", "this one"):
            # "i need calculator for college, can you install it": the app was named earlier in the same sentence
            m = _ANTECEDENT.search(low[: low.rfind(" " + name)] + " ," if (" " + name) in low else low)
            if m and not re.fullmatch(r"(?:it|that|this|them|one|you|me|help|something|anything)", m.group("x")):
                return _verdict("reroute", intent=intent, slots={**slots, "name": m.group("x").strip()})
        if re.search(rf"\b{_DIALOG}\b", name) and intent == "close_app":
            return _verdict("reroute", intent="dialog_interaction", slots={"action": "dismiss"})
        if re.search(rf"\b{_UI}\b", name):
            return _verdict("planner", reason="names a control inside a window, not an app")
        if re.search(r"\b(?:for|of|in)\s+(?:this|that|the\s+current)$", name):
            # "open notification settings for this app" read as an app called "notification settings for this"
            return _verdict("planner", reason="a page of an app, not an app name")
        if re.match(r"^(?:stop|start|open|close|run|kill|restart|launch|quit|exit)\b", name):
            # "stop test app" read as close_app "stop test": a verb is never part of an app's name
            return _verdict("clarify", question="Which app do you mean? Tell me its name.")
        if re.fullmatch(r"(?:open\s+|close\s+)?(?:square\s+|curly\s+|round\s+)?(?:brackets?|paren\w*|braces?|quotes?|"
                        r"quotation\s+marks?)", name):
            return _verdict("clarify", question="Do you mean the symbol? While dictating, say 'open bracket' and I'll type it.")
        if re.match(r"^(?:the\s+)?(?:next|previous|prior|other|first|second|third|last|same)\s+(?:file|tab|page|result|link|"
                    r"item|one|document|pdf|photo|image|video|song|track|message|chat)s?$", name):
            what = name.split()[-1]
            return _verdict("clarify", question=f"Which {what} do you mean? Show or search the list first, then say "
                                                f"'open the second one'.")
        if intent == "open_app" and re.search(r"\b(?:file|document|doc|pdf|report|folder|photo|image|screenshot|"
                                              r"spreadsheet|presentation|notes?)s?\b", name) \
                and re.search(rf"\b{_REF_WORDS}\b|\b(?:we|i|you)\b", name):
            path = _path_from_actions(name)
            if path:
                return _verdict("reroute", intent="open_file", slots={"path": path, "resolved_from": "action_log"})
            return _verdict("clarify", question="Which file do you mean? I don't have a single file from earlier to go on - "
                                                "tell me its name or search for it first.")
        if intent == "open_app" and re.search(r"\b(?:resume|cv|readme|pdf|screenshot|download|report|invoice|receipt|"
                                              r"assignment|spreadsheet|presentation|document|file)s?\b", name) \
                and (re.search(r"\b(?:my|latest|newest|recent|last|first|second|third|previous|downloaded)\b|\b(?:resume|cv|"
                               r"readme|pdf)\b", name) or re.search(r"\bin\s+(?:my\s+|the\s+)?(?:downloads|documents|desktop|"
                                                                     r"pictures)\b", low)):
            # "open my resume", "open the latest pdf in downloads": a file to find first, not an app
            return _verdict("planner", reason="names a file, not an app")
        if re.search(rf"\b{_REF_WORDS}\b", name) or re.search(rf"\b{_REF_WORDS}\b", low) and _GENERIC_APP.match(name):
            found = _name_from_actions(name)
            if found is None:  # "open the one I used earlier": the verb is in the sentence, after the command verb
                found = _name_from_actions(" ".join(low.split()[1:]))
            if found:
                return _verdict("reroute", intent=intent, slots={**slots, "name": found, "resolved_from": "action_log"})
            what = {"install_software": "install", "uninstall_software": "uninstall", "update_software": "update",
                    "close_app": "close", "check_app_installed": "check", "get_app_location": "locate"}.get(intent, "open")
            return _verdict("clarify", question=f"Which app should I {what}? I don't have a record of the one you mean - "
                                                f"tell me its name.")
        if _GENERIC_APP.match(name):
            what = {"install_software": "install", "uninstall_software": "uninstall", "update_software": "update",
                    "close_app": "close", "check_app_installed": "check", "get_app_location": "locate"}.get(intent, "open")
            return _verdict("clarify", question=f"Which {'package' if 'package' in name else 'app'} should I {what}?")
        return None
    if intent == "android_open_app":
        app = str(slots.get("app_name") or slots.get("name") or "").strip().lower()
        if re.match(r"^(?:this|that|the|my)\s+(?:file|url|link|page|pdf|document|photo|screenshot|tab)\b|^(?:page|link|url)\b", app):
            return _verdict("planner", reason="names a file or page to put on the phone, not an app")
        return None
    if intent == "find_file":
        query = str(slots.get("query") or "").strip().lower()
        probe = low if not re.search(r"[a-z0-9]", query) else query  # "*" (constraints only): read the whole request
        if re.search(r"\b(?:said|says|told|tell|wrote|texted|messaged|replied|asked|chat(?:ted)?|messages?|whats\s*app)\b", low) \
                and not re.search(rf"\b(?:{_FILE_WORDS})s?\b|\.\w{{2,4}}\b", low):
            return _verdict("rematch", reason="asks what someone said, not for a file")
        if re.search(rf"\b{_UI}\b", probe):
            return _verdict("planner", reason="looks for a control on screen, not a file")
        if re.search(r"\b(?:in|on|from|inside)\s+(?:my\s+|the\s+)?(?:google\s+drive|drive|one\s*drive|gmail|inbox|e-?mails?|web|"
                     r"internet|chrome|edge|browser|whats\s*app)\b", probe):
            return _verdict("planner", reason="looks in another app or online, not on this PC")
        if re.search(rf"\b{_REMOTE}\b", probe) and not re.search(r"\.\w{2,4}\b|\b(?:local|this\s+pc|my\s+pc|laptop|"
                                                                r"downloads|desktop|documents)\b", probe):
            return _verdict("planner", reason="looks for something online or in another app, not a local file")
        if _CONTENT_Q.search(probe):
            return _verdict("reroute", intent="knowledge_search", slots={"question": (text or "").strip()})
        local = _FILE_WORDS.replace("|music", "").replace("|song", "").replace("|video", "")
        if re.match(r"^(?:(?:please|kindly|um+|uh+|so|can you|could you|would you|jarvis|hey jarvis|ok jarvis),?\s+)*(?:search|look\s+up|google)"
                    r"(?:\s+(?:for|about))\s+", low) and re.search(r"[a-z0-9]", query) \
                and not re.search(rf"\b(?:{local})s?\b|\.\w{{2,4}}\b|\b(?:my|mine|files?|folders?|downloads|documents|"
                                  rf"desktop|pictures|this\s+pc|computer|laptop|drive|saved|yesterday|today|last\s+week)\b", low):
            # "search for lofi music": nothing about it is a file on this PC - the web
            return _verdict("reroute", intent="search_web", slots={"query": query})
        return None
    if intent == "list_directory" and not re.search(r"\b(?:list|show|open|browse|display|explore|see|view|check|contents?|"
                                                    r"files?\s+(?:are\s+|there\s+)?in|look\s+in|what(?:'s|\s+is|\s+are)\s+in|"
                                                    r"inside|go\s+to|folder|directory|dir|in\s+(?:my\s+|the\s+)?(?:downloads|"
                                                    r"documents|desktop|pictures|music|videos))\b",
                                                    low + " " + (normalized or "").lower()):
        return _verdict("planner", reason="mentions documents but does not ask to list a folder")
    if intent in ("screen_click", "browser_click", "desktop_ui_click"):
        target = str(slots.get("target") or slots.get("name") or slots.get("element") or "").strip().lower()
        if re.search(r"\b(?:same|that|previous|last|earlier|other)\b", target):
            try:
                from jarvis.core.action_log import get_action_log
                e = get_action_log().last(tools=("screen_click", "browser_click", "desktop_ui_click"))
            except Exception:
                e = None
            prev = (e.args.get("target") or e.args.get("name") or "") if e is not None and e.ok else ""
            if isinstance(prev, str) and prev.strip() and not re.search(r"\b(?:same|that|previous|last)\b", prev.lower()):
                return _verdict("reroute", intent=intent, slots={**slots, "target": prev.strip(), "resolved_from": "action_log"})
            return _verdict("clarify", question="Which control should I click? I don't have a record of the one you mean - "
                                                "tell me its label.")
        return None
    if intent in FILE_CHANGE_INTENTS:
        if re.search(r"\b(?:the\s+)?(?:last|previous|next|first)\s+(?:\d+\s+|one\s+|two\s+|three\s+|four\s+|five\s+|few\s+|"
                     r"couple\s+of\s+)?[a-z]{2,10}$", low) and not re.search(rf"\b(?:{_FILE_WORDS})s?\b|\.\w{{2,4}}\b|[\\/]", low):
            # "delete the last 3 wrds": a count of something in the text, not a file - never guess a file to remove
            return _verdict("clarify", question="Do you mean text in the field you're typing in? Say e.g. 'delete the "
                                                "last 3 words', or name the file.")
        path = str(slots.get("path") or slots.get("source") or slots.get("name") or "").strip().lower()
        ref = re.match(r"^(?:this|that|these|those|the\s+current|the\s+selected)\s+(?P<noun>[a-z]{2,20})$", path)
        if ref and not re.fullmatch(rf"(?:{_FILE_WORDS})s?|item|one|thing|folder|directory|attachment", ref.group("noun")):
            # "rename this symbol", "delete this line", "move this smybol": the thing in front is not a file
            return _verdict("clarify", question=f"'{ref.group('noun')}' isn't a file I can see. If it's in the editor or a "
                                                f"field, say e.g. 'rename this symbol to X' in the IDE; otherwise name the file.")
        said = re.search(r"[\\/]", path) and not re.search(r"[\\/]", low)  # a folder the resolver added, not the owner
        base = re.split(r"[\\/]", path)[-1] if said else path
        if base and _BARE_FILE.match(base) and not re.search(r"\.\w{2,4}$", base) \
                and (said or not re.search(r"[\\/]", path)):
            path = base
            noun = re.sub(r"^(?:the|that|this|my|a)\s+", "", path)
            noun = "file" if noun in ("it", "that", "this", "them", "one") else noun
            verb = {"delete_file": "remove", "move_file": "move", "rename_file": "rename", "copy_file": "copy"}[intent]
            if intent == "delete_file" and slots.get("qualifiers", {}).get("keep"):
                return _verdict("clarify", question=f"Do you mean take the {noun} out of what you're preparing, or delete the "
                                                    f"{noun} file itself? If it's the file, tell me its name - I won't delete "
                                                    f"anything until I know exactly which one.")
            return _verdict("clarify", question=f"Which {noun} should I {verb}? Tell me its name or where it is - I won't "
                                                f"{verb} anything until I know exactly which one.")
        return None
    return None
