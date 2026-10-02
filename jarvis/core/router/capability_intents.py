"""Capability parser for the second operator layer: files, IDE work, phone, system state, watches, workflows, and the
window / control / text / browser primitives the first layer (operator_intents) does not claim.

Same contract as operator_intents: an *object family* (a file tab, a symbol, a notification, a slider, a workflow, a
condition ...) decides the capability, the *verb family* decides the action, and references ("this", "that", "its",
"the current") stay references - the tool resolves them against what is on screen or in resource memory, never the
router. Nothing here executes, nothing is special-cased per sentence, and when a reference cannot work without a
target ("do this on my phone") the answer is a question.

Families are tried in a fixed order: conditions and watches first (so "when X, open it" never opens anything now),
then families whose objects are unambiguous (workflow, symbol, notification, APK, slider), then the general ones.
"""
from __future__ import annotations

import re
from typing import Optional

from jarvis.core.router.models import RouteDecision, RouteLane
from jarvis.core.router.operator_intents import _APPS, _IDES, _NUM_RE, _ORD, _ORD_RE, _d, _n, _raw

_REF = r"(?:this|that|the|my|its|it|current|the current|these|those|our|your)"
_DET = rf"(?:{_REF}\s+)?"
_PRONOUN = re.compile(r"^(?:it|this|that|them|these|those|this one|that one|here|there)$")
_PHONE = r"(?:my\s+|the\s+)?(?:phone|mobile|android|cell(?:\s?phone)?|device)"
_ON_PHONE = rf"\s+(?:on|in|from|of)\s+{_PHONE}"
_PC = r"(?:my\s+|the\s+)?(?:pc|computer|laptop|desktop)"
_FILE_TYPES = (r"pdfs?|images?|pictures?|photos?|screenshots?|videos?|documents?|docs?|spreadsheets?|presentations?|"
               r"zips?|text files?|files?|downloads?")
_PANELS = (r"code editor|editor|code|ai prompt|prompt|ai chat|chat|agent(?: panel)?|terminal(?: panel)?|problems(?: panel)?|"
           r"errors? panel|output(?: panel)?|project files|file explorer|explorer|files panel|source control(?: panel)?|"
           r"git panel|search panel|sidebar")


# Operator actions that only look (a question may route to them): everything else changes something.
READ_ACTIONS = frozenset({"status", "read", "state", "tab_list", "results", "list", "find", "modal", "explain", "info",
                          "active", "url", "title", "detect_login", "verify", "verify_deleted", "media_state", "current_app",
                          "ui_tree", "read_screen", "notifications", "installed", "list_attachments", "read_error",
                          "preview", "audit", "count", "search", "relocate"})
_READ_DEV_OPS = frozenset({"online", "memory", "storage", "packages", "battery", "screen_state", "logcat", "device_info"})


def is_read_action(intent: str, slots: dict) -> bool:
    if not (intent or "").endswith("_op"):
        return False
    action, op = (slots or {}).get("action"), (slots or {}).get("op")
    if intent == "phone_op" and action == "dev":
        return op in _READ_DEV_OPS
    if intent == "system_op":
        return action in ("status", "audit", "running") or (action in ("models", "audio") and op in ("list", "loaded", None))
    if intent == "deliver_op":
        return action == "verify"
    return action in READ_ACTIONS


def _ref(x: str) -> str:
    """'this window' -> '' (the one in front); 'my calculator window' -> 'calculator'."""
    x = re.sub(rf"^(?:{_REF})\s+", "", (x or "").strip())
    x = re.sub(r"\s+(?:window|app|application|program)$", "", x).strip()
    return "" if _PRONOUN.match(x) or x in ("window", "app", "one", "") else x


def _clarify(rid: str, t: str, question: str, intent: str = "clarify") -> RouteDecision:
    return _d(rid, t, intent, {}, lane=RouteLane.CLARIFY, clarification=question)


def _planner(rid: str, t: str) -> RouteDecision:
    from jarvis.core.router.models import ComplexityLevel, ReasonCode, RouteSource
    return RouteDecision(request_id=rid, lane=RouteLane.LANE_2, intent=None, slots={"deliberate_plan": True}, confidence=0.9,
                         source=RouteSource.COMPLEXITY_GATE, complexity=ComplexityLevel.COMPLEX, needs_planner=True,
                         normalized_text=t, reason_code=ReasonCode.MULTI_STEP, candidate_count=0)


# "open calculator on chrome": the thing is opened as a web page in that browser, never as a second desktop app
_BROWSERS = {"chrome": "chrome", "google chrome": "chrome", "edge": "edge", "microsoft edge": "edge", "firefox": "firefox",
             "mozilla firefox": "firefox", "brave": "brave", "opera": "", "vivaldi": "", "browser": "", "the browser": "",
             "my browser": ""}
_WEB_TOOLS = {"calculator": "https://www.google.com/search?q=calculator", "calc": "https://www.google.com/search?q=calculator",
              "maps": "https://maps.google.com", "google maps": "https://maps.google.com",
              "translate": "https://translate.google.com", "google translate": "https://translate.google.com",
              "calendar": "https://calendar.google.com", "google calendar": "https://calendar.google.com",
              "drive": "https://drive.google.com", "google drive": "https://drive.google.com",
              "docs": "https://docs.google.com", "google docs": "https://docs.google.com",
              "sheets": "https://sheets.google.com", "google sheets": "https://sheets.google.com",
              "slides": "https://slides.google.com", "meet": "https://meet.google.com", "google meet": "https://meet.google.com",
              "keep": "https://keep.google.com", "photos": "https://photos.google.com", "news": "https://news.google.com",
              "outlook": "https://outlook.live.com", "teams": "https://teams.microsoft.com", "word": "https://www.office.com/launch/word",
              "excel": "https://www.office.com/launch/excel", "powerpoint": "https://www.office.com/launch/powerpoint",
              "notepad": "https://www.google.com/search?q=online+notepad", "whatsapp": "https://web.whatsapp.com",
              "whatsapp web": "https://web.whatsapp.com", "weather": "https://www.google.com/search?q=weather",
              "clock": "https://www.google.com/search?q=clock", "timer": "https://www.google.com/search?q=timer",
              "stopwatch": "https://www.google.com/search?q=stopwatch"}


def _pc_radio(t, raw, rid, mode):
    """"turn on bluetooth" on this PC: Windows has no supported switch for it, so its Settings page opens and the reply
    says what is left to do - it never claims the radio changed."""
    if re.search(r"\b(?:phone|mobile|android)\b", t):
        return None
    m = re.match(r"^(?:turn|switch)\s+(?P<s>on|off)\s+(?:the\s+|my\s+)?(?P<x>bluetooth|wi-?fi)$|^(?:turn|switch)\s+(?:the\s+|my\s+)?"
                 r"(?P<x2>bluetooth|wi-?fi)\s+(?P<s2>on|off)$|^(?P<v>enable|disable)\s+(?:the\s+|my\s+)?(?P<x3>bluetooth|wi-?fi)$|"
                 r"^(?P<x4>bluetooth|wi-?fi)\s+(?P<s4>on|off)$", t)
    if not m:
        return None
    what = (m.group("x") or m.group("x2") or m.group("x3") or m.group("x4")).replace("-", "")
    state = m.group("s") or m.group("s2") or m.group("s4") or ("on" if m.group("v") == "enable" else "off")
    return _d(rid, t, "open_system_settings", {"page": what, "want": state})


def _app_in_browser(t, raw, rid, mode):
    m = re.match(r"^(?:open|launch|start|load|show|pull\s+up|bring\s+up|go\s+to|visit|use|run)\s+(?:up\s+)?(?:the\s+|a\s+)?"
                 r"(?P<x>[a-z0-9][\w .+&'-]{0,40}?)\s+(?:on|in|using|with|via|inside)\s+(?P<b>(?:google\s+|microsoft\s+|mozilla\s+)?"
                 r"(?:chrome|edge|firefox|brave|opera|vivaldi)|(?:the\s+|my\s+)?browser)(?:\s+browser)?$", t)
    if not m:
        return None
    x = m.group("x").strip()
    if re.match(r"my\s", x):
        return None           # "my resume in chrome": a file of the owner's, found first
    if re.search(r"\b(?:tabs?|window|incognito|private|profile|settings|history|downloads|bookmarks?|extensions?|it|this|that|"
                 r"link|page|file|pdf)\b", x):
        return None           # the browser's own things ("a new tab in chrome", "this link in edge") have their own routes
    from jarvis.tools.system.app_resolver import WEB_SERVICES
    if re.fullmatch(r"[a-z]+ing", x) and x not in _WEB_TOOLS and x not in WEB_SERVICES:
        return None           # "start typing in chrome": an activity there, not a site to open
    browser = _BROWSERS.get(m.group("b").strip(), "")
    if re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/\S*)?", x):
        url = x if x.startswith("http") else f"https://{x}"
    else:
        url = _WEB_TOOLS.get(x) or WEB_SERVICES.get(x) or \
            "https://www.google.com/search?q=" + "+".join(re.findall(r"[a-z0-9+#.]+", x))
    slots = {"url": url, "title": f"{_raw(raw, x)} in {m.group('b').strip().title()}"}
    if browser:
        slots["browser"] = browser
    return _d(rid, t, "open_website", slots)


def _zip(t, raw, rid, mode):
    """'zip report.pdf', 'compress my project folder', 'make a zip of the photos folder'."""
    m = re.match(r"^(?:zip(?:\s+up)?|compress|archive|make\s+(?:a\s+)?zip(?:\s+file)?\s+(?:of|from|with)|put)\s+(?P<x>(?:my\s+|the\s+)?"
                 r"[\w][\w .()-]{0,80}?)(?:\s+(?:into|in(?:to)?\s+a|as\s+a)\s+zip(?:\s+file)?)?$", t)
    if not m or (t.startswith("put ") and not re.search(r"\bzip\b", t)):
        return None
    x = re.sub(r"\s+(?:folder|directory|dir)$", "", re.sub(r"^(?:my|the)\s+", "", m.group("x"))).strip()
    if not x or re.fullmatch(r"(?:it|this|that|them|these|those|everything|all)", x):
        return None
    return _d(rid, t, "compress_files", {"path": _raw(raw, x)})


def match_capability(t: str, raw: str, rid: str, mode: str = "") -> Optional[RouteDecision]:
    for fn in (_dry_run, _danger, _zip, _app_in_browser, _pc_radio, _schedule, _conditional, _orchestration, _device_refs, _messages, _assistant, _workflow,
               _system, _phone, _pc, _ide, _files, _browser, _text, _controls, _windows):
        d = fn(t, raw, rid, mode)
        if d is not None:
            return d
    return None


# ------------------------------------------------------------------------------------------------- conditions
_TELL = r"(?:tell|let|notify|ping|alert|remind|message|text|buzz)\s+(?:me\s+)?(?:know\s+)?(?:(?:on|via|through)\s+" + _PHONE + r"\s+)?"
_EVENT_DONE = r"(?:finishes|finished|completes|completed|is done|is finished|ends|is over|stops|is ready|succeeds|passes)"
_EVENT_FAIL = r"(?:fails|failed|breaks|errors?(?: out)?|crashes|goes wrong)"


def _condition(c: str) -> Optional[dict]:
    """A condition clause -> watch slots (condition, subject, threshold). None when it isn't one we can observe."""
    c = re.sub(r"^(?:the|a|an|my|this|that)\s+", lambda m: m.group(0), c.strip(" ,."))
    m = re.match(r"^(?:the\s+)?(?P<x>[\w' ]+?)\s+(?:button|control|option|link)?\s*(?:becomes|is|gets|turns)\s+"
                 r"(?:enabled|clickable|active|available)$", c)
    if m:
        return {"condition": "control_enabled", "subject": m.group("x").strip()}
    m = re.match(r"^(?:the\s+|a\s+)?(?P<x>[\w' ]*?(?:button|control|option|link|dialog|popup))\s+(?:appears|shows up|is shown|"
                 r"is visible|pops up)$", c)
    if m:
        return {"condition": "control_appears", "subject": m.group("x").strip()}
    m = re.match(r"^(?:a\s+|an\s+)?captcha\s+(?:appears|shows up|pops up|comes up)$", c)
    if m:
        return {"condition": "captcha"}
    m = re.match(rf"^(?:a\s+|any\s+)?(?:new\s+)?(?P<x>{_FILE_TYPES}|[\w-]+\.\w{{2,4}})\s+(?:appears|arrives|lands|shows up|"
                 rf"is saved|gets saved|comes in)(?:\s+(?:here|in (?:this|the|my) (?:folder|downloads)|in downloads))?$", c)
    if m:
        x = re.sub(r"^(?:phone\s+)?", "", m.group("x"))
        return {"condition": "file_appears", "subject": re.sub(r"s$", "", x) if x not in ("downloads",) else ""}
    m = re.match(r"^(?:the|this|that|my)?\s*(?:phone\s+)?(?P<x>screenshot|photo|file|pdf|recording)\s+(?:arrives|lands|comes in|"
                 r"is here|shows up)$", c)
    if m:
        return {"condition": "file_appears", "subject": m.group("x")}
    m = re.match(r"^(?:the|this|that|my)?\s*download(?:s)?\s+(?:finishes|is done|completes|is finished|is complete|ends)$", c)
    if m:
        return {"condition": "download_done"}
    # "nisha messages me", "i get a message from nisha", "anyone texts me": a new one-to-one WhatsApp message
    m = re.match(r"^(?P<x>[a-z][\w'-]{1,20}|anyone|someone|anybody)\s+(?:messages|texts|whatsapps|pings|writes\s+to|replies\s+to|"
                 r"sends)\s+me(?:\s+(?:a\s+)?(?:message|text|msg))?(?:\s+on\s+whats\s*app)?$|^i\s+(?:get|receive)\s+(?:a\s+)?(?:new\s+)?"
                 r"(?:whatsapp\s+)?(?:message|text|msg|reply)\s+from\s+(?P<x2>[a-z][\w'-]{1,20})(?:\s+on\s+whats\s*app)?$", c)
    if m:
        who = m.group("x") or m.group("x2") or ""
        return {"condition": "whatsapp_message", "subject": "" if who in ("anyone", "someone", "anybody") else who}
    m = re.match(rf"^{_PHONE}\s+(?:comes|is|gets|goes)\s+(?:back\s+)?(?:online|connected|reachable)$|^{_PHONE}\s+"
                 rf"(?:reconnects|connects|is back|comes back)$", c)
    if m:
        return {"condition": "phone_connected"}
    m = re.match(rf"^{_PHONE}\s+(?:is|gets)\s+(?:fully\s+)?charged(?:\s+enough)?$|^{_PHONE}(?:'s|s)?\s+(?:battery\s+)?(?:is|reaches|"
                 rf"hits|gets to)\s+(?:at\s+)?(?P<n>\d{{1,3}})\s*%?(?:\s+percent)?$", c)
    if m:
        n = m.groupdict().get("n")
        return {"condition": "battery_above", "subject": "phone", "threshold": float(n) if n else
                (100.0 if "fully" in c else 80.0)}
    m = re.match(r"^(?:the\s+|my\s+)?(?:pc\s+|laptop\s+)?battery\s+(?:drops|falls|goes|gets|is)\s+(?:below|under|to|down to)\s+"
                 r"(?P<n>\d{1,3})\s*%?(?:\s+percent)?$", c)
    if m:
        return {"condition": "battery_below", "threshold": float(m.group("n"))}
    # "my battery hits 85 percent" / "the battery reaches 90%" / "my laptop is fully charged"
    m = re.match(r"^(?:the\s+|my\s+)?(?:pc\s+|laptop\s+)?(?:battery|charge)\s+(?:hits|reaches|gets\s+to|is\s+at|goes\s+(?:up\s+)?to|"
                 r"climbs\s+to)\s+(?P<n>\d{1,3})\s*%?(?:\s+percent)?$|^(?:the\s+|my\s+)?(?:laptop|pc|battery)\s+is\s+fully\s+charged$", c)
    if m:
        n = m.groupdict().get("n")
        return {"condition": "battery_above", "threshold": float(n) if n else 100.0}
    m = re.match(r"^(?:the\s+|this\s+|that\s+)?(?:page|tab|site)\s+(?:changes|updates|reloads|loads|finishes loading)"
                 r"(?:\s+(?:state|status))?$", c)
    if m:
        return {"condition": "page_changed"}
    m = re.match(rf"^(?:the\s+|this\s+|that\s+)?(?:(?P<ide>{_IDES})(?:\s+agent)?|(?:ai\s+)?(?:response|generation|agent|answer|reply))"
                 rf"\s+(?:is\s+)?(?:finishes|finished|is done|completes|stops|ends|is ready)(?:\s+(?:generating|working|thinking))?$", c)
    if m:
        return {"condition": "ide_done", "subject": (m.group("ide") or "").strip()}
    m = re.match(rf"^(?:the\s+|that\s+)?(?P<x>{_APPS}|app|window|that window|this window|it)\s+(?P<e>opens|is open|launches|starts|"
                 rf"closes|is closed|exits|quits|shuts)$", c)
    if m:
        x = _ref(m.group("x"))
        opened = m.group("e") in ("opens", "is open", "launches", "starts")
        return {"condition": "window_opened" if opened else "window_closed", "subject": x}
    m = re.match(rf"^(?:the\s+|this\s+|that\s+|my\s+)?(?:long\s+|current\s+|background\s+)?(?P<x>build|tests?|test run|"
                 rf"task|job|workflow|transfer|upload|install(?:ation)?|it|this)\s+(?P<e>{_EVENT_DONE}|{_EVENT_FAIL})$", c)
    if m:
        x, failed = m.group("x"), bool(re.match(_EVENT_FAIL, m.group("e")))
        kind = "build" if x in ("build", "test", "tests", "test run") else "task"
        return {"condition": f"{kind}_{'failed' if failed else 'done'}",
                "subject": x if x not in ("it", "this", "task", "job") else ""}
    return None


def _then_text(then: str, cond: dict) -> str:
    """'press it' -> 'press the Continue button'; 'open its folder' keeps its reference (resource memory has it)."""
    subj = cond.get("subject") or ""
    then = then.strip(" ,.")
    if subj and re.search(r"\b(?:it|that)$", then) and cond["condition"] in ("control_appears", "control_enabled"):
        then = re.sub(r"\b(?:it|that)$", f"the {subj}", then)
    return then


def _conditional(t, raw, rid, mode):
    # "tell me (on my phone) when X" / "notify me only if X" / "keep monitoring X"
    m = re.match(rf"^{_TELL}(?:only\s+)?(?:when|once|as soon as|if|whenever)\s+(?P<c>.+?)(?:\s+(?:on|via)\s+{_PHONE})?$", t)
    if m:
        cond = _condition(m.group("c"))
        if cond is None:
            return None
        phone = bool(re.search(rf"\b(?:on|via|through)\s+{_PHONE}\b", t))
        if cond["condition"] == "download_done" and not phone:
            return _d(rid, t, "watch_op", {"action": "download_done"})
        if cond["condition"] == "ide_done" and not phone:
            from jarvis.core.router.operator_intents import _ide_name
            return _d(rid, t, "watch_op", {"action": "ide_done", "ide": _ide_name(cond.get("subject", ""))})
        return _d(rid, t, "watch_op", {"action": "when", **cond, "notify_phone": phone})
    m = re.match(r"^(?:keep\s+)?(?:monitor(?:ing)?|watch(?:ing)?|track(?:ing)?|keep an eye on)\s+(?:the\s+|this\s+|my\s+)?"
                 r"(?P<x>build|tests?|download|task|job|transfer)(?:\s+(?:while|as)\s+i\s+.+)?$", t)
    if m:
        x = m.group("x")
        cond = {"condition": "build_done" if x in ("build", "test", "tests") else
                "download_done" if x == "download" else "task_done", "subject": "" if x in ("task", "job") else x}
        if cond["condition"] == "download_done":
            return _d(rid, t, "watch_op", {"action": "download_done"})
        return _d(rid, t, "watch_op", {"action": "when", **cond})
    # "when X, <command>" / "<command> when X" (X observable): the command waits for X, it never runs now
    m = re.match(r"^(?:when|once|as soon as|after|if)\s+(?P<c>[^,]+?),\s*(?:then\s+)?(?P<then>.+)$", t) or \
        re.match(r"^(?P<then>(?:continue|resume|retry|open|show|send|start|run|copy|play|press|click|tap)\b.+?)\s+"
                 r"(?:when|once|as soon as|after)\s+(?P<c>.+)$", t)
    if m:
        cond = _condition(m.group("c"))
        if cond is None:
            return None
        if re.match(r"^(?:stop|pause|don'?t|do not|never|skip|hold)\b", m.group("then")):
            return None                                      # a standing rule ("if it fails, stop"): discourse keeps it
        then = _then_text(_raw(raw, m.group("then")), cond)
        if cond["condition"] == "download_done":
            return _d(rid, t, "watch_op", {"action": "download_done", "then": then})
        return _d(rid, t, "watch_op", {"action": "when", **cond, "then": then})
    # "skip the ad when the button appears": the scoped ad watcher
    if re.match(r"^skip\s+(?:the\s+|any\s+|all\s+)?ads?\s+(?:when|once|as soon as|whenever|if)\s+(?:the\s+)?(?:skip\s+)?"
                r"(?:button|option)\s+(?:appears|shows up|is shown|comes up)$", t):
        return _d(rid, t, "watch_op", {"action": "skip_ads"})
    return None


# ------------------------------------------------------------------------------------------------- orchestration
def _orchestration(t, raw, rid, mode):
    # two activities at once, or a branch on an outcome: the planner builds the graph (never one tool)
    if re.search(r"\b(?:while|meanwhile|in parallel|at the same time|simultaneously)\b", t) and \
            re.match(r"^(?:run|search|find|open|build|test|download|start|check|look)\b", t) and \
            re.search(r"\b(?:while|meanwhile)\s+(?:you|it|the|i'm|i am|they)\b|\bin parallel\b|\bat the same time\b", t):
        return _planner(rid, t)
    if re.match(r"^if\s+.+?(?:,|\bthen\b).+\b(?:otherwise|else|if not)\b", t):
        return _planner(rid, t)
    if re.search(r"\band\s+if\s+(?:it'?s|it\s+is|the|my|there|they|that)\b.{3,}?\b(?:turn|set|lower|raise|open|close|send|tell|"
                 r"start|stop|lock|mute|play|show|notify|switch|dim)\b", t):
        return _planner(rid, t)                              # "check my battery and if it's low turn the brightness down"
    m = re.match(r"^(?:install|download\s+and\s+install|get)\s+(?P<x>[a-z][\w .+-]{1,30}?)\s+(?:and|then|and\s+then)\s+(?:open|launch|"
                 r"start|run)\s+it$", t)
    if m:
        from jarvis.core.router.models import ComplexityLevel, ReasonCode, RouteSource, SubCommand
        name = _raw(raw, m.group("x")).strip()
        subs = [SubCommand(intent="install_software", tool="install_software", arguments={"name": name}),
                SubCommand(intent="open_app", tool="open_app", arguments={"name": name})]
        return RouteDecision(request_id=rid, lane=RouteLane.LANE_0, intent="compound",
                             slots={"steps": ["install_software", "open_app"]}, confidence=0.95, source=RouteSource.EXACT,
                             complexity=ComplexityLevel.COMPOUND, risk="EXTERNAL_EFFECT", normalized_text=t,
                             reason_code=ReasonCode.COMPOUND_COMMAND, subcommands=subs, candidate_count=2)
    if re.match(r"^(?:\W*)(?:show|list|find|open|search|get|play|send|copy|run)\b[^.;!?]+[.;!?]\s+(?:then\s+)?(?:open|show|send|"
                r"play|click|close|copy|run|find)\b", raw.lower().strip(" .")):
        return _planner(rid, t)                              # "Show my PDFs. Open the second one."
    if re.match(r"^(?:save|put|add|write|send)\s+(?:a\s+|the\s+)?(?:summary|digest|recap|gist)\s+of\s+.+\s+(?:to|in|into|as)\s+"
                r"(?:my\s+|a\s+)?(?:notes?|note|doc|document|file)\b", t):
        return _planner(rid, t)                              # summarise first, then save: two capabilities
    return None


# ------------------------------------------------------------------------------------------------- device references
def _device_refs(t, raw, rid, mode):
    # "do this on my phone, not my PC": a device switch with nothing named to do there
    if re.match(rf"^(?:do|run|try|open|continue)\s+(?:this|that|it)\s+(?:on|from)\s+(?:{_PHONE}|{_PC})(?:,?\s+not\s+(?:on\s+)?"
                rf"(?:{_PHONE}|{_PC}))?$", t):
        return _clarify(rid, t, "What should I do there? Tell me the action and I'll run it on that device.")
    # "send it to the device I used earlier": a device described, not named
    if re.match(r"^(?:send|share|move|push|transfer|put)\s+(?:it|this|that|them)\s+(?:to|onto)\s+(?:the\s+)?(?:other|same|previous|"
                r"last|earlier)?\s*(?:device|machine|computer|screen)(?:\s+(?:i|we)\s+(?:used|had|was using)(?:\s+\w+)?)?$", t):
        return _clarify(rid, t, "Which device - your phone or this PC - and what exactly should I send?")
    return None


# ------------------------------------------------------------------------------------------------- messages
_PERSON = r"(?P<who>[a-z][\w'.-]{1,24}(?:\s+[a-z][\w'.-]{1,24})?)"


def _person(who: str, raw: str) -> bool:
    from jarvis.core.router.extended import _looks_like_person, _name_like
    w = who.strip().lower()
    if not w or re.fullmatch(r"(?:the|my|this|that|it|me|you|him|her|them|us|everyone|all|a|an|some|chrome|it\s+to)", w):
        return False
    return _looks_like_person(w, raw) or _name_like(w)


def _said_to_end(raw: str, piece: str) -> str:
    """The message as the owner said it, from where the matched part starts to the end of the request - the matching
    text has courtesy words ("for me", "please") cleaned off, the message must keep them ("don't wait for me")."""
    words = piece.split()
    i = raw.lower().find(" ".join(words[:2]).lower()) if words else -1
    out = raw[i:] if i >= 0 else piece
    out = re.sub(r"(?:[\s,]+(?:on|via|in|through)\s+whats\s*app)?(?:[\s,]+(?:jarvis|please|pls|thanks|thank\s+you))*[\s.!]*$", "",
                 out, flags=re.I)
    return out.strip() or piece


def _messages(t, raw, rid, mode):
    if re.search(r"\b(?:e-?mails?|mail|gmail|inbox|outlook|slack|teams|telegram|sms)\b", t):
        return None
    # "tell arun to call me" / "tell mom not to wait for me": reported speech, kept as said - the WhatsApp composer turns
    # it into the words Arun reads ("Please call me."). ask / remind / let ... know have their own route with the composer.
    m = re.match(r"^tell\s+(?P<who>[a-z][\w'-]{1,20})\s+(?P<msg>(?:not\s+to|to\s+not|to)\s+\S.{1,200})$", t)
    if m and _person(m.group("who"), raw) and m.group("who") not in ("me", "us", "you", "him", "her", "them"):
        d = _d(rid, t, "send_whatsapp_message", {"recipient": _raw(raw, m.group("who")).title(),
                                                 "message": _said_to_end(raw, m.group("msg"))})
        return d.model_copy(update={"context_trace": {"compose_style": "tell", "raw_text": raw}})
    m = re.match(r"^tell\s+(?P<who>[a-z][\w'-]{1,20})\s+(?:that\s+)?(?P<msg>(?!to\b|about\b|me\b|him\b|her\b|them\b|us\b|a\s+joke\b|"
                 r"a\s+story\b)\S.{1,200})$", t)
    if m and _person(m.group("who"), raw) and m.group("who") not in ("me", "us", "you", "him", "her", "them"):
        return _d(rid, t, "send_whatsapp_message", {"recipient": _raw(raw, m.group("who")).title(),
                                                    "message": _said_to_end(raw, m.group("msg"))})
    m = re.match(r"^(?:read|show|check|open|get)\s+(?:me\s+)?(?P<who>[a-z][\w'-]{1,20})(?:'s|s')\s+(?:(?P<n>last|latest|newest|recent|new|unread)\s+)?"
                 r"(?:whatsapp\s+)?(?:message|messages|msg|msgs|text|texts|chat)s?$", t)
    if m and m.group("who") not in ("my", "the", "your", "this", "that", "his", "her", "their", "our"):
        # reading is read-only: any one name is fine - the reader says so if there is no such chat
        one = m.group("n") in ("last", "latest", "newest")
        return _d(rid, t, "read_whatsapp_messages", {"filter": "all", "sender": m.group("who"), "limit": 1 if one else 5})
    # "send farhan can we talk tonight": one person, then the words to send (replies have their own route)
    m = re.match(r"^(?P<v>send|message|msg|text|ping)\s+(?!(?:whats\s*app|message|msg|text|sms|e-?mail|mail|a|an|the|my|this|that|"
                 r"it|them|him|her|to|me|us|file|photo|pic|picture|video|link|location)\b)(?P<who>[a-z][\w'-]{1,20})\s+(?:a\s+(?:message|text|msg)\s+)?"
                 r"(?:saying\s+|that\s+|with\s+)?(?P<msg>(?!to\b|(?:on|in|via|over|through)\s+(?:whats\s*app|telegram|sms|signal|instagram|e-?mail|"
                 r"(?:my\s+|the\s+|his\s+|her\s+)?(?:phone|mobile|pc|laptop|computer))\b|via\b|the\b|my\b|this\b|that\b|it\b|a\s+file)\S.{2,})$", t)
    if m and _person(m.group("who"), raw) and not re.search(r"\.(?:pdf|docx?|xlsx?|pptx?|png|jpe?g|txt|csv|zip|mp4)\b|"
                                                             r"\b(?:file|screenshot|photo|document|folder)\b|"
                                                             r"\bto\s+(?:my\s+|the\s+)?(?:phone|mobile|pc|laptop|computer|desktop)\b|"
                                                             r"^(?:who|which|whom|that)\b|"
                                                             r"^(?:(?:in|after)\s+(?:\d+|an?|half\s+an?)\s+(?:secs?|seconds?|mins?|minutes?|hrs?|hours?|days?)|"
                                                             r"(?:at|by|around|before)\s+(?:\d{1,2}(?::\d\d)?\s*(?:am|pm)?|noon|midnight)(?:\s+(?:today|tomorrow|tonight))?)$",
                                                             m.group("msg")):
        msg = _raw(raw, m.group("msg")).strip()
        return _d(rid, t, "send_whatsapp_message", {"recipient": _raw(raw, m.group("who")).title(), "message": msg})
    m = re.match(rf"^(?:show|read|get|check|open|pull up)\s+(?:me\s+)?(?:my\s+|the\s+)?(?:recent|latest|last|new|unread|today'?s)?\s*"
                 rf"(?:whatsapp\s+)?(?:messages?|texts?|chats?|dms?)\s+(?:from|with|by)\s+{_PERSON}(?:\s+on\s+whatsapp)?$", t)
    if m and m.group("who") not in ("me", "you", "him", "her", "them", "everyone", "today", "yesterday"):
        return _d(rid, t, "read_whatsapp_messages", {"filter": "all", "sender": m.group("who"), "limit": 5})
    m = re.match(rf"^(?:open|show|go to)\s+(?:me\s+)?{_PERSON}(?:'s|s')\s+(?:direct\s+|whatsapp\s+|private\s+|personal\s+)?"
                 rf"(?:chat|conversation|messages|dms?|thread)$", t)
    if m:
        return _d(rid, t, "read_whatsapp_messages", {"filter": "all", "sender": m.group("who"), "limit": 10})
    m = re.match(rf"^(?:handle|take care of|manage|cover|answer|look after|deal with)\s+{_PERSON}(?:'s|s')\s+(?:direct\s+|whatsapp\s+)?"
                 rf"(?:messages|chats|dms|replies)\s+(?P<w>for\s+(?:the\s+next\s+)?\S+\s+(?:minutes?|mins?|hours?|hrs?)|until\s+.+)$", t)
    if m:
        from jarvis.core.router.extended import match_auto_reply
        return match_auto_reply(f"auto reply to {m.group('who')} {m.group('w')}", rid)
    return None


# ------------------------------------------------------------------------------------------------- workflows
_WF = r"(?:workflow|routine|automation)"


def _wf_name(x: str) -> str:
    x = re.sub(rf"\b(?:my|the|this|that|a|an)\b|\b{_WF}s?\b", " ", x or "")
    return " ".join(x.split()) or "this"


def _workflow(t, raw, rid, mode):
    if not re.search(rf"\b{_WF}s?\b|\b(?:tomorrow'?s|scheduled|next)\s+run\b|^run\s+(?:this|it)\s+every\b", t):
        return None
    m = re.match(rf"^(?:run|start|launch|kick off|do|execute)\s+(?P<n>.*?){_WF}(?P<o>\s+(?:using|with|on|for)\s+.+?)?$", t)
    if m:
        slots = {"action": "run", "name": _wf_name(m.group("n"))}
        if m.group("o"):
            slots["override"] = re.sub(r"^\s*(?:using|with|on|for)\s+|\s+instead$", "", m.group("o")).strip()
        return _d(rid, t, "workflow_op", slots)
    m = re.match(rf"^(?:show|tell|preview)\s+(?:me\s+)?(?:exactly\s+)?(?:what\s+)?(?P<n>.*?){_WF}\s+(?:will|would|is going to)\s+do$|"
                 rf"^(?:preview|show|describe|what(?:'s| is) in)\s+(?:me\s+)?(?P<n2>.*?){_WF}(?:\s+steps)?$|"
                 rf"^what (?:does|will|would)\s+(?P<n3>.*?){_WF}\s+do$", t)
    if m:
        return _d(rid, t, "workflow_op", {"action": "preview",
                                          "name": _wf_name(m.group("n") or m.group("n2") or m.group("n3") or "")})
    m = re.match(rf"^(?:save|store|remember|turn)\s+(?:these|those|the last \w+|the|my last \w+)\s+(?:steps|commands|actions)\s+"
                 rf"(?:as|into)\s+(?:a\s+)?(?:new\s+)?{_WF}(?:\s+(?:called|named)\s+(?P<n>.+))?$", t)
    if m:
        return _d(rid, t, "workflow_op", {"action": "create", "name": (m.group("n") or "").strip() or "my workflow",
                                          "steps": []})
    m = re.match(rf"^(?:make|create)\s+(?:a\s+)?(?:copy|duplicate|clone)\s+of\s+(?P<n>.*?){_WF}(?:\s+(?:called|named|as)\s+(?P<new>.+))?$|"
                 rf"^(?:clone|duplicate|copy)\s+(?P<n2>.*?){_WF}(?:\s+(?:as|to)\s+(?P<new2>.+))?$", t)
    if m:
        return _d(rid, t, "workflow_op", {"action": "clone", "name": _wf_name(m.group("n") or m.group("n2") or ""),
                                          "new_name": (m.group("new") or m.group("new2") or "").strip()})
    m = re.match(rf"^(?P<v>disable|enable|turn off|turn on|pause|switch off|switch on|re-?enable)\s+(?P<n>.*?){_WF}(?:\s+again)?$", t)
    if m:
        on = m.group("v") in ("enable", "turn on", "switch on", "reenable", "re-enable")
        return _d(rid, t, "workflow_op", {"action": "enable" if on else "disable", "name": _wf_name(m.group("n"))})
    m = re.match(r"^(?:cancel|delete|remove|skip|stop)\s+(?:tomorrow'?s|the\s+scheduled|the\s+next|next|the)\s+(?:scheduled\s+)?run"
                 r"(?:\s+of\s+(?P<n>.+))?$|^(?:cancel|remove|clear)\s+(?:the\s+)?schedule\s+(?:for|of)\s+(?P<n2>.+)$", t)
    if m:
        return _d(rid, t, "workflow_op", {"action": "cancel_schedule", "name": _wf_name(m.group("n") or m.group("n2") or "")
                                          if (m.group("n") or m.group("n2")) else ""})
    m = re.match(rf"^(?:run|schedule|repeat)\s+(?P<n>this|it|.*?{_WF})\s+(?P<w>every\s+.+|(?:on\s+)?(?:weekdays|weekends|daily)"
                 rf"(?:\s+at\s+.+)?|at\s+\d.+)$", t)
    if m:
        return _d(rid, t, "workflow_op", {"action": "schedule", "name": _wf_name(m.group("n")), "when": m.group("w")})
    if re.match(rf"^(?:list|show)\s+(?:me\s+)?(?:all\s+)?(?:my\s+)?(?:saved\s+)?{_WF}s$|^what {_WF}s do i have$", t):
        return _d(rid, t, "workflow_op", {"action": "list"})
    return None


# ------------------------------------------------------------------------------------------------- system state
def _system(t, raw, rid, mode):
    if re.search(r"\b(?:phone|mobile|android)\b", t) and not re.search(r"\bpc\b", t):
        return None                                          # the phone's state: the phone family
    m = re.match(r"^(?:how much|what(?:'s| is)(?: the)?)\s+(?:free\s+)?(?:disk|storage|drive|hard drive|ssd)\s*(?:space)?\s*"
                 r"(?:is\s+)?(?:left|free|available|remaining|used)?(?:\s+on\s+(?:the\s+|my\s+)?(?:pc|computer|laptop|c drive))?$|"
                 r"^(?:how full is|check)\s+(?:my\s+|the\s+)?(?:disk|drive|c drive|storage)$", t)
    if m:
        return _d(rid, t, "system_op", {"action": "status", "what": "disk"})
    if re.match(r"^(?:how long has|since when has)\s+(?:the\s+|my\s+|this\s+)?(?:pc|computer|laptop|machine|system)\s+been\s+"
                r"(?:on|up|running)$|^(?:what(?:'s| is)\s+(?:the\s+)?)?(?:system\s+|pc\s+)?uptime$|^when did (?:the |my )?(?:pc|computer) "
                r"(?:boot|start)(?: up)?$", t):
        return _d(rid, t, "system_op", {"action": "status", "what": "uptime"})
    m = re.match(r"^(?:send|give|show|tell)\s+me\s+(?:the\s+)?(?:pc'?s?\s+|computer'?s?\s+|system\s+)?(?P<w>cpu|ram|memory|gpu|disk)"
                 r"(?:\s*(?:/|and|&|,)\s*(?:cpu|ram|memory|gpu|disk))*\s+(?:status|usage|load)$", t)
    if m:
        return _d(rid, t, "system_op", {"action": "status", "what": "all"})
    if re.match(r"^(?:which|what)\s+(?:audio|sound|output|speaker)\s+device\s+(?:is|am i)\s+(?:active|being used|in use|"
                r"selected|on|using)$|^(?:list|show)\s+(?:me\s+)?(?:my\s+|the\s+)?(?:audio|sound|output)\s+devices$|"
                r"^where is (?:the )?sound (?:coming|going)(?: out)?(?: from| to)?$", t):
        return _d(rid, t, "system_op", {"action": "audio", "op": "list"})
    m = re.match(r"^(?:switch|change|move|set)\s+(?:the\s+)?(?:audio|sound|output|playback)?\s*(?:output\s+)?(?:to|over to)\s+"
                 r"(?:my\s+|the\s+)?(?P<d>headphones?|headset|earbuds|earphones|airpods|speakers?|bluetooth (?:speaker|headphones)|"
                 r"monitor speakers|[\w ]+ (?:headphones|speakers?|headset))$", t)
    if m:
        return _d(rid, t, "system_op", {"action": "audio", "op": "switch", "target": m.group("d")})
    m = re.match(r"^(?:which|what)\s+(?:local\s+|ollama\s+|ai\s+)?models\s+(?:are|do i have)\s+(?:ready|installed|available|loaded|"
                 r"running|downloaded)(?:\s+(?:right now|now|locally))?$|^(?:list|show)\s+(?:me\s+)?(?:my\s+|the\s+)?(?:local\s+|ollama\s+)"
                 r"?models$", t)
    if m:
        return _d(rid, t, "system_op", {"action": "models", "op": "loaded" if re.search(r"loaded|running", t) else "list"})
    m = re.match(r"^(?:unload|free|release|drop)\s+(?:the\s+)?(?P<m>[\w.:-]+)\s+model(?:\s+(?:when|once|after)\s+.+)?$", t)
    if m:
        return _d(rid, t, "system_op", {"action": "models", "op": "unload", "target": m.group("m")})
    m = re.match(r"^(?:keep|make sure)\s+(?:the\s+)?(?:small\s+|fast\s+|big\s+)?(?P<m>planner|chat|fast|vision|embed\w*|[\w.:-]+)"
                 r"(?:\s+model)?\s+(?:is\s+)?(?:warm|loaded|ready|hot)(?:\s+for\s+.+)?$|^(?:warm up|preload|load)\s+(?:the\s+)?"
                 r"(?P<m2>planner|chat|fast|vision|[\w.:-]+)\s+model$", t)
    if m:
        return _d(rid, t, "system_op", {"action": "models", "op": "warm", "target": m.group("m") or m.group("m2")})
    if re.match(r"^(?:tell me|show me|list|what(?:'s| is| are))\s+(?:which|what)?\s*(?:required\s+)?(?:capabilit(?:y|ies)|tools?|"
                r"permissions?)\s+(?:is|are)\s+(?:unavailable|missing|not available|blocked)(?:\s+for\s+.+)?$|^(?:what can'?t you do|"
                r"what are you allowed to (?:use|do)) (?:here|for this(?: task)?)$|^(?:run a\s+)?capability (?:audit|check)$", t):
        return _d(rid, t, "system_op", {"action": "audit"})
    return None


# ------------------------------------------------------------------------------------------------- phone
_SETTINGS = {"wi-fi": "wifi", "wifi": "wifi", "bluetooth": "bluetooth", "display": "display", "sound": "sound",
             "battery": "battery", "storage": "storage", "location": "location", "notification": "notifications",
             "notifications": "notifications", "developer": "developer", "app": "app_info", "info": "app_info"}


def _phone(t, raw, rid, mode):
    phone = bool(re.search(r"\b(?:phone|mobile|android|apk)\b", t)) or mode == "phone"
    # objects that exist only on the phone (or the phone named): notification, APK, screen recording, recents
    m = re.match(r"^(?:find|show|read|list|check|get)\s+(?:me\s+)?(?:only\s+)?(?:the\s+)?(?:latest\s+|last\s+|new\s+|recent\s+)?"
                 r"(?P<app>[\w]+\s+)?notifications?(?:\s+from\s+(?P<who>[\w ]+?))?(?:" + _ON_PHONE + r")?$", t)
    if m and (m.group("app") or m.group("who")):
        app = (m.group("app") or "").strip()
        if app in ("my", "all", "the", "phone", "this", "those", "any"):
            app = ""
        who = (m.group("who") or "").strip()
        if re.fullmatch(r"(?:my\s+|the\s+)?(?:phone|mobile|android|device)", who):
            who = ""
        if not app and not who:
            return _d(rid, t, "android_notifications", {})
        if who in ("this contact", "that contact", "them", "him", "her"):
            return _clarify(rid, t, "Which contact's notifications?")
        return _d(rid, t, "phone_op", {"action": "notifications", "app": app, "arg": who})
    if re.match(r"^(?:what|which|any)\s+(?:new\s+)?notifications\s+(?:came in|arrived|have i got|do i have|are there|did i get)"
                r"(?:\s+(?:today|recently|just now))?(?:" + _ON_PHONE + r")?$", t):
        return _d(rid, t, "android_notifications", {})
    m = re.match(r"^(?P<v>open|dismiss|clear|swipe away|close|remove)\s+(?:the\s+|that\s+|this\s+)?(?P<app>[\w]+\s+)?notification"
                 r"(?:\s+(?:i|you)\s+just\s+(?:mentioned|read|said))?(?:" + _ON_PHONE + r")?$", t)
    if m:
        app = (m.group("app") or "").strip()
        app = "" if app in ("that", "this", "the", "latest", "last", "my") else app
        act = "open_notification" if m.group("v") == "open" else "dismiss_notification"
        return _d(rid, t, "phone_op", {"action": act, "app": app})
    if re.search(r"\bapk\b", t):
        m = re.match(r"^(?:install|sideload|push and install)\s+(?:my\s+|the\s+)?(?:latest\s+|newest\s+|last\s+)?(?P<x>[\w .-]*?)\s*apk"
                     r"(?:" + _ON_PHONE + r")?$", t)
        if m:
            return _d(rid, t, "phone_op", {"action": "dev", "op": "install_apk", "arg": m.group("x").strip() or "latest"})
    m = re.match(r"^(?P<v>start|begin|stop|end|finish)\s+(?:the\s+)?(?:phone\s+)?screen\s*record(?:ing)?(?:" + _ON_PHONE + r")?$|"
                 r"^(?P<v2>stop|end)\s+(?:the\s+)?(?:phone\s+)?recording(?:" + _ON_PHONE + r")?$|^record\s+(?:my\s+|the\s+)?phone(?:'s)?"
                 r"\s+screen$", t)
    if m:
        v = m.group("v") or m.group("v2") or "start"
        if m.group("v2") and not phone and not _phone_recording():
            return None                                      # "stop recording" with no phone recording: voice/dictation
        return _d(rid, t, "phone_op", {"action": "record", "op": "stop" if v in ("stop", "end", "finish") else "start"})
    m = re.match(r"^(?:show|open)\s+(?:me\s+)?(?:the\s+)?recent\s+apps(?:" + _ON_PHONE + r")?$", t)
    if m:
        return _d(rid, t, "phone_op", {"action": "key", "key": "recents"})
    if re.match(rf"^(?:go|switch)\s+back\s+to\s+(?:the\s+)?(?:previous|last|other)\s+(?:phone\s+)?app(?:{_ON_PHONE})?$", t) and \
            (phone or "phone app" in t):
        return _d(rid, t, "phone_op", {"action": "key", "key": "previous_app"})
    if re.match(r"^bring\s+(?:the\s+)?phone(?:'s)?\s+app\s+(?:back\s+)?(?:to\s+the\s+front|up)(?:\s+again)?$", t):
        return _d(rid, t, "phone_op", {"action": "key", "key": "previous_app"})
    m = re.match(r"^(?P<v>answer|pick\s+up|accept|take|hang\s+up|end|reject|decline|cut)\s+(?:the\s+|this\s+|my\s+)?(?:phone\s+|incoming\s+)?"
                 r"call(?:\s+on\s+(?:my\s+)?phone)?$|^hang\s+up(?:\s+the\s+(?:phone|call))?$", t)
    if m:
        v = (m.group("v") or "hang up")
        return _d(rid, t, "phone_op", {"action": "key", "key": "answer_call" if v in ("answer", "pick up", "accept", "take")
                                       else "end_call"})
    if re.match(rf"^open\s+(?:the\s+)?camera(?:\s+app)?{_ON_PHONE}$", t):
        return _d(rid, t, "phone_op", {"action": "key", "key": "camera"})
    # state questions about the phone
    if re.match(rf"^(?:what(?:'s| is)|which (?:song|track|video|media) is)\s+playing\s+on\s+{_PHONE}$", t):
        return _d(rid, t, "phone_op", {"action": "media_state"})
    if re.match(rf"^(?:what|which)\s+app\s+(?:is|am i)\s+(?:active|open|in front|running|using|on)\s+(?:on|in)\s+{_PHONE}$|"
                rf"^what(?:'s| is)\s+(?:open|on screen|in front)\s+on\s+{_PHONE}$", t):
        return _d(rid, t, "android_quick_action", {"action": "current_app"})
    if re.match(rf"^what\s+(?:file|document|photo|page)\s+(?:was|am)\s+i\s+(?:viewing|looking at|reading|using)\s+on\s+{_PHONE}$", t):
        return _clarify(rid, t, "Android doesn't tell other apps which file you viewed - which file was it, or shall I "
                                "list the phone's recent downloads?")
    m = re.match(rf"^(?:how much)\s+(?P<w>ram|memory|storage|space)\s+(?:is\s+)?(?:the\s+|my\s+)?(?:phone|mobile)\s+(?:is\s+)?"
                 rf"(?:using|used|free|left)$|^(?:how much)\s+(?P<w2>ram|memory|storage|space)\s+is\s+(?:free|left|used)\s+on\s+{_PHONE}$", t)
    if m:
        w = m.group("w") or m.group("w2")
        return _d(rid, t, "phone_op", {"action": "dev", "op": "memory" if w in ("ram", "memory") else "storage"})
    if re.match(rf"^is\s+{_PHONE}\s+(?:online|on the internet|reachable)$", t):
        return _d(rid, t, "phone_op", {"action": "dev", "op": "online"})
    m = re.match(rf"^is\s+(?P<a>[\w ]+?)\s+installed(?:{_ON_PHONE})?$", t)
    if m and phone:
        return _d(rid, t, "phone_op", {"action": "installed", "target": m.group("a")})
    if re.match(rf"^(?:what|which)\s+apps\s+(?:are|do i have)\s+installed\s+on\s+{_PHONE}$|^(?:list|show)\s+(?:the\s+)?(?:installed\s+)?"
                rf"apps\s+on\s+{_PHONE}$", t):
        return _d(rid, t, "phone_op", {"action": "dev", "op": "packages"})
    m = re.match(rf"^(?:what\s+controls|which\s+buttons|what(?:'s| is)\s+(?:tappable|clickable))\s+(?:are\s+)?(?:visible|there|here|"
                 rf"on\s+(?:the\s+)?screen)(?P<p>{_ON_PHONE})?$", t)
    if m:
        if m.group("p") or mode == "phone":
            return _d(rid, t, "phone_op", {"action": "ui_tree"})
        return _d(rid, t, "ui_op", {"action": "read", "target": ""})
    if re.match(rf"^(?:read|summari[sz]e|describe|what(?:'s| is))\s+(?:me\s+)?(?:what(?:'s| is)\s+)?(?:visible|on\s+(?:the\s+)?screen|"
                rf"(?:the|this)\s+screen)\s+(?:on\s+{_PHONE})$|^(?:read|summari[sz]e)\s+(?:my\s+|the\s+)?phone(?:'s)?\s+screen$", t):
        return _d(rid, t, "phone_op", {"action": "read_screen"})
    # media volume on the phone
    m = re.match(rf"^(?:set|put|turn)\s+(?:the\s+)?(?:phone(?:'s)?\s+)?(?:media\s+)?volume\s+(?:on\s+{_PHONE}\s+)?(?:to\s+)?(?P<v>\d{{1,3}})"
                 rf"\s*(?:%|percent)(?:{_ON_PHONE})?$|^(?:set|put|turn)\s+{_PHONE}(?:'s)?\s+(?:media\s+)?volume\s+(?:to\s+)?(?P<v2>\d{{1,3}})"
                 rf"\s*(?:%|percent)$", t)
    if m and phone:
        return _d(rid, t, "phone_op", {"action": "volume", "value": float(m.group("v") or m.group("v2"))})
    if re.match(rf"^unmute\s+(?:the\s+)?{_PHONE}(?:\s+media)?$", t):
        return _d(rid, t, "android_key", {"key": "volume_up"})
    # phone settings pages
    m = re.match(rf"^open\s+(?:the\s+)?(?P<p>[\w-]+)\s+(?:settings|info|page)\s+(?:for|of)\s+(?:this|that|the|my)\s+(?P<a>[\w ]*?)app"
                 rf"(?:{_ON_PHONE})?$|^open\s+(?:the\s+)?(?:app\s+)?info\s+for\s+(?:this|that|the)\s+app$", t)
    if m and phone:
        page = _SETTINGS.get((m.groupdict().get("p") or "info").lower(), "app_info")
        return _d(rid, t, "phone_op", {"action": "settings", "target": page, "app": ""})
    # move things between phone and PC
    m = re.match(rf"^(?:bring|get|pull|copy|move|show|send|transfer)\s+(?:me\s+)?(?:the\s+|that\s+|this\s+|my\s+)?(?P<w>latest|last|"
                 rf"newest|today'?s|recent|selected)?\s*(?:phone\s+)?(?P<k>screenshots?|photos?|pictures?|recordings?|files?|"
                 rf"downloads?)(?:\s+(?:i|you)\s+just\s+took)?(?:\s+from\s+{_PHONE})?\s+(?:here|to\s+(?:my\s+|the\s+|this\s+)?"
                 rf"(?:pc|computer|laptop|desktop)|over|across)(?:\s+(?:here|now))?$", t)
    if m and (phone or "phone" in t):
        from jarvis.core.router.extended import match_phone_transfer
        known = match_phone_transfer(t, raw, rid)       # the existing ADB transfer covers counted / named pulls
        if known is not None:
            return known
        k = re.sub(r"s$", "", m.group("k"))
        when = {"today's": "today", "todays": "today", "selected": "selected"}.get(m.group("w") or "", "latest")
        if k in ("photo", "picture"):
            k = "photo"
        return _d(rid, t, "phone_op", {"action": "pull", "target": k, "arg": when})
    if re.match(rf"^(?:show|open)\s+(?:me\s+)?(?:that|the|this)\s+phone\s+screenshot(?:\s+here)?$|^show\s+me\s+the\s+screenshot\s+i\s+"
                rf"just\s+took(?:{_ON_PHONE})$", t):
        return _d(rid, t, "phone_op", {"action": "pull", "target": "screenshot", "arg": "latest"})
    if re.match(rf"^(?:bring|get|copy|paste|grab|fetch|pull)\s+(?:me\s+)?(?:the\s+|my\s+)?(?:copied text|clipboard(?: text)?|text i (?:just\s+)?copied)\s+"
                rf"(?:from|on|off)\s+{_PHONE}"
                rf"(?:\s+(?:here|to\s+(?:my\s+)?(?:pc|computer)))?$", t):
        return _d(rid, t, "phone_op", {"action": "clipboard"})
    m = re.match(rf"^(?:open|continue|show|load|send)\s+(?:this|the|that)\s+(?P<o>url|link|page|tab|site|article)\s+on\s+{_PHONE}$|"
                 rf"^continue\s+(?:this|it|reading|watching)\s+on\s+{_PHONE}$", t)
    if m:
        return _d(rid, t, "phone_op", {"action": "open_url"})
    if re.match(rf"^(?:open|bring|show|continue)\s+(?:the|that)\s+(?:page|tab|link|site)\s+(?:from|on)\s+{_PHONE}\s+(?:here|on\s+"
                rf"(?:my\s+|the\s+|this\s+)?(?:pc|computer|laptop))$", t):
        return _d(rid, t, "phone_op", {"action": "pc_url"})
    if re.match(rf"^(?:did|has)\s+(?:the|that|this|my)\s+(?:file|screenshot|photo|pdf)\s+(?:actually\s+|really\s+)?(?:reach|arrive on|"
                rf"get to|land on|make it to)\s+{_PHONE}$", t):
        return _d(rid, t, "deliver_op", {"action": "verify", "resource": "it", "to": "phone"})
    # phone surface controls (named phone, or the phone session in front)
    if phone:
        m = re.match(rf"^(?:find|locate|where is)\s+(?:the\s+)?(?P<x>.+?)(?:{_ON_PHONE})?$", t)
        if m and re.search(r"\b(?:button|field|box|link|toggle|switch|icon|tab|option)\b", m.group("x")):
            return _d(rid, t, "phone_op", {"action": "find", "target": m.group("x")})
        m = re.match(rf"^(?:clear|empty|wipe)\s+(?:this|the|that)\s+(?P<x>(?:text\s?box|field|box|input|search bar))(?:{_ON_PHONE})?$", t)
        if m:
            return _d(rid, t, "phone_op", {"action": "clear", "target": m.group("x")})
        m = re.match(rf"^(?:swipe|scroll)\s+(?P<d>up|down|left|right)(?:\s+(?:on|in)\s+(?:this|the)\s+(?:list|page|screen))?"
                     rf"(?:{_ON_PHONE})?$", t)
        if m and t.startswith("swipe"):
            return _d(rid, t, "phone_op", {"action": "swipe", "target": m.group("d")})
        m = re.match(rf"^(?:stop|force stop|kill|close|quit)\s+(?P<a>[\w ]+?)(?:{_ON_PHONE})$", t)
        if m:
            return _d(rid, t, "phone_op", {"action": "close_app", "target": _ref(m.group("a"))})
        m = re.match(rf"^(?:restart|relaunch|reopen|reload)\s+(?P<a>[\w ]+?)(?:{_ON_PHONE})$", t)
        if m:
            return _d(rid, t, "phone_op", {"action": "relaunch", "target": _ref(m.group("a"))})
        m = re.match(rf"^(?:show|read|get|open)\s+(?:me\s+)?(?:the\s+)?(?P<a>[\w ]*?)\s*(?:app\s+)?logs?(?:{_ON_PHONE})?$", t)
        if m:
            return _d(rid, t, "phone_op", {"action": "dev", "op": "logcat", "arg": _ref(m.group("a"))})
    # "swipe up on this list": swiping is a touch gesture - the phone
    m = re.match(r"^swipe\s+(?P<d>up|down|left|right)(?:\s+(?:on|in)\s+(?:this|the)\s+(?:list|page|screen|feed))?$", t)
    if m:
        return _d(rid, t, "phone_op", {"action": "swipe", "target": m.group("d")})
    # "stop / restart my (test) app": the app the owner is developing runs on the phone
    m = re.match(r"^(?P<v>stop|force stop|kill|restart|relaunch)\s+(?:my\s+(?:test\s+|debug\s+|dev\s+)?|(?:the\s+)?(?:test|debug|dev)\s+)app$", t)
    if m:
        act = "close_app" if m.group("v") in ("stop", "force stop", "kill") else "relaunch"
        return _d(rid, t, "phone_op", {"action": act, "target": "my app"})
    if re.match(r"^(?:show|read|get|open)\s+(?:me\s+)?my\s+(?:test\s+|debug\s+)?app(?:'s)?\s+logs?$", t):
        return _d(rid, t, "phone_op", {"action": "dev", "op": "logcat", "arg": "my app"})
    return None


def _phone_recording() -> bool:
    try:
        from jarvis.core.operator.device import get_device_operator
        return bool(getattr(get_device_operator(), "_recording", None))
    except Exception:
        return False


# ------------------------------------------------------------------------------------------------- IDE
_CODE_EXT = r"py|js|ts|tsx|jsx|java|kt|go|rs|rb|php|cs|cpp|c|h|hpp|swift|json|ya?ml|toml|md|html|css|scss|sql|sh|ps1"


def _ide(t, raw, rid, mode):
    ide_named = re.search(rf"\b(?:{_IDES})\b", t)
    from jarvis.core.router.operator_intents import _ide_name
    ide = _ide_name(t) if ide_named else ""
    s = re.sub(rf"\s+(?:in|on)\s+(?:the\s+)?(?:{_IDES})$", "", t)
    if re.fullmatch(r"(?:(?:put|move|set|give)\s+(?:the\s+)?focus|focus|go back|switch)", s):
        s = t                                                # "put focus in the code editor": the editor is the object
    m = re.match(r"^(?:close)\s+(?:this|the|that|current)\s+(?:file\s+|editor\s+)tab$", s)
    if m:
        return _d(rid, t, "ide_op", {"action": "tab_close", "ide": ide})
    m = re.match(r"^(?:go|switch|move|jump)\s+to\s+(?:the\s+)?(?P<w>next|previous|prior|last)\s+(?:file\s+|editor\s+)tab$", s)
    if m:
        return _d(rid, t, "ide_op", {"action": "tab_next" if m.group("w") == "next" else "tab_previous", "ide": ide})
    m = re.match(rf"^(?:go|jump|switch|navigate)\s+to\s+(?P<f>[\w./\\-]+\.(?:{_CODE_EXT}))$", s)
    if m:
        return _d(rid, t, "ide_op", {"action": "open_file", "ide": ide, "text": _raw(raw, m.group("f"))})
    m = re.match(rf"^(?:put|move|set|give)\s+(?:the\s+)?focus\s+(?:in|on|to|into)\s+(?:the\s+)?(?P<p>{_PANELS})$|"
                 rf"^(?:focus|go to|switch to)\s+(?:the\s+)?(?P<p2>{_PANELS})$|"
                 rf"^(?:open|show|toggle|reveal)\s+(?:me\s+)?(?:the\s+)?(?P<p3>terminal panel|problems(?: panel)?|errors? panel|"
                 rf"output panel|project files|files panel|source control(?: panel)?|git panel|search panel|agent panel|ai chat)$|"
                 rf"^continue\s+in\s+(?:this|the)\s+(?:same\s+)?(?:ai\s+)?(?P<p4>chat|conversation)$", s)
    if m:
        p = (m.group("p") or m.group("p2") or m.group("p3") or m.group("p4") or "").replace(" panel", "")
        if m.group("p2") and p in ("code", "chat", "terminal", "editor", "explorer", "file explorer", "sidebar", "output",
                                   "agent", "prompt") and not (ide_named or mode == "ide"):
            return None                                      # "switch to the terminal": an app, or ask
        panel = {"code editor": "editor", "code": "editor", "ai prompt": "agent", "prompt": "agent", "ai chat": "agent",
                 "chat": "agent", "conversation": "agent", "agent": "agent", "project files": "explorer",
                 "file explorer": "explorer", "files": "explorer", "errors": "problems", "error": "problems",
                 "git": "source_control", "source control": "source_control"}.get(p, p)
        return _d(rid, t, "ide_op", {"action": "focus", "ide": ide, "text": panel})
    if re.match(r"^(?:what|which)\s+files?\s+(?:are|is)\s+attached(?:\s+to\s+(?:the|this)\s+prompt)?$|^(?:list|show)\s+(?:me\s+)?"
                r"(?:the\s+)?attachments$", s):
        return _d(rid, t, "ide_op", {"action": "list_attachments", "ide": ide})
    if re.match(r"^(?:send|submit)\s+(?:this|the|my)\s+prompt$", s):
        return _d(rid, t, "ide_op", {"action": "send", "ide": ide})
    if re.match(r"^(?:stop|cancel|interrupt|abort|halt)\s+(?:the\s+)?(?:current\s+|ai\s+|agent'?s?\s+)?(?:generation|generating|"
                r"response|answer|agent run)$|^stop\s+generating$", s):
        return _d(rid, t, "ide_op", {"action": "cancel", "ide": ide})
    m = re.match(r"^(?P<v>read|show|tell me|copy)\s+(?:me\s+)?(?:the\s+)?(?:latest|last|current|newest)\s+(?:ai\s+|agent\s+)?"
                 r"(?:response|reply|answer|output)$", s)
    if m:
        return _d(rid, t, "ide_op", {"action": "copy_response" if m.group("v") == "copy" else "read", "ide": ide})
    if re.match(r"^(?:start|open|begin|create)\s+(?:a\s+)?(?:new|fresh)\s+(?:ai\s+|agent\s+)?(?:conversation|chat|session|thread)$", s):
        return _d(rid, t, "ide_op", {"action": "key", "ide": ide, "name": "new_chat"})
    m = re.match(r"^(?:go|jump|navigate)\s+to\s+(?:the\s+)?definition(?:\s+of\s+(?:this|the|that)\s+(?:symbol|function|class|method|"
                 r"variable))?$|^(?:show|find|list|peek)\s+(?:all\s+)?(?:the\s+)?(?P<r>references|usages|callers)\s+(?:for|of|to)\s+(?:this|the|"
                 r"that)\s+(?:symbol|function|class|method|variable)$", s)
    if m:
        return _d(rid, t, "ide_op", {"action": "references" if m.groupdict().get("r") else "definition", "ide": ide})
    m = re.match(r"^rename\s+(?:this|the|that)\s+(?:symbol|variable|function|method|class|identifier|field|parameter)\s+(?:to|as)\s+"
                 r"(?P<n>[a-z_$][\w$]*)$", s)
    if m:
        return _d(rid, t, "ide_op", {"action": "rename", "ide": ide, "text": _raw(raw, m.group("n"))})
    if re.match(r"^rename\s+(?:this|the|that)\s+(?:symbol|variable|function|method|class|identifier)$", s):
        return _clarify(rid, t, "What should the new name be?", intent="ide_op")
    m = re.match(r"^(?P<v>format|save|reformat|tidy|prettify)\s+(?:this|the|current|my)\s+(?:file|code|document|source)$|"
                 r"^save\s+(?:everything|all(?:\s+(?:the\s+)?files)?|all open files)$", s)
    if m:
        if s.startswith("save"):
            return _d(rid, t, "ide_op" if (re.search(r"everything|all", s) or ide_named or mode == "ide") else "text_op",
                      {"action": "save_all", "ide": ide} if re.search(r"everything|all", s) else
                      ({"action": "save", "ide": ide} if (ide_named or mode == "ide") else {"action": "save"}))
        return _d(rid, t, "ide_op", {"action": "format", "ide": ide})
    m = re.match(r"^(?:open|show|find)\s+(?:the\s+)?(?:docs|documentation|reference)\s+(?:for|of|on)\s+(?:this|the|that)\s+"
                 r"(?:symbol|function|class|method|api|library|module)$", s)
    if m:
        return _d(rid, t, "ide_op", {"action": "docs", "ide": ide})
    if (ide_named or mode == "ide") and re.match(r"^what(?:'s| is| does)\s+(?:this|that|the current)\s+error(?:\s+mean)?$|"
                                                r"^read\s+(?:me\s+)?(?:this|the|current)\s+error$", s):
        return _d(rid, t, "ide_op", {"action": "read_error", "ide": ide})
    if re.match(r"^copy\s+(?:this|the|current|that)\s+(?:current\s+)?error(?:\s+message)?$", s):
        return _d(rid, t, "ide_op", {"action": "copy_error", "ide": ide})
    m = re.match(r"^(?:switch|change|move)\s+to\s+(?:the\s+|my\s+)?(?P<p>[\w-]+(?:\s+[\w-]+)?)\s+(?:project|repo|repository|"
                 r"workspace)$", s)
    if m:
        return _d(rid, t, "ide_op", {"action": "open_project", "ide": ide, "text": m.group("p")})
    m = re.match(r"^(?:find|show|go to|locate|where(?:'s| is))\s+(?:me\s+)?(?:the\s+)?(?P<x>[\w ]+?)\s+(?P<k>handler|function|method|"
                 r"class|component|endpoint|route|controller|service|module|hook|test)$", s)
    if m and m.group("x") not in ("this", "that", "the"):
        return _d(rid, t, "code_search", {"query": f"{m.group('x')} {m.group('k')}"})
    if re.match(r"^(?:stop|cancel|kill|abort)\s+(?:the\s+)?(?:running\s+)?(?:tests?|test run|build|dev server|server)$", s):
        return _d(rid, t, "project_stop", {})
    if re.match(r"^(?:run|start|execute)\s+(?:the\s+|my\s+|all\s+)?(?:project\s+|unit\s+)?tests$", s):
        return _d(rid, t, "run_project_tests", {})
    if re.match(r"^(?:show|what(?:'s| is| are))\s+(?:me\s+)?(?:the\s+)?(?:current\s+)?(?:git\s+)?(?:diff|changes i made|uncommitted "
                r"changes)$", s):
        return _d(rid, t, "git_diff", {})
    m = re.match(r"^(?:attach|add)\s+(?:the\s+)?(?:current|latest|last|new)\s+(?P<r>screenshot|file|image)$", s)
    if m:
        return _d(rid, t, "ide_op", {"action": "attach", "ide": ide, "resource": m.group("r")})
    return None


# ------------------------------------------------------------------------------------------------- files
_TYPES = {"pdf": "pdf", "pdfs": "pdf", "image": "images", "images": "images", "picture": "images", "pictures": "images",
          "photo": "photos", "photos": "photos", "video": "videos", "videos": "videos", "document": "documents",
          "documents": "documents", "doc": "documents", "docs": "documents", "spreadsheet": "spreadsheet", "zip": "zip"}
_HERE = r"(?:here|in\s+(?:this|the\s+current|the)\s+folder|in\s+(?:my\s+)?(?:downloads|documents|desktop|pictures|videos))"


def _where(t: str) -> str:
    m = re.search(r"\bin\s+(?:my\s+)?(downloads|documents|desktop|pictures|videos)\b", t)
    if m:
        return m.group(1)
    return "here" if re.search(r"\bhere\b|\b(?:this|the current) folder\b", t) else ""


_EXT = r"pdf|docx?|xlsx?|pptx?|csv|txt|md|png|jpe?g|gif|mp4|mkv|mp3|wav|zip|rar|py|js|ts|json|html|exe|msi|apk"


def _files(t, raw, rid, mode):
    m = re.match(rf"^(?:get\s+rid\s+of|trash|bin|throw\s+away|delete|remove|erase)\s+(?:the\s+(?:file\s+)?|my\s+)?"
                 rf"(?P<f>[\w .()'&+-]{{1,60}}\.(?:{_EXT}))$", t)
    if m:
        return _d(rid, t, "delete_file", {"path": _raw(raw, m.group("f"))})
    m = re.match(r"^(?:find|show|list|look\s+for|check\s+for|scan\s+for|search\s+for)\s+(?:me\s+)?(?:any\s+|the\s+|all\s+)?(?:duplicate|"
                 r"duplicated|identical|repeated)\s+(?:files|copies|photos|pictures|documents)?\s*(?:in|inside|under)?\s*(?:my\s+|the\s+)?"
                 r"(?P<d>[\w ]*?)(?:\s+folder)?$|^(?:do\s+i\s+have|are\s+there)\s+(?:any\s+)?duplicate\s+files\s+in\s+(?:my\s+|the\s+)?"
                 r"(?P<d2>[\w ]+?)(?:\s+folder)?$", t)
    if m:
        d = (m.group("d") or m.group("d2") or "").strip().title()
        return _d(rid, t, "find_duplicates", {"folder": d, "directory": d} if d else {})
    m = re.match(r"^what\s+does\s+(?:my|the|this|that)\s+(?P<f>[\w .'-]{2,40}?)\s+say\s+(?:about|on|regarding)\s+(?P<q>.+)$", t)
    if m:
        return _d(rid, t, "document_qa", {"question": raw.strip()})
    m = re.match(rf"^(?:go|jump|navigate|take\s+me)\s+to\s+(?P<f>[\w./\\-]+\.(?:{_EXT}))$", t)
    if m and not re.search(rf"\.(?:{_CODE_EXT})$", m.group("f")):
        return _d(rid, t, "open_file", {"path": _raw(raw, m.group("f"))})
    if re.match(r"^read\s+(?:out\s+)?(?:the\s+|all\s+the\s+)?(?:text|words|content|contents)\s+(?:in|on|of)\s+(?:this|the|current|"
                r"active)\s+(?:window|screen|app|page)$", t):
        return _d(rid, t, "screen_op", {"action": "read", "scope": "active"})
    m = re.match(r"^open\s+(?:what|the (?:file|thing)|whatever)\s+i\s+(?:just\s+)?downloaded$", t)
    if m:
        return _d(rid, t, "file_op", {"action": "open_latest_download"})
    m = re.match(rf"^open\s+(?:the\s+)?(?:newest|latest|last|most recent)\s+(?:thing|file|one|item)\s+(?:generated|created|saved|added|"
                 rf"made|written)?\s*(?:{_HERE})$", t)
    if m:
        return _d(rid, t, "file_op", {"action": "open_newest", "folder": _where(t) or "here"})
    m = re.match(r"^(?:show|reveal|highlight|open)\s+(?P<x>that|this|the|my)\s+(?P<o>download|file|pdf|document|screenshot|project)\s+"
                 r"(?:in\s+(?:its|the|file)\s+(?:folder|explorer|location)|in\s+explorer)$|^show\s+me\s+where\s+(?:this|that|the)\s+"
                 r"(?:file|download|pdf|document)\s+(?:is|lives|went|landed|was saved)$|^(?:show|tell)\s+me\s+(?:on\s+(?:the\s+)?pc\s+)?where\s+"
                 r"(?:the|that|this)\s+file\s+(?:sent|shared|transferred)\s+from\s+(?:my\s+)?phone\s+(?:landed|went|is)$|^reveal\s+"
                 r"(?:it|this|that)(?:\s+in\s+explorer)?$", t)
    if m:
        return _d(rid, t, "file_op", {"action": "reveal", "target": m.groupdict().get("o") or ""})
    m = re.match(r"^(?P<v>move|copy)\s+(?:this|that|it|these|those|them)\s+(?:in)?to\s+(?:the\s+|my\s+)?(?P<d>[\w -]+?)(?:\s+folder)?$", t)
    if m and not re.search(r"\b(?:side|left|right|top|bottom|corner|half|monitor|screen|display|front|back|middle|center|centre)\b",
                           m.group("d")):
        return _d(rid, t, "move_file" if m.group("v") == "move" else "copy_file",
                  {"source": "this", "destination": _raw(raw, m.group("d"))})
    if re.match(r"^(?:show|open)\s+(?:me\s+)?(?:the|that|my)\s+(?:last\s+|latest\s+)?screenshot\s+(?:i|you)\s+(?:just\s+)?(?:took|made|"
                r"captured)$", t):
        return _d(rid, t, "file_op", {"action": "open", "target": "screenshot"})
    if re.search(r"\b(?:find|locate|re-?scan|refresh|look for)\s+(?:the\s+)?(?:new|updated|current)\s+(?:executable|exe|install(?:ation)?\s+"
                 r"(?:path|folder)|app\s+path)\b", t):
        return _d(rid, t, "refresh_applications", {})
    m = re.match(r"^open\s+(?:its|the|this|that)\s+(?:containing\s+|parent\s+)?folder$|^open\s+the\s+folder\s+(?:it'?s|it is|this is|"
                 r"that is)\s+in$", t)
    if m:
        return _d(rid, t, "file_op", {"action": "open_folder"})
    m = re.match(r"^copy\s+(?:the\s+)?(?:this|that|the|its)?\s*(?P<o>file|folder|document|pdf)(?:'s)?\s+(?:path|location)$|"
                 r"^copy\s+the\s+(?:path|location)\s+of\s+(?:this|that|the)\s+(?P<o2>file|folder)$", t)
    if m:
        return _d(rid, t, "file_op", {"action": "copy_path", "folder_path": (m.group("o") or m.group("o2")) == "folder"})
    m = re.match(r"^(?:make|create)\s+(?:a\s+)?(?:copy|duplicate)\s+of\s+(?:the\s+file\s+)?(?P<f>[\w .()-]+\.[a-z0-9]{1,5})$|"
                 r"^duplicate\s+(?:the\s+file\s+)?(?P<f2>[\w .()-]+\.[a-z0-9]{1,5})$", t)
    if m:
        return _d(rid, t, "file_op", {"action": "duplicate", "target": _raw(raw, m.group("f") or m.group("f2")).strip()})
    m = re.match(r"^(?:summari[sz]e|sum\s+up|give\s+me\s+(?:a\s+)?(?:summary|gist)\s+of)\s+my\s+(?:[a-z]+\s+){0,3}(?:policy|statement|"
                 r"receipt|ticket|certificate|slip|bill|report|letter|itinerary|record|marksheet|resume|cv|invoice|agreement|"
                 r"proposal|assignment|notes|document|file|pdf)$", t)
    if m:
        return _d(rid, t, "document_qa", {"question": _raw(raw, t).strip()})
    m = re.match(r"^(?:summari[sz]e|sum\s+up|give\s+me\s+(?:a\s+)?(?:summary|gist)\s+of)\s+(?:the\s+)?(?:file\s+|document\s+)?"
                 r"(?P<f>[\w .()-]+\.(?:pdf|docx?|txt|md|pptx?|xlsx?|csv|rtf))$|^what\s+does\s+(?:the\s+)?(?:file\s+)?"
                 r"(?P<f2>[\w .()-]+\.(?:pdf|docx?|txt|md|pptx?|xlsx?|csv|rtf))\s+say(?:\s+about\s+.+)?$", t)
    if m:
        return _d(rid, t, "document_qa", {"question": _raw(raw, t).strip()})
    m = re.match(r"^(?:make|create)\s+(?:a\s+)?(?:copy|duplicate)\s+of\s+(?:this|that|the)\s+(?:file|document|pdf)$|^duplicate\s+"
                 r"(?:this|that|the)\s+(?:file|document|pdf)$", t)
    if m:
        return _d(rid, t, "file_op", {"action": "duplicate"})
    m = re.match(r"^open\s+(?:this|that|it|the file)\s+(?:in|with)\s+(?P<a>an? (?:app|editor|program)(?: that can edit it)?|[\w +]+)$", t)
    if m:
        a = m.group("a")
        app = "editor" if re.match(r"an? (?:app|editor|program)", a) else a
        return _d(rid, t, "file_op", {"action": "open_with", "app": app})
    m = re.match(r"^restore\s+(?:the\s+)?(?P<n>[\w .'-]+?)(?:\s+file)?\s+(?:if\s+it'?s\s+|that'?s\s+)?(?:in|from)\s+(?:the\s+)?"
                 r"recycle\s*bin$", t)
    if m:
        return _d(rid, t, "file_op", {"action": "restore", "target": m.group("n")})
    if re.match(r"^(?:the\s+)?file\s+(?:moved|was moved|got moved)[;,]?\s+(?:find|locate)\s+it\s+again(?:\s+and\s+(?:continue|carry on|"
                r"keep going))?$|^(?:find|locate)\s+(?:that|this|the)\s+(?:moved\s+)?file\s+again$|^where did (?:that|this|the) file "
                r"(?:go|move to)$", t):
        return _d(rid, t, "file_op", {"action": "relocate"})
    if re.match(r"^(?:make sure|check|verify|confirm)\s+(?:that\s+)?(?:this|that|the)\s+deleted\s+file\s+(?:no longer appears|is gone|"
                r"doesn'?t (?:appear|exist|show up)(?: anymore)?)$|^(?:make sure|check|verify|confirm)\s+(?:that\s+)?(?:this|that|the)"
                r"\s+file\s+(?:really\s+|actually\s+)?(?:was|got|is)\s+(?:really\s+|actually\s+)?deleted$", t):
        return _d(rid, t, "file_op", {"action": "verify_deleted"})
    m = re.match(r"^(?:check|verify|confirm|make sure)\s+(?:that\s+)?(?:the|this|that)\s+file\s+(?:really\s+|actually\s+)?(?:moved|"
                 r"got moved|was moved|is in (?P<d>.+))$|^did\s+(?:the|this|that)\s+file\s+(?:really\s+|actually\s+)?(?:move|get moved)$", t)
    if m:
        return _d(rid, t, "file_op", {"action": "verify", "destination": (m.groupdict().get("d") or "").strip()})
    # size / age / type filters
    m = re.match(rf"^(?:show|find|list|get)\s+(?:me\s+)?(?:all\s+)?(?:the\s+)?(?P<ty>{_FILE_TYPES})\s+(?:between|from)\s+(?P<a>\d+(?:\.\d+)?)"
                 rf"\s*(?P<ua>kb|mb|gb)?\s+(?:and|to|-)\s+(?P<b>\d+(?:\.\d+)?)\s*(?P<ub>kb|mb|gb)(?:\s+{_HERE})?$|"
                 rf"^(?:show|find|list|get)\s+(?:me\s+)?(?:all\s+)?(?:the\s+)?(?P<ty2>{_FILE_TYPES})\s+(?P<cmp>bigger|larger|over|more|smaller|"
                 rf"less|under|below)\s+(?:than\s+)?(?P<c>\d+(?:\.\d+)?)\s*(?P<uc>kb|mb|gb)(?:\s+{_HERE})?$", t)
    if m:
        ty = (m.group("ty") or m.group("ty2") or "").rstrip("s")
        types = [_TYPES[ty]] if ty in _TYPES else []
        if m.group("a"):
            slots = {"min_size": f"{m.group('a')} {m.group('ua') or m.group('ub')}", "max_size": f"{m.group('b')} {m.group('ub')}"}
        else:
            big = m.group("cmp") in ("bigger", "larger", "over", "more")
            slots = {("min_size" if big else "max_size"): f"{m.group('c')} {m.group('uc')}"}
        return _d(rid, t, "file_op", {"action": "search", "types": types, "sort": "largest", "folder": _where(t), **slots})
    m = re.match(rf"^(?:show|find|get|list|which is)\s+(?:me\s+)?(?:the\s+)?(?P<s>oldest|largest|biggest|smallest|heaviest)"
                 rf"\s+(?P<ty>{_FILE_TYPES})(?:\s+{_HERE})?$", t)
    if m:
        ty = m.group("ty").rstrip("s")
        sort = {"biggest": "largest", "heaviest": "largest", "latest": "newest"}.get(m.group("s"), m.group("s"))
        return _d(rid, t, "file_op", {"action": "search", "types": [_TYPES[ty]] if ty in _TYPES else [], "sort": sort,
                                      "limit": 1, "folder": _where(t)})
    if re.match(r"^what(?:'s| is)\s+in\s+(?:this|the current|the)\s+folder$|^(?:list|show)\s+(?:me\s+)?(?:what'?s|everything)\s+in\s+"
                r"(?:this|the current)\s+folder$", t):
        return _d(rid, t, "list_directory", {"pronoun": "this"})
    m = re.match(r"^(?:do i have|is there)\s+(?:another|a second|any other)\s+file\s+with\s+(?:this|that|the same)\s+name$", t)
    if m:
        return _d(rid, t, "find_duplicates", {"pronoun": "this", "by": "name"})
    m = re.match(r"^(?:find|show|search for)\s+(?:the\s+|my\s+)?(?P<o>[\w ]+?)\s+with\s+['\"]?(?P<q>[\w .-]+?)['\"]?\s+in\s+(?:the|its)"
                 r"\s+(?:file\s?)?name$", t)
    if m:
        return _d(rid, t, "find_file", {"query": _raw(raw, m.group("q")), "type_hint": m.group("o").strip()})
    m = re.match(r"^(?:which|what)\s+(?:files|documents|notes|pdfs)\s+(?:mention|talk about|discuss|contain|cover|reference)\s+(?P<q>.+)$", t)
    if m:
        return _d(rid, t, "knowledge_search", {"question": _raw(raw, m.group("q"))})
    m = re.match(r"^(?:find|show me|go to|open)\s+(?:the\s+)?(?:section|part|chapter|page)s?\s+(?:on|about|covering|that covers)\s+"
                 r"(?P<q>.+?)(?:\s+in\s+(?:this|the)\s+(?:doc|document|pdf|file))?$", t)
    if m:
        return _d(rid, t, "document_qa", {"question": _raw(raw, m.group("q"))})
    return None


# ------------------------------------------------------------------------------------------------- browser
def _browser(t, raw, rid, mode):
    page = r"(?:this|the|current|that)\s+(?:page|site|website|tab|article)"
    m = re.match(r"^(?:search|look up|find)\s+(?:on\s+)?(?:this|the)\s+(?:site|website|page)\s+for\s+(?P<q>.+)$|^search\s+for\s+(?P<q2>.+?)"
                 r"\s+on\s+(?:this|the)\s+(?:site|website)$", t)
    if m:
        return _d(rid, t, "browser_op", {"action": "site_search", "target": _raw(raw, m.group("q") or m.group("q2"))})
    if re.match(r"^(?:duplicate|clone)\s+(?:this|the|current)\s+tab$|^open\s+(?:this|the current)\s+(?:page|tab)\s+(?:again\s+)?in\s+"
                r"(?:a\s+)?(?:new|second|another)\s+tab$", t):
        return _d(rid, t, "browser_op", {"action": "duplicate"})
    if re.match(rf"^(?:stop|cancel|halt)\s+(?:loading|the loading of)\s+(?:{page})$|^stop\s+(?:{page})\s+(?:from\s+)?loading$", t):
        return _d(rid, t, "browser_op", {"action": "stop"})
    if re.match(rf"^what\s+(?:page|site|website|url)\s+am\s+i\s+on$|^what(?:'s| is)\s+(?:the\s+)?(?:url|address|link)\s+(?:of\s+)?"
                rf"(?:{page})?$|^(?:where am i|which site is this)\s+(?:on the web|in the browser)?$", t):
        return _d(rid, t, "browser_op", {"action": "url"})
    if re.match(rf"^what(?:'s| is)\s+(?:the\s+)?(?:title|name|heading)\s+of\s+(?:{page})$|^what\s+is\s+(?:{page})\s+called$", t):
        return _d(rid, t, "browser_op", {"action": "title"})
    if re.match(rf"^copy\s+(?:the\s+)?(?:this\s+|current\s+)?(?:page|tab|site)\s+(?:link|url|address)$|^copy\s+(?:the\s+)?(?:link|url|"
                rf"address)\s+(?:of|to|for)\s+(?:{page})$|^copy\s+(?:this|the current)\s+(?:url|link)$", t):
        return _d(rid, t, "browser_op", {"action": "copy_url"})
    m = re.match(r"^(?:find|show me|highlight)\s+where\s+it\s+(?:says|mentions|talks about)\s+['\"]?(?P<q>.+?)['\"]?$", t)
    if m:
        return _d(rid, t, "browser_op", {"action": "find", "target": _raw(raw, m.group("q"))})
    m = re.match(r"^(?:take me|jump|go|scroll|skip)\s+(?:down\s+)?to\s+(?:the\s+)?(?P<h>[\w -]+?)\s+(?:section|heading|part|chapter)$|"
                 r"^take me to\s+(?:the\s+)?(?P<h2>[a-z][\w -]{2,40})$", t)
    if m:
        h = m.group("h") or m.group("h2")
        if m.group("h2") and (re.search(rf"\b(?:{_APPS})\b|\.\w{{2,4}}\b|\b(?:home|homepage|website|site|page|tab|window|app|folder)\b", h)
                              or len(h.split()) > 3):
            return None
        return _d(rid, t, "browser_op", {"action": "heading", "target": _raw(raw, h)})
    m = re.match(r"^(?:read|tell me)\s+(?:me\s+)?(?:the\s+)?(?P<h>[\w -]+?)\s+section$", t)
    if m and m.group("h") not in ("this", "that", "next", "previous"):
        return _d(rid, t, "browser_op", {"action": "heading", "target": _raw(raw, m.group("h")), "read": True})
    if re.match(rf"^(?:tell me\s+)?(?:if|whether)\s+(?:{page})\s+(?:needs|wants|requires)\s+(?:me\s+)?to\s+(?:sign|log)\s+in$|"
                rf"^(?:do i need to|should i|must i)\s+(?:sign|log)\s+in\s+(?:here|to this (?:site|page))$|^am i\s+(?:signed|logged)\s+in"
                rf"(?:\s+(?:here|on this (?:site|page)))?$", t):
        return _d(rid, t, "browser_op", {"action": "detect_login"})
    m = re.match(r"^(?:find|get|look up|show me)\s+(?:the\s+)?official\s+(?P<k>fix|docs|documentation|answer|solution|page|guide)\s+"
                 r"(?:for|on|about)\s+(?P<q>.+)$", t)
    if m:
        q = m.group("q")
        if re.match(r"^(?:this|that|the)\s+(?:error|problem|issue|bug)$", q):
            return _planner(rid, t)                          # read the error first, then look it up
        return _d(rid, t, "browser_op", {"action": "official", "target": _raw(raw, q)})
    if re.match(r"^(?:open|click)\s+(?:this|that|the)\s+(?:result|link|one)(?:\s+in\s+(?:a\s+new\s+tab|new\s+tab|"
                r"(?:google\s+)?chrome|(?:microsoft\s+)?edge|firefox|brave|(?:another|the\s+other)\s+browser))?$", t):
        return _clarify(rid, t, "Which result - say its number, like 'open the second result in a new tab'.",
                        intent="browser_op")
    m = re.match(r"^(?:open|click|follow)\s+(?:the\s+)?(?P<n>[\w -]+?)\s+link(?P<nt>\s+in\s+(?:a\s+)?new\s+tab)?$", t)
    if m and not re.match(rf"^(?:{_ORD_RE}|this|that|same)$", m.group("n")):
        return _d(rid, t, "browser_op", {"action": "open_link", "target": _raw(raw, m.group("n")), "new_tab": bool(m.group("nt"))})
    m = re.match(r"^(?:upload|attach)\s+(?:this|that|it|the\s+(?:file|screenshot|pdf|image|document))\s+(?:to|on|into)\s+(?:this|the)\s+"
                 r"(?:page|form|site|website|upload field)$", t)
    if m:
        return _d(rid, t, "browser_op", {"action": "upload"})
    m = re.match(r"^(?:open|start)?\s*(?:a\s+|another\s+|one more\s+)?(?:new\s+)?(?:browser\s+|chrome\s+|edge\s+)?tab(?:\s+on\s+(?:my\s+)?pc|"
                 r"\s+(?:in|on)\s+(?:google\s+)?(?:chrome|edge|firefox|brave|(?:the\s+)?browser))?$|"
                 r"^open\s+(?:a\s+)?new\s+(?:chrome|edge|browser)\s+tab(?:\s+on\s+(?:my\s+)?pc)?$", t)
    if m:
        return _d(rid, t, "browser_quick_action", {"action": "new_tab"})
    m = re.match(r"^(?:search|look)\s+(?:the web\s+|online\s+|google\s+)?(?:for|up)\s+(?P<q>.+?)\s+(?:docs|documentation|tutorials?|"
                 r"guides?|examples?|articles?|papers?)$", t)
    if m and not re.search(r"\b(?:file|folder|pdf|my)\b", m.group("q")):
        return _d(rid, t, "search_web", {"query": _raw(raw, t.split(" for ", 1)[-1] if " for " in t else m.group("q"))})
    return None


# ------------------------------------------------------------------------------------------------- text
def _text(t, raw, rid, mode):
    m = re.match(rf"^move\s+(?:the\s+)?(?:cursor|caret)\s+(?P<d>left|right|up|down|back|forward)\s+(?:by\s+)?(?:(?P<n>{_NUM_RE})\s+)?"
                 rf"(?P<u>words?|characters?|chars?|letters?|lines?)$|^move\s+(?:the\s+)?(?:cursor|caret)\s+(?:(?P<n2>{_NUM_RE})\s+)?"
                 rf"(?P<u2>words?|characters?|chars?|letters?|lines?)\s+(?:to the\s+)?(?P<d2>left|right|up|down|back|forward)$", t)
    if m:
        unit = re.sub(r"s$", "", m.group("u") or m.group("u2")).replace("character", "char").replace("letter", "char")
        return _d(rid, t, "text_op", {"action": "caret", "unit": unit, "n": _n(m.group("n") or m.group("n2") or "", 1),
                                      "direction": m.group("d") or m.group("d2")})
    m = re.match(r"^(?:go|jump|move|take me)(?:\s+the\s+cursor)?\s+to\s+the\s+(?P<w>start|beginning|top|end|bottom)(?:\s+of\s+"
                 r"(?:the\s+|this\s+)?(?P<o>document|doc|file|text|line|page|field))?$", t)
    if m and (m.group("o") or (mode not in ("media", "browser") and m.group("w") not in ("top", "bottom"))):
        o = m.group("o") or "document"
        start = m.group("w") in ("start", "beginning", "top")
        unit = "line" if o == "line" else "document"
        return _d(rid, t, "text_op", {"action": "caret", "unit": unit, "direction": ("start" if start else "end")
                                      if unit == "document" else ("left" if start else "right")})
    m = re.match(r"^(?:new|next)\s+(?P<k>line|paragraph)$|^(?:start\s+a\s+|add\s+a\s+)new\s+(?P<k2>line|paragraph)$", t)
    if m:
        k = m.group("k") or m.group("k2")
        return _d(rid, t, "text_op", {"action": "press", "key": "new_line" if k == "line" else "new_paragraph", "n": 1})
    if re.match(r"^paste\s+(?:this|it|that)?\s*(?:as\s+plain\s+text|without\s+(?:the\s+)?formatting|unformatted|as\s+text\s+only)$", t):
        return _d(rid, t, "text_op", {"action": "paste_plain"})
    if re.match(r"^paste\s+(?:this|it|that)?\s*(?:with|keeping|preserving)\s+(?:the\s+)?formatting(?:\s+where\s+(?:supported|possible))?$", t):
        return _d(rid, t, "pc_quick_action", {"action": "paste"})
    if re.match(r"^how many\s+(?:words|characters|letters|lines)\s+(?:are|is)\s+(?:there\s+)?in\s+(?:this|the)\s+(?:field|box|text|"
                r"document|doc|paragraph|message|draft)$|^(?:word|character)\s+count$|^count\s+(?:the\s+)?words(?:\s+here)?$", t):
        return _d(rid, t, "text_op", {"action": "count"})
    m = re.match(r"^find\s+the\s+(?:word|phrase|text)\s+['\"]?(?P<q>.+?)['\"]?(?:\s+in\s+(?:this|the)\s+(?:document|doc|text|field|file))?$|"
                 r"^find\s+['\"]?(?P<q2>.+?)['\"]?\s+in\s+(?:this|the)\s+(?:document|doc|text|field|draft)$", t)
    if m:
        return _d(rid, t, "text_op", {"action": "find", "find": _raw(raw, m.group("q") or m.group("q2"))})
    m = re.match(r"^(?:insert|paste|use|add)\s+(?:my\s+|the\s+)?(?P<n>[\w -]+?)\s+template(?:\s+here)?$", t)
    if m:
        return _d(rid, t, "text_op", {"action": "template", "name": m.group("n").strip()})
    m = re.match(r"^(?:add|put|append|move|insert|write)\s+(?P<x>.+?)\s+(?:to|at)\s+the\s+(?P<w>end|bottom|top|start|beginning)"
                 r"(?:\s+of\s+(?:the\s+|this\s+)?(?:document|text|field|file|note))?$", t)
    if m:
        x = m.group("x")
        top = m.group("w") in ("top", "start", "beginning")
        if re.match(r"^(?:this|that|it|the)\s+(?:sentence|line|paragraph|text|word)s?$|^(?:this|that|it)$", x):
            return _clarify(rid, t, f"What exactly should I put at the {'top' if top else 'end'}? Say the words, or select "
                                    "the text and say 'cut that' first.", intent="text_op")
        x = re.sub(r"^['\"]|['\"]$", "", _raw(raw, x))
        return _d(rid, t, "text_op", {"action": "prepend" if top else "append", "text": x})
    m = re.match(r"^save\s+(?:this|it|the\s+(?:file|document|doc|note))\s+as\s+['\"]?(?P<n>[\w .()-]+\.\w{1,5})['\"]?$", t)
    if m:
        return _d(rid, t, "text_op", {"action": "save_as", "name": _raw(raw, m.group("n"))})
    if re.match(r"^save\s+(?:this|the)\s+(?:document|doc|note|draft|text)$", t):
        return _d(rid, t, "text_op", {"action": "save"})
    return None


# ------------------------------------------------------------------------------------------------- controls
_FIELD = r"(?:field|box|text\s?box|textbox|input|search box|search bar|text area|textarea|entry|form field)"


def _controls(t, raw, rid, mode):
    surf = "phone" if mode == "phone" else "auto"
    if re.match(r"^(?:is|are)\s+(?:there\s+)?(?:a|any)\s+(?:popup|pop-up|dialog|modal|prompt|alert)s?\s+(?:blocking|open|in the way|"
                r"stopping)(?:\s+me)?$|^what(?:'s| is)\s+(?:this|that|the)\s+(?:popup|pop-up|dialog|modal)$|^is something\s+"
                r"blocking\s+(?:me|the screen)$", t):
        return _d(rid, t, "ui_op", {"action": "modal"})
    m = re.match(r"^(?:choose|pick|select)\s+(?P<o>[\w .+#-]+?)\s+(?:from|in|out of)\s+(?:this|the|that)\s+(?P<w>list|dropdown|drop-down|"
                 r"menu|options|combo ?box|picker)$", t)
    if m:
        return _d(rid, t, "ui_op", {"action": "select", "option": _raw(raw, m.group("o")), "target": m.group("w"), "surface": surf})
    m = re.match(r"^(?:choose|pick)\s+(?P<o>[\w.+#-]+(?:\s+[\w.+#-]+)?)$", t)
    if m and not re.search(rf"\b(?:{_APPS}|file|folder|one|it|this|that|result|option|{_ORD_RE})\b", m.group("o")):
        return _d(rid, t, "ui_op", {"action": "select", "option": _raw(raw, m.group("o")), "surface": surf})
    m = re.match(r"^(?:turn|switch|toggle|flip)\s+(?P<x>(?:this|that|the)\s+(?:[\w ]+\s+)?(?:option|setting|toggle|switch|checkbox|"
                 r"check box|box))\s+(?P<s>on|off)$|^(?:turn|switch)\s+(?P<s2>on|off)\s+(?P<x2>(?:this|that|the)\s+(?:[\w ]+\s+)?"
                 r"(?:option|setting|toggle|switch|checkbox))$", t)
    if m:
        on = (m.group("s") or m.group("s2")) == "on"
        x = re.sub(r"^(?:this|that|the)\s+", "", m.group("x") or m.group("x2"))
        return _d(rid, t, "ui_op", {"action": "check" if on else "uncheck", "target": x, "surface": surf})
    m = re.match(r"^(?:set|move|drag|put)\s+(?P<x>(?:this|the|that)\s+(?:[\w ]+\s+)?(?:slider|seek bar|range|knob))\s+(?:to\s+)?(?P<v>\d{1,3})"
                 r"\s*(?:%|percent)?$", t)
    if m:
        return _d(rid, t, "ui_op", {"action": "slider", "target": re.sub(r"^(?:this|that|the)\s+", "", m.group("x")),
                                    "value": float(m.group("v")), "surface": surf})
    m = re.match(r"^scroll\s+(?P<x>(?:this|the|that)\s+(?:panel|list|pane|sidebar|section|table|dialog|menu|chat|feed))\s+"
                 r"(?P<d>up|down)(?:\s+(?P<n>\w+)\s+times)?$|^scroll\s+(?P<d2>up|down)\s+(?:in|on)\s+(?P<x2>(?:this|the|that)\s+"
                 r"(?:panel|list|pane|sidebar|section|table|dialog|menu))$", t)
    if m:
        return _d(rid, t, "ui_op", {"action": "scroll", "direction": m.group("d") or m.group("d2"),
                                    "target": re.sub(r"^(?:this|that|the)\s+", "", m.group("x") or m.group("x2")),
                                    "n": _n(m.group("n") or "", 1), "surface": surf})
    m = re.match(r"^(?P<v>expand|open up|unfold|collapse|close up|fold)\s+(?P<x>(?:this|that|the)\s+[\w ]*?(?:folder tree|tree|section|group|"
                 r"node|folder|panel|accordion|menu|details|row|list))$", t)
    if m:
        open_ = m.group("v") in ("expand", "open up", "unfold")
        return _d(rid, t, "ui_op", {"action": "expand" if open_ else "collapse",
                                    "target": re.sub(r"^(?:this|that|the)\s+", "", m.group("x")), "surface": surf})
    m = re.match(r"^why\s+(?:can'?t|cannot|won'?t\s+it\s+let)\s+i\s+(?:press|click|tap|use|hit|submit|select)?\s*(?:the\s+)?(?P<x>[\w ]+?)"
                 r"(?:\s+button)?$|^why\s+is\s+(?:the\s+)?(?P<x2>[\w ]+?)(?:\s+button)?\s+(?:disabled|greyed out|grayed out|not working|"
                 r"not clickable)$|^find\s+the\s+disabled\s+(?P<x3>[\w ]+?)\s+button\s+and\s+tell\s+me\s+what\s+(?:blocks|is blocking)"
                 r"\s+it$|^why\s+(?:can'?t|cannot)\s+i\s+(?P<x4>continue|submit|proceed|go on|save|send)$", t)
    if m:
        x = m.group("x") or m.group("x2") or m.group("x3") or m.group("x4") or ""
        return _d(rid, t, "ui_op", {"action": "explain", "target": _raw(raw, x), "surface": surf})
    if re.match(r"^(?:move|go|jump|tab)\s+(?:the\s+)?(?:focus\s+)?to\s+the\s+next\s+(?:input|field|box|control|textbox)$|^next\s+field$", t):
        return _d(rid, t, "ui_op", {"action": "next_focus", "surface": surf})
    m = re.match(rf"^(?:put|place|move)\s+(?:the\s+)?(?:cursor|caret|focus)\s+(?:in|into|on)\s+(?:the\s+)?(?P<x>[\w ]*?{_FIELD})$|"
                 rf"^(?:focus|click into|select)\s+(?:on\s+)?(?:the\s+)?(?P<x2>[\w ]*?{_FIELD})$", t)
    if m:
        x = (m.group("x") or m.group("x2")).strip()
        return _d(rid, t, "phone_op" if surf == "phone" else "ui_op",
                  {"action": "focus", "target": x, **({} if surf == "phone" else {"surface": surf})})
    m = re.match(rf"^(?:clear|empty|wipe|blank|erase)\s+(?:out\s+)?(?:this|that|the|current)\s+(?P<x>[\w ]*?{_FIELD})(?:\s+out)?$", t)
    if m:
        return _d(rid, t, "phone_op" if surf == "phone" else "ui_op",
                  {"action": "clear", "target": m.group("x"), **({} if surf == "phone" else {"surface": surf})})
    m = re.match(rf"^copy\s+(?:this|that|the|the current)\s+(?P<x>[\w ]*?(?:{_FIELD}|value|label|cell))(?:'s\s+(?:value|text))?$", t)
    if m:
        return _d(rid, t, "ui_op", {"action": "copy", "target": m.group("x"), "surface": surf})
    m = re.match(rf"^(?:remove|delete|detach|drop|take off)\s+(?:the\s+)?(?P<w>{_ORD_RE}|screenshot|image|picture|pdf|file|photo|last|"
                 rf"attached)?\s*(?:attached\s+)?(?:attachment|attached file|attached image|attached screenshot|chip)$", t)
    if m:
        w = (m.group("w") or "").strip()
        which = str(_ORD.get(w, 1)) if w in _ORD else w
        intent = "ide_op" if mode == "ide" else "ui_op"
        slots = {"action": "remove_attachment", "text": which or "first"} if intent == "ide_op" else \
            {"action": "remove_attachment", "target": which, "surface": surf}
        return _d(rid, t, intent, slots)
    m = re.match(r"^(?:find|locate|where(?:'s| is))\s+(?:the\s+)?(?P<x>[\w ]+?\s+(?:button|toggle|checkbox|switch|field|link|icon|tab))$", t)
    if m:
        if surf == "phone":
            return _d(rid, t, "phone_op", {"action": "find", "target": m.group("x")})
        return _d(rid, t, "ui_op", {"action": "find", "target": m.group("x"), "surface": surf})
    return None


# ------------------------------------------------------------------------------------------------- windows
def _windows(t, raw, rid, mode):
    m = re.match(rf"^(?:bring|pull|put)\s+(?P<x>(?:{_APPS})|[\w]+)\s+(?:to\s+the\s+front|to\s+the\s+top|up\s+front|back up)(?:\s+again)?$|"
                 rf"^(?:bring|pull)\s+(?:up\s+)?(?P<x2>{_APPS})(?:\s+window)?\s+to\s+the\s+front$", t)
    if m:
        x = m.group("x") or m.group("x2")
        if x in ("this", "it", "that", "phone"):
            return None
        return _d(rid, t, "window_op", {"action": "focus", "target": x})
    if re.match(rf"^(?:go|switch|get)\s+back\s+to\s+(?:the\s+|my\s+)?(?:editor|ide|document|{_APPS})(?:\s+window)?\s+and\s+(?:then\s+)?"
                rf"(?:continue|carry on|keep going|resume|pick up)\b", t):
        return _planner(rid, t)                              # focus, then continue whatever was paused there
    if re.match(r"^(?:go|switch|take me|get me)\s+back\s+to\s+(?:the\s+)?(?:app|window|program)\s+i\s+(?:was|had been)\s+(?:just\s+)?"
                r"(?:using|in|on|working in|working on)$", t):
        return _d(rid, t, "window_op", {"action": "focus", "target": "previous"})
    m = re.match(r"^close\s+(?:only\s+|just\s+)?(?:the\s+)?(?P<x>[\w ]+?)\s+window(?:\s+only)?$", t)
    if m and (re.search(r"\b(?:only|just)\b", t) or re.fullmatch(rf"(?:{_APPS})", m.group("x"))) \
            and m.group("x") not in ("this", "that", "the", "top", "current", "active", "other"):
        return _d(rid, t, "window_op", {"action": "close", "target": m.group("x")})
    if re.match(r"^(?:bring|put|set|get)\s+(?:this|it|that|the window)\s+back\s+to\s+(?:its\s+)?(?:normal|regular|original|usual)\s+size$|"
                r"^(?:make|set)\s+(?:this|the)\s+window\s+normal\s+size(?:\s+again)?$", t):
        return _d(rid, t, "window_op", {"action": "restore", "target": ""})
    m = re.match(r"^(?:make|set)\s+(?P<x>this|the|that|my)?\s*(?P<w>[\w]+\s+)?window\s+(?P<d>smaller|bigger|larger|wider|narrower|a bit smaller|"
                 r"a bit bigger|a little smaller|a little bigger)$|^(?P<v>shrink|enlarge|grow)\s+(?:this|the|that|my)\s+(?P<w2>[\w]+\s+)?window"
                 r"(?:\s+(?:a\s+(?:bit|little|touch)|slightly|some(?:what)?))?$", t)
    if m:
        d = m.group("d") or ("smaller" if m.group("v") == "shrink" else "bigger")
        w = (m.group("w") or m.group("w2") or "").strip()
        return _d(rid, t, "window_op", {"action": "resize", "target": w if w and w not in ("current", "active") else "",
                                        "direction": "smaller" if re.search(r"small|narrow|shrink", d) else "bigger"})
    m = re.match(r"^move\s+(?P<x>this|it|that|the window|this window)\s+to\s+the\s+other\s+side(?:\s+of\s+the\s+screen)?$", t)
    if m:
        return _d(rid, t, "window_op", {"action": "move", "target": "", "direction": "other"})
    m = re.match(rf"^(?:move|send|put|throw|push)\s+(?P<x>{_APPS})\s+(?:over\s+)?(?:to|onto)\s+(?:my\s+|the\s+)?"
                 rf"(?:second|other|next|left|right|external|2nd)\s+(?:monitor|screen|display)$", t)
    if m:
        x = m.group("x")
        return _d(rid, t, "window_op", {"action": "arrange", "target": "" if x in ("this", "it", "this window", "the window") else x,
                                        "layout": "next_monitor"})
    if re.match(r"^(?:what|which)\s+(?:apps|windows|programs|applications)\s+(?:are|do i have)\s+(?:open|running)(?:\s+(?:right now|now))?$|"
                r"^(?:list|show)\s+(?:me\s+)?(?:all\s+)?(?:the\s+|my\s+)?open\s+(?:apps|windows|programs)$", t):
        return _d(rid, t, "window_op", {"action": "list"})
    m = re.match(r"^where\s+(?:did|has)\s+(?:my\s+|the\s+)?(?P<x>[\w ]+?)(?:\s+window)?\s+(?:go|gone|disappear(?:ed)?|went)$|^i\s+(?:lost|can'?t "
                 r"find)\s+(?:my\s+|the\s+)?(?P<x2>[\w ]+?)\s+window$|^find\s+(?:my\s+|the\s+)?(?P<x3>[\w ]+?)\s+window$", t)
    if m:
        x = m.group("x") or m.group("x2") or m.group("x3")
        if x in ("file", "files", "download", "it", "that"):
            return None
        return _d(rid, t, "window_op", {"action": "find", "target": x})
    if re.match(r"^(?:show|give|tell|open)\s+(?:me\s+)?(?:the\s+)?(?:info|information|details|properties|settings)(?:\s+page)?\s+"
                r"(?:for|about|on|of)\s+(?:this|the|that|current)\s+(?:app|window|program)$", t):
        return _d(rid, t, "window_op", {"action": "info", "target": ""})
    if re.match(r"^(?:what|which)\s+(?:app|application|program|window)\s+(?:am\s+i\s+(?:in|using|on)|is\s+(?:in\s+front|active|focused|"
                r"open\s+now|on\s+top|current))$", t):
        return _d(rid, t, "window_op", {"action": "active"})
    m = re.match(r"^(?:remember|save|store|keep)\s+(?:this|the|my|the current)\s+(?:window\s+)?(?:arrangement|layout|setup|window layout)"
                 r"(?:\s+(?:as|called|named)\s+(?P<n>[\w ]+))?$", t)
    if m:
        return _d(rid, t, "window_op", {"action": "save_layout", "name": (m.group("n") or "default").strip()})
    m = re.match(r"^(?:restore|bring back|load|set up|reopen)\s+(?:my|the)\s+(?P<n>[\w ]+?)\s+(?:window\s+)?(?:layout|arrangement|setup|"
                 r"windows)$", t)
    if m:
        return _d(rid, t, "window_op", {"action": "restore_layout", "name": m.group("n").strip()})
    return None



# ------------------------------------------------------------------------------------------------- dry run
def _dry_run(t, raw, rid, mode):
    """'dry run: delete x' / 'what would you do if I said close y' / 'preview the command z': explain, run nothing."""
    m = re.match(r"^(?:dry\s*-?\s*run|simulate|test\s+run)\s*[:,-]?\s+(?P<c>.+)$|^what\s+(?:would\s+(?:you|jarvis)\s+do|would\s+happen|happens)\s+if\s+i\s+"
                 r"(?:said|say|told\s+you|asked\s+you\s+to)\s*[:,]?\s+(?P<c2>.+)$|^(?:preview|explain)\s+(?:the\s+)?command\s*[:,]?\s+"
                 r"(?P<c3>.+)$|^how\s+would\s+you\s+handle\s*[:,]?\s+(?P<c4>.+)$", t)
    if not m:
        return None
    cmd = next(g for g in (m.group("c"), m.group("c2"), m.group("c3"), m.group("c4")) if g)
    return _d(rid, t, "explain_route", {"command": _raw(raw, cmd).strip(" '\"")})


# ------------------------------------------------------------------------------------------------- refusals
_DANGER = re.compile(
    r"\bformat\s+(?:my\s+|the\s+|this\s+)?(?:[a-z]\s+)?(?:hard\s+)?(?:disk|drive|ssd|hdd|partition|computer|pc|laptop)\b"
    r"|\b(?:disable|turn\s+off|switch\s+off|kill|stop|remove|uninstall)\s+(?:the\s+|my\s+)?(?:windows\s+)?(?:defender|firewall|"
    r"antivirus|anti-virus|uac|user\s+account\s+control|smart\s*screen|windows\s+security|security\s+updates)\b"
    r"|\b(?:delete|wipe|erase|remove)\s+(?:the\s+)?(?:system32|windows\s+folder|registry|boot\s+(?:loader|partition)|"
    r"(?:all\s+)?system\s+files)\b"
    r"|\b(?:bypass|break|crack|hack|skip|get\s+past|get\s+around|unlock\s+without)\s+(?:the\s+|my\s+)?(?:\w+\s+)?(?:lock\s*screen|"
    r"screen\s+lock|pin|passcode|password|pattern|captcha|otp|2fa|two[\s-]factor|login)\b"
    r"|\b(?:unlock|open|get\s+into|access)\s+(?:my\s+|the\s+|this\s+|someone'?s?\s+)?(?:\w+\s+)?(?:phone|mobile|laptop|pc|computer|"
    r"account)\s+without\s+(?:the\s+|my\s+|a\s+|its\s+)?(?:pin|passcode|password|pattern|fingerprint|face\s*id|code)\b"
    r"|\b(?:wipe|erase)\s+(?:my\s+|the\s+)?(?:whole|entire|complete)\s+(?:hard\s+)?(?:drive|disk|ssd|pc|computer)\b"
    r"|\b(?:wipe|erase|nuke)\s+(?:my\s+|the\s+|this\s+)?(?:[a-z]\s*:?\s+)?(?:hard\s+)?(?:drive|disk|ssd|hdd|partition)\b"
    r"|\bsolve\s+(?:this|the|that)\s+captcha\b"
    r"|\brun\s+(?:this|that|a|some|the)\s+(?:powershell|cmd|batch|bash|shell)\s+script\s+from\s+(?:the\s+)?(?:internet|web|net|"
    r"site|website|email)\b")
_PRIVATE_DATA = re.compile(r"\b(?:send|share|forward|post|message|text|email|tell)\b.*\b(?:my\s+)?(?:aadhaar|aadhar|pan\s+card|"
                           r"passport\s+(?:number|details)|bank\s+(?:details|account|password)|card\s+(?:number|details)|cvv|"
                           r"passwords?|otp|pin\s+number)\b")


def _danger(t, raw, rid, mode):
    if _DANGER.search(t):
        return _d(rid, t, None, {"refused": "unsafe_system_action"}, lane=RouteLane.REJECT,
                  clarification="I won't do that - it would switch off your PC's protection, destroy the system or get "
                                "around a security check. If you really need it, do it yourself from Windows Settings.")
    if _PRIVATE_DATA.search(t) and not re.search(r"\b(?:don'?t|never|do\s+not)\b", t):
        return _clarify(rid, t, "I don't send ID numbers, passwords, OTPs or card details in messages. If you're sure, "
                                "share it yourself.")
    return None


# ------------------------------------------------------------------------------------------------- timed commands / triggers
_NUMW = r"\d+(?:\.\d+)?|a|an|one|two|three|four|five|ten|fifteen|twenty|thirty|forty\s+five|half\s+an|a\s+couple\s+of|few"
_IN = rf"in\s+(?:{_NUMW})\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?)"
_AT_LEAD = r"(?:tomorrow\s+)?at\s+(?:\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)?|noon|midnight)(?:\s+tomorrow)?"
_AT_TAIL = r"(?:tomorrow\s+)?at\s+(?:\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm|a\.m\.|p\.m\.|o'?clock)|noon|midnight)(?:\s+tomorrow)?"
_NOT_DEFERRABLE = re.compile(r"^(?:remind|set\s+(?:a|an)\s+(?:timer|alarm|reminder)|wake\s+me|schedule|book|meet|tell|message|"
                             r"text|send|e-?mail|whats\s*app|reply|call|ping|let\s+\w+\s+know)\b|\b(?:meeting|alarm|reminder|"
                             r"timer|appointment|event|calendar|agenda|every|daily|weekdays?|weekends?|each)\b")


# Only a direct action on this PC or the phone is deferred ("in 10 minutes open krita"); a note, a call to set up or a table
# to reserve that merely mentions a time is not a command to run later.
_DEFERRABLE = re.compile(r"^(?:open|launch|start|run|close|quit|exit|kill|lock|mute|unmute|pause|resume|play|stop|skip|turn\s+(?:on|off|up|"
                         r"down)|switch|set\s+(?:the\s+|my\s+)?(?:volume|brightness|sound|theme)|lower|raise|increase|decrease|dim|"
                         r"brighten|minimi[sz]e|maximi[sz]e|restart|relaunch|reboot|shut\s*down|sleep|hibernate|log\s*off|"
                         r"take\s+a\s+screenshot|screenshot|empty|disconnect|connect|enable|disable|show|hide|focus|go\s+to|"
                         r"bring|move|copy|clean|organi[sz]e|sync|back\s*up)\b")


def _schedule(t, raw, rid, mode):
    m = re.match(rf"^(?P<w>{_IN}|{_AT_LEAD})\s*,?\s*(?:please\s+)?(?P<c>[a-z].+)$", t) or \
        re.match(rf"^(?P<c>[a-z].+?)\s*,?\s+(?P<w>{_IN}|{_AT_TAIL})$", t)
    if m:
        cmd = m.group("c").strip(" ,")
        if _NOT_DEFERRABLE.search(cmd) or not _DEFERRABLE.match(cmd) \
                or len(cmd.split()) < 2 and cmd not in ("mute", "unmute", "lock"):
            return None                       # reminders, timers, meetings and messages keep their own handling
        if re.match(r"^(?:what|when|where|how|who|which|why|is|are|am|do|does|did|can|could|will|would|should|shall|was|"
                    r"were|have|has)\b", cmd):
            return None
        return _d(rid, t, "workflow_op", {"action": "run_at", "command": _raw(raw, cmd), "when": m.group("w")})
    m = re.match(r"^(?:whenever|every\s+time|each\s+time|any\s*time|anytime)\s+(?P<c>[^,]+?)\s*(?:,|\bthen\b)\s*(?:then\s+)?"
                 r"(?P<cmd>.+)$", t)
    if m:
        trig = _trigger(m.group("c"))
        if trig is None:
            return None
        cmd = re.sub(r"\s+(?:too|as\s+well|also)$", "", m.group("cmd")).strip(" ,.")
        if not cmd:
            return None
        return _d(rid, t, "workflow_op", {"action": "trigger", **trig, "command": _raw(raw, cmd)})
    if re.match(r"^(?:list|show|what\s+are)\s+(?:me\s+)?(?:all\s+)?(?:my\s+|the\s+)?(?:automations?|triggers?|scheduled\s+"
                r"(?:commands?|tasks?|actions?)|schedules)(?:\s+(?:i\s+have|running|set\s+up))?$", t):
        return _d(rid, t, "workflow_op", {"action": "list_triggers"})
    m = re.match(r"^(?:delete|remove|cancel|stop|turn\s+off|disable)\s+(?:the\s+|my\s+)?(?P<x>.*?)\s*(?:automation|trigger|"
                 r"scheduled\s+(?:command|task|action)|schedule)s?$", t)
    if m and not re.search(r"\bworkflow\b", t):
        return _d(rid, t, "workflow_op", {"action": "cancel_trigger", "ref": m.group("x").strip()})
    return None


def _trigger(c: str) -> Optional[dict]:
    c = c.strip()
    m = re.match(r"^(?:i\s+)?(?:open|start|launch|run)\s+(?P<x>[\w .+-]+)$|^(?P<x2>[\w .+-]+?)\s+(?:opens|starts|launches|is\s+opened)$", c)
    if m:
        return {"condition": "app_opened", "subject": (m.group("x") or m.group("x2")).strip()}
    m = re.match(r"^(?:i\s+)?(?:close|quit|exit)\s+(?P<x>[\w .+-]+)$|^(?P<x2>[\w .+-]+?)\s+(?:closes|quits|exits|is\s+closed)$", c)
    if m:
        return {"condition": "app_closed", "subject": (m.group("x") or m.group("x2")).strip()}
    if re.match(r"^(?:my\s+|the\s+)?phone\s+(?:connects|reconnects|is\s+connected|comes\s+online|gets\s+connected)$|"
                r"^i\s+(?:plug\s+in|connect)\s+(?:my\s+|the\s+)?phone$", c):
        return {"condition": "phone_connected"}
    if re.match(r"^(?:my\s+|the\s+)?phone\s+(?:disconnects|goes\s+offline|is\s+disconnected)$", c):
        return {"condition": "phone_disconnected"}
    m = re.match(r"^(?:my\s+|the\s+)?(?:laptop\s+|pc\s+)?battery\s+(?:drops|falls|goes|gets|is)\s+(?P<d>below|under|above|over)\s+"
                 r"(?P<n>\d{1,3})\s*(?:%|percent)?$", c)
    if m:
        return {"condition": "battery_below" if m.group("d") in ("below", "under") else "battery_above",
                "threshold": float(m.group("n"))}
    if re.match(r"^(?:a\s+|the\s+|any\s+)?download\s+(?:finishes|completes|is\s+done)$|^something\s+finishes\s+downloading$", c):
        return {"condition": "download_done"}
    return None


# ------------------------------------------------------------------------------------------------- assistant
def _assistant(t, raw, rid, mode):
    if re.match(r"^(?:say|announce|shout|read\s+out)\s+(?!.*\bto\s+[a-z]+$)(?!(?:that|it)\s+again$).+", t) and \
            not re.search(r"\b(?:message|whatsapp|text)\b", t):
        return _chat(rid, t)                                 # "say good luck out loud": JARVIS says it
    m = re.match(r"^(?:read|give|tell)\s+(?:me\s+)?(?:a\s+|the\s+)?(?:short\s+|quick\s+)?(?:summary\s+of\s+)?(?:my\s+|the\s+)"
                 r"(?P<f>[\w .'-]{2,40}?)(?:\s+summary)?$", t)
    if m and re.search(r"\bsummary\b", t) and not re.search(r"\b(?:email|mail|messages?|chat|day|calendar|news)\b", t):
        return _d(rid, t, "document_qa", {"question": f"summarize my {m.group('f')}"})
    m = re.match(r"^(?:reply|answer|respond|talk|speak)\s+(?:to\s+)?me\s+(?:only\s+)?in\s+(?P<l>english|[a-z]{0,4}glish|tamil|my\s+"
                 r"language)\b", t)
    if m:
        lang = m.group("l")
        lang = "english" if lang == "english" else "auto" if lang == "my language" else "thanglish"
        return _d(rid, t, "set_reply_language", {"mode": lang})
    if re.match(r"^(?:stop|quit|cut)\s+reading(?:\s+.*)?$", t):
        return _d(rid, t, "stop_speaking", {}, lane=RouteLane.CONTROL)
    if re.match(r"^(?:show|list|read|what\s+are)\s+(?:me\s+)?(?:my\s+)?(?:recent|latest|last)\s+(?:notes|memos)$", t):
        return _d(rid, t, "memos_recent", {})
    m = re.match(r"^remember\s+(?:that\s+)?(?P<f>[a-z][\w.-]*(?:'s|s')\s+\w+.{2,})$", t)
    if m and not re.search(r"\b(?:to|about)\s+(?:call|buy|send|pay|take|do)\b", t):
        return _d(rid, t, "remember_fact", {"fact": _raw(raw, m.group("f"))})
    m = re.match(r"^(?:can\s+you\s+|could\s+you\s+|please\s+)?forget\s+(?:what|everything)\s+i\s+(?:said|told\s+you)\s+about\s+(?P<q>.+)$", t)
    if m:
        return _d(rid, t, "forget_fact", {"query": _raw(raw, m.group("q"))})
    if re.match(r"^did\s+(?:you|u)\s+(?:already\s+|actually\s+|really\s+|just\s+)?(?:open|close|start|launch|remind|send|message|text|"
                r"install|uninstall|delete|move|play|do|run|save|turn|lock|mute|set|copy|rename)\b", t) or \
            re.match(r"^did\s+(?!you\b|u\b|i\b)[\w .'-]{2,30}?\s+(?:actually|really|properly|even)\s+(?:close|open|start|install|go\s+through|"
                     r"send|finish|get\s+(?:sent|saved|deleted|moved))\b", t):
        return _d(rid, t, "recent_actions", {"question": raw.strip()})
    if re.match(r"^when\s+did\s+i\s+(?:last\s+)?(?:open|use|ask|run|start|launch|play)\b", t):
        return _d(rid, t, "command_history", {})
    if re.match(r"^(?:repeat|say)\s+(?:what\s+you\s+(?:just\s+)?said|that|it)(?:\s+again)?$|^read\s+(?:that|it)\s+(?:again|once\s+more)$", t):
        return _d(rid, t, "recent_actions", {"question": raw.strip()})
    m = re.match(r"^(?:speak|talk|read|say)\s+(?:.+?\s+)?(?P<a>slower|faster|louder|softer|quieter)$", t)
    if m:
        a = {"quieter": "softer"}.get(m.group("a"), m.group("a"))
        return _d(rid, t, "speech_control", {"action": a}, lane=RouteLane.CONTROL)
    m = re.match(r"^what\s+(?:meetings?|events?|appointments?|calls?)\s+(?:do\s+i\s+have|have\s+i\s+got|are\s+there)\s+(?:at|around)\s+"
                 r"(?P<at>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)(?:\s+(?P<d>today|tomorrow|tonight))?$|^(?:am\s+i|will\s+i\s+be)\s+(?:free|busy|"
                 r"available)\s+(?:at|around)\s+(?P<at2>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)(?:\s+(?P<d2>today|tomorrow|tonight))?$", t)
    if m:
        return _d(rid, t, "calendar_list_events", {"time_window": m.group("d") or m.group("d2") or "today",
                                                   "at": m.group("at") or m.group("at2")})
    if re.match(r"^(?:teach\s+me|explain|give\s+me\s+(?:some\s+)?(?:ideas|tips|suggestions|advice))\b", t) and \
            not re.search(r"\b(?:file|folder|screen|error|window|page|code\s+in|this|that)\b", t):
        return _chat(rid, t)                                 # "teach me rust basics", "give me ideas for an app": a conversation
    return None


def _chat(rid: str, t: str) -> RouteDecision:
    from jarvis.core.router.models import ComplexityLevel, ReasonCode, RouteSource
    return RouteDecision(request_id=rid, lane=RouteLane.LANE_2, intent=None, slots={}, confidence=0.9,
                         source=RouteSource.EXACT, complexity=ComplexityLevel.SIMPLE, normalized_text=t,
                         reason_code=ReasonCode.QUESTION_NOT_COMMAND, candidate_count=0)


# ------------------------------------------------------------------------------------------------- PC
_NOT_APP = r"(?:pc|computer|laptop|system|machine|windows|phone|mobile|tests?|server|dictation|it|this|that|the\s+\w+|my\s+\w+)"


def _pc(t, raw, rid, mode):
    m = re.match(r"^(?:minimi[sz]e|hide)\s+(?:everything|all(?:\s+(?:the\s+)?(?:other\s+)?windows)?|all\s+other\s+windows|every\s+"
                 r"(?:other\s+)?window|the\s+rest)\s+(?:except|but|apart\s+from|other\s+than|besides)\s+(?:for\s+)?(?P<x>.+)$|"
                 r"^(?:just\s+show|show\s+only|only\s+show|focus\s+on)\s+(?P<x2>.+?)(?:\s+(?:only|and\s+hide\s+the\s+rest))$", t)
    if m:
        return _d(rid, t, "window_op", {"action": "isolate", "target": _ref(m.group("x") or m.group("x2")) or ""})
    m = re.match(rf"^(?:restart|relaunch|reopen|reboot)\s+(?P<x>(?!{_NOT_APP}$)[a-z][\w .+-]{{1,30}}?)(?:\s+app)?$", t) or \
        re.match(r"^(?P<x>[a-z][\w .+-]{1,30}?)\s+is\s+(?:acting\s+(?:weird|up|strange)|frozen|stuck|hanging|not\s+responding|lagging|"
                 r"buggy|broken|slow)\s*,?\s*(?:so\s+)?(?:please\s+)?(?:restart|relaunch|reopen)\s+it$", t)
    if m and not re.search(r"\b(?:pc|computer|laptop|phone|mobile|machine|windows|my\s+app|tests?|server)\b", m.group("x")) \
            and not re.match(r"(?:the|my|this|that|a|last|previous|closed|recent)\b|.*\b(?:tabs?|window|page|file|folder|document|"
                             r"song|video|track|download|chat|game|level)\b", m.group("x")):
        return _d(rid, t, "system_op", {"action": "restart_app", "target": m.group("x").strip()})
    m = re.match(r"^is\s+(?P<x>[a-z][\w .+-]{1,30}?)\s+(?:still\s+)?(?:running|open|active|on)(?:\s+right\s+now)?$", t)
    if m and not re.search(rf"\b(?:{_NOT_APP}|anything|something|wake\s+word|mic|microphone|dictation|wifi|bluetooth|"
                           r"dark\s+mode|music|the\s+download)\b", m.group("x")):
        return _d(rid, t, "system_op", {"action": "running", "target": m.group("x").strip()})
    m = re.match(r"^(?:turn|switch|set|put|change|go)\s+(?:on\s+|to\s+)?(?:windows\s+|the\s+(?:pc|system|laptop)\s+)?(?:to\s+|into\s+)?"
                 r"(?P<m>dark|light|night)\s+(?:mode|theme)(?:\s+on)?$|^(?:enable|use|turn\s+on|switch\s+on)\s+(?P<m2>dark|light)\s+"
                 r"(?:mode|theme)$|^(?:turn|switch)\s+(?:off|on)\s+(?P<m3>dark|light)\s+(?:mode|theme)$|^switch\s+(?:windows|the\s+pc|the\s+"
                 r"theme)\s+to\s+(?P<m4>dark|light)(?:\s+(?:mode|theme))?$", t)
    if m:
        mode_ = m.group("m") or m.group("m2") or m.group("m4") or m.group("m3")
        if m.group("m3") and re.search(r"\boff\b", t):
            mode_ = "light" if m.group("m3") == "dark" else "dark"
        return _d(rid, t, "system_op", {"action": "theme", "target": "dark" if mode_ == "night" else mode_})
    if re.match(r"^(?:read|what'?s|what\s+is)\s+(?:out\s+)?(?:on|in)?\s*(?:me\s+)?(?:my\s+|the\s+)?clipboard(?:\s+contents?)?$|"
                r"^(?:read|show)\s+(?:me\s+)?(?:my\s+|the\s+)?clipboard(?:\s+contents?|\s+text)$|^read\s+(?:me\s+)?(?:my\s+|the\s+)?clipboard$", t):
        return _d(rid, t, "clipboard_op", {"action": "read"})
    # "open / show clipboard history" stays Windows' own panel (Win+V); "my clipboard history" is JARVIS's list of this session
    if re.match(r"^(?:show|list|read|what'?s\s+in|open)\s+(?:me\s+)?my\s+clipboard\s+history$|^(?:list|read|what'?s\s+in)\s+(?:me\s+)?"
                r"(?:the\s+)?clipboard\s+history$|^what\s+(?:did|have)\s+i\s+cop(?:y|ied)(?:\s+(?:before|earlier|recently|today))?$", t):
        return _d(rid, t, "clipboard_op", {"action": "history"})
    if re.match(r"^(?:clear|wipe|delete|erase|empty)\s+(?:my\s+|the\s+)?clipboard\s+history$", t):
        return _d(rid, t, "clipboard_op", {"action": "clear_history"})
    m = re.match(rf"^(?P<v>paste|copy|bring\s+back)\s+(?:the\s+)?(?P<o>{_ORD_RE}|second\s+last|third\s+last|previous|earlier|"
                 rf"other|(?P<num>\d{{1,2}})(?:st|nd|rd|th)?)\s+(?:thing|item|text|entry|clip(?:board\s+item)?|clipboard\s+(?:item|entry))"
                 rf"(?:\s+(?:i|you)\s+(?:copied|had))?(?:\s+again)?$|^(?P<v2>paste)\s+what\s+i\s+copied\s+(?:before\s+that|earlier|"
                 rf"previously)$", t)
    if m:
        o = (m.group("o") or "previous").lower()
        n = int(m.group("num")) if m.group("num") else {"second last": 2, "third last": 3, "previous": 2, "earlier": 2,
                                                          "other": 2}.get(o, _ORD.get(o, 2))
        n = max(1, n if n > 0 else 1)
        return _d(rid, t, "clipboard_op", {"action": "paste_nth", "n": n,
                                            "paste": (m.group("v") or m.group("v2")) == "paste"})
    m = re.match(r"^(?:put|place|arrange|show|set|tile|snap)\s+(?P<a>[a-z][\w .+-]{1,25}?)\s+(?:and|&|with|next\s+to|beside)\s+"
                 r"(?P<b>[a-z][\w .+-]{1,25}?)\s+(?P<l>side\s+by\s+side|next\s+to\s+each\s+other|split\s+screen|left\s+and\s+right|"
                 r"on\s+top\s+of\s+each\s+other|stacked)$", t)
    if m:
        layout = "stack" if re.search(r"top|stack", m.group("l")) else "side_by_side"
        targets = [x if x not in ("this", "it") else "current" for x in (m.group("a").strip(), m.group("b").strip())]
        return _d(rid, t, "window_op", {"action": "arrange", "targets": targets, "layout": layout})
    if re.match(r"^switch\s+over\s+to\s+(?P<x>[a-z][\w .+-]{1,30})$", t):
        x = re.sub(r"^switch\s+over\s+to\s+", "", t)
        return _d(rid, t, "switch_window", {"target": x})
    return None
