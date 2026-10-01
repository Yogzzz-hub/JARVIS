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


_CHANGE_VERB = re.compile(r"^(?:(?:please|now|then|and|also|just|jarvis|hey\s+jarvis|can\s+you|could\s+you)[\s,]+)*"
                          r"(?P<v>create|schedule|book|draft|compose|attach|upload|paste|insert|install|uninstall|delete|remove|"
                          r"rename|move|copy|save|store|submit|post|publish|reply|forward)\b(?!\s+(?:on|along|ahead|me\b))", re.I)


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


def check_target(intent: str, slots: dict, text: str, normalized: str = "") -> Optional[dict]:
    """None when the route can run as it is; otherwise a verdict: reroute / planner / clarify."""
    slots = slots or {}
    low = " ".join((text or "").lower().replace("’", "'").split())
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
        if intent == "open_app" and re.search(r"\b(?:file|document|doc|pdf|report|folder|photo|image|screenshot|"
                                              r"spreadsheet|presentation|notes?)s?\b", name) \
                and re.search(rf"\b{_REF_WORDS}\b|\b(?:we|i|you)\b", name):
            path = _path_from_actions(name)
            if path:
                return _verdict("reroute", intent="open_file", slots={"path": path, "resolved_from": "action_log"})
            return _verdict("clarify", question="Which file do you mean? I don't have a single file from earlier to go on - "
                                                "tell me its name or search for it first.")
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
    if intent == "find_file":
        query = str(slots.get("query") or "").strip().lower()
        probe = query or low
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
        path = str(slots.get("path") or slots.get("source") or slots.get("name") or "").strip().lower()
        if path and _BARE_FILE.match(path) and not re.search(r"[\\/]|\.\w{2,4}$", path):
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
