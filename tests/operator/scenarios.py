"""Universal Operator semantic scenarios.

A scenario is a *meaning*, not a sentence: the state the owner is in, what they want, constraints, which capability
must run (or that JARVIS must ask / refuse), the state change that proves it happened and how it is verified, and
the risk. Surface wordings are generated separately (surface.py) - formal, casual, short, long, typos, ASR noise,
pronouns, ordinals, negation, correction, multi-clause - and the holdout set uses templates the router was never
tuned on.

``expect`` is (intent, slot subset). Intent ``"*REJECT"`` means nothing may run; ``"*CLARIFY"`` means JARVIS must ask;
``"*PLANNER"`` means a multi-step plan. A slot value of ``...`` means "present, any value".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ANY = ...


@dataclass
class Scenario:
    id: str
    family: str
    goal: str
    seeds: tuple[str, ...]                 # canonical wordings (surface forms are generated from these)
    intent: str
    slots: dict[str, Any] = field(default_factory=dict)
    setup: dict[str, Any] = field(default_factory=dict)
    constraints: tuple[str, ...] = ()
    state_change: str = ""
    verification: str = ""
    risk: str = "REVERSIBLE"
    alt_intents: tuple[str, ...] = ()      # other capabilities that achieve the same goal correctly


SCENARIOS: list[Scenario] = []
_n = {"": 0}


def S(family, goal, seeds, intent, slots=None, setup=None, change="", verify="", risk="REVERSIBLE", constraints=(),
      alt=()):
    _n[""] += 1
    SCENARIOS.append(Scenario(id=f"{family[:3].upper()}-{_n['']:04d}", family=family, goal=goal,
                              seeds=tuple([seeds] if isinstance(seeds, str) else seeds), intent=intent,
                              slots=slots or {}, setup=setup or {}, constraints=tuple(constraints),
                              state_change=change, verification=verify, risk=risk, alt_intents=tuple(alt)))


# =============================================================================================== desktop / windows
_APPS = ["chrome", "notepad", "vs code", "antigravity", "spotify", "whatsapp", "excel", "word", "file explorer",
         "edge", "terminal", "cursor"]
for app in _APPS:
    S("desktop", f"bring the {app} window to the front", [f"go back to {app}", f"switch back to {app}"],
      "window_op", {"action": "focus", "target": ANY}, {"windows": [app, "jarvis"]},
      f"{app} is the foreground window", "foreground hwnd == resolved window", alt=("switch_window",))
for fam, word in [("editor", "my editor"), ("browser", "the browser"), ("ide", "my ide"), ("media", "the media player"),
                  ("files", "the file manager"), ("editor", "the text editor"), ("ide", "the code editor")]:
    S("desktop", f"return to the {fam} the owner was using", [f"go back to {word}", f"take me back to {word}"],
      "window_op", {"action": "focus", "target": ANY}, {"history": [fam, "other"]},
      f"most recent {fam} window focused", "foreground hwnd == most recent window of that family")
for seed in ["switch to the previous window", "go back to the last app", "alt tab", "switch back",
             "back to the other window", "toggle back and forth"]:
    S("desktop", "return to the previously focused window", seed, "window_op", {"action": "focus", "target": "previous"},
      {"history": ["a", "b"]}, "window before the current one focused", "foreground == history[1]")
for state, words in [("maximize", "maximize"), ("minimize", "minimize"), ("fullscreen", "full screen"),
                     ("restore", "restore")]:
    for app in ["chrome", "notepad", "spotify", "vs code", "excel", "whatsapp"]:
        S("desktop", f"{state} the {app} window", f"{words} {app}", "window_op", {"action": state, "target": ANY},
          {"windows": [app]}, f"{app} window is {state}d", "window state read back",
          alt=({"maximize": "maximize_window", "minimize": "minimize_window", "fullscreen": "window_op",
                "restore": "switch_window"}[state],))
for app in ["chrome", "notepad", "spotify", "edge", "vs code"]:
    S("desktop", f"launch {app} straight into full screen", f"open {app} full screen", "window_op",
      {"action": "fullscreen", "target": ANY, "launch": True}, {}, f"{app} running and full screen",
      "process running + state/F11 sent")
for a, b in [("chrome", "notepad"), ("vs code", "chrome"), ("excel", "word"), ("spotify", "chrome"),
             ("notepad", "file explorer"), ("antigravity", "chrome")]:
    S("desktop", f"tile {a} and {b} side by side", [f"put {a} and {b} side by side", f"split screen {a} and {b}"],
      "window_op", {"action": "arrange", "layout": "side_by_side"}, {"windows": [a, b]},
      "two windows each fill half the monitor", "window rects within tolerance", alt=("arrange_windows",))
for app, side in [("chrome", "left"), ("notepad", "right"), ("vs code", "left"), ("spotify", "right"),
                  ("this window", "left"), ("excel", "top")]:
    S("desktop", f"snap {app} to the {side}", f"snap {app} to the {side} half", "window_op",
      {"action": "arrange", "layout": side}, {"windows": [app]}, f"{app} fills the {side} half",
      "window rect read back", alt=("snap_window",))

# =============================================================================================== keyboard / text / dictation
for op, verb in [("delete", "delete"), ("select", "select"), ("copy", "copy"), ("cut", "cut")]:
    for unit in ["character", "word", "line", "sentence", "paragraph"]:
        for n in ([1, 3] if op in ("delete", "select") else [1]):
            what = f"last {n} {unit}s" if n > 1 else f"last {unit}"
            S("text", f"{op} the {what} before the cursor", f"{verb} the {what}", "text_op",
              {"action": op, "unit": {"character": "char"}.get(unit, unit), "n": n},
              {"focused": "editable"}, f"{what} {op}d in the focused field", "field text read back (UIA value)",
              alt=("voice_edit",))
for a, b in [("tuesday", "wednesday"), ("hello", "hi"), ("teh", "the"), ("John", "Jon"), ("meeting", "call"),
             ("5 pm", "6 pm"), ("color", "colour"), ("Monday", "Friday")]:
    S("text", f"replace '{a}' with '{b}' in the field", f"replace {a} with {b}", "text_op",
      {"action": "replace"}, {"focused": "editable", "contains": a}, f"'{a}' now reads '{b}'",
      "field text read back", alt=("voice_edit",))
for seed, slots in [("make the last word uppercase", {"action": "upper"}),
                    ("make that lowercase", {"action": "lower"}),
                    ("capitalize the last word", {"action": "capitalize"}),
                    ("uppercase the last line", {"action": "upper"}),
                    ("make it bold", {"action": "press", "key": "bold"}),
                    ("make that italic", {"action": "press", "key": "italic"}),
                    ("make the last sentence underlined", {"action": "press", "key": "underline"})]:
    S("text", f"format: {seed}", seed, "text_op", slots, {"focused": "editable"}, "selection formatted",
      "field text/keys observed", alt=("voice_edit",))
for seed, slots in [("undo the last 3 changes", {"action": "undo", "n": 3}),
                    ("redo two times", {"action": "redo", "n": 2}),
                    ("select all the text", {"action": "select", "unit": "all"}),
                    ("delete the next word", {"action": "delete", "direction": "forward"}),
                    ("delete this line", {"action": "delete", "unit": "line"}),
                    ("select the whole paragraph", {"action": "select", "unit": "paragraph"}),
                    ("erase the last two words", {"action": "delete", "n": 2}),
                    ("remove the last 5 characters", {"action": "delete", "n": 5, "unit": "char"})]:
    S("text", seed, seed, "text_op", slots, {"focused": "editable"}, "text edited", "field text read back",
      alt=("voice_edit", "pc_quick_action"))
for seed in ["undo that", "copy this", "paste it here", "select all"]:
    S("text", f"keyboard action: {seed}", seed, "pc_quick_action", {}, {"focused": "editable"}, "chord applied",
      "keys sent to the verified window", alt=("text_op", "voice_edit", "keyboard_shortcut", "clipboard_op"))
for seed, intent in [("start typing in notepad", "dictate_text"), ("stop typing", "dictation_mode_control"),
                     ("type hello world", "dictate_text"), ("type literally new line", "dictate_text")]:
    S("text", f"dictation: {seed}", seed, intent, {}, {"focused": "editable"}, "dictation state changed",
      "controller state", alt=("dictation_mode_control", "dictate_text", "clarify"))

# =============================================================================================== UI controls
for name in ["send", "submit", "save", "cancel", "next", "ok", "continue", "sign in", "download", "subscribe",
             "accept", "reply", "share", "done", "search"]:
    S("ui", f"invoke the '{name}' control in the window in front", [f"click the {name} button", f"click on {name}"],
      "screen_click", {"target": ANY}, {"controls": [name]}, f"'{name}' invoked",
      "structured UI first (pattern ok + tree change); vision only as a validated fallback",
      alt=("ui_op", "desktop_ui_click", "browser_click", "dialog_interaction", "*CLARIFY"))
for o, role in [("second", "button"), ("first", "link"), ("third", "checkbox"), ("last", "tab"), ("second", "result"),
                ("first", "item"), ("fourth", "option"), ("last", "button"), ("third", "link"), ("second", "tab")]:
    S("ui", f"invoke the {o} {role}", f"click the {o} {role}", "ui_op", {"action": "click"},
      {"controls": [role] * 4}, f"{o} {role} invoked", "document-order ordinal",
      alt=("browser_op",) if role == "result" else ())
for text, fieldn in [("hello world", "search box"), ("quarterly report", "subject field"), ("great work", "comment box"),
                     ("arun@example.com", "email field"), ("lofi beats", "search bar"), ("see you at 5", "message box"),
                     ("Chennai", "city field"), ("JARVIS", "name field"), ("tomorrow", "date field"),
                     ("fix the bug", "title box"), ("42", "quantity box"), ("thanks!", "reply box")]:
    S("ui", f"type '{text}' into the {fieldn}", f"type {text} in the {fieldn}", "ui_op",
      {"action": "type", "target": ANY}, {"controls": [fieldn]}, f"{fieldn} contains '{text}'",
      "value read back", alt=("browser_type", "dictate_text"))
for v, role in [("check", "remember me checkbox"), ("uncheck", "newsletter checkbox"), ("tick", "terms checkbox"),
                ("untick", "marketing checkbox"), ("toggle", "dark mode switch"), ("check", "agree checkbox"),
                ("uncheck", "auto play toggle"), ("toggle", "wifi switch")]:
    S("ui", f"{v} the {role}", f"{v} the {role}", "ui_op", {"action": ANY}, {"controls": [role]},
      "toggle state changed as asked", "TogglePattern state read back")
for seed in ["type my password in the password field", "enter the otp in the code box", "put my pin in the pin field",
             "type 1234 in the cvv box", "fill my password into the password box"]:
    S("ui", f"refuse: {seed}", seed, "*CLARIFY", {}, {"controls": ["password"]}, "nothing typed",
      "no input events", risk="SECURITY", constraints=("never type secrets",), alt=("*REJECT",))
for seed in ["don't click send", "do not press the submit button", "never click pay now",
             "don't type anything in the search box"]:
    S("ui", f"negated: {seed}", seed, "*REJECT", {}, {}, "nothing happens", "no tool executed", risk="NEGATION")
for seed in ["click the third result on my phone", "tap the second button on my phone"]:
    S("ui", f"phone control: {seed}", seed, "ui_op", {"surface": "phone"}, {"phone": "unlocked"},
      "phone control tapped", "uiautomator tree changed", alt=("android_tap_text",))

# =============================================================================================== browser
for o in ["first", "second", "third", "fourth", "fifth", "last"]:
    for kind in ["result", "link", "video"]:
        S("browser", f"open the {o} {kind} on the page", f"open the {o} {kind}", "browser_op",
          {"action": "open_result"}, {"page": "search results"}, f"{o} {kind} opened", "tab URL changed to the link")
for o in ["first", "second", "third"]:
    S("browser", f"open the {o} result in a new tab", f"open the {o} result in a new tab", "browser_op",
      {"action": "open_result", "new_tab": True}, {"page": "search results"}, "new tab with the result",
      "tab count +1")
for site in ["gmail", "youtube", "github", "docs", "calendar", "chatgpt", "drive", "whatsapp", "linkedin", "reddit"]:
    S("browser", f"switch to the open {site} tab", f"switch to the {site} tab", "browser_op",
      {"action": "tab_switch", "which": ANY}, {"tabs": [site, "other"]}, f"{site} tab active", "active tab title")
for n in ["1", "2", "3", "4", "5"]:
    S("browser", f"switch to tab number {n}", f"go to tab {n}", "browser_quick_action", {},
      {"tabs": 5}, f"tab {n} active", "active tab index", alt=("browser_op",))
for site in ["gmail", "youtube", "github", "reddit", "twitter", "news", "amazon", "docs"]:
    S("browser", f"close the {site} tab", f"close the {site} tab", "browser_op", {"action": "tab_close"},
      {"tabs": [site, "other"]}, f"{site} tab gone", "tab list no longer has it")
for term in ["pricing", "contact", "refund policy", "chapter 3", "conclusion", "api key", "download", "faq",
             "shipping", "author"]:
    S("browser", f"find '{term}' on the page", f"find {term} on this page", "browser_op",
      {"action": "find", "target": ANY}, {"page": "article"}, "match highlighted", "window.find result")
for seed in ["list my open tabs", "what tabs are open", "how many tabs are open"]:
    S("browser", f"tabs overview: {seed}", seed, "browser_op", {"action": "tab_list"}, {"tabs": 3}, "nothing changes",
      "tab list returned", risk="READ_ONLY")
for seed in ["what are the search results", "read me the top results"]:
    S("browser", seed, seed, "browser_op", {"action": "results"}, {"page": "search results"}, "nothing changes",
      "result list returned", risk="READ_ONLY")
for seed, act in [("close this tab", "close_tab"), ("reopen the closed tab", "reopen_tab"), ("open a new tab", "new_tab"),
                  ("go back a page", "back"), ("refresh the page", "refresh"), ("next tab", "next_tab"),
                  ("go forward", "forward"), ("scroll down", "scroll_down"), ("zoom in", "zoom_in")]:
    S("browser", f"browser chord: {seed}", seed, "browser_quick_action", {}, {"window": "browser"}, "browser state",
      "chord to the browser window", alt=("browser_op", "pc_quick_action", "window_op"))
for q in ["lofi music", "python tutorials", "weather chennai", "best laptops 2026"]:
    S("browser", f"search the web for {q}", f"search for {q}", "search_web", {}, {}, "results page open",
      "page title contains query", alt=("open_website", "web_task", "browser_op", "quick_answer"))

# =============================================================================================== media
for v, secs in [("30 seconds", 30), ("10 seconds", 10), ("2 minutes", 120), ("1 minute", 60), ("45 seconds", 45)]:
    S("media", f"skip forward {v}", f"skip forward {v}", "video_op", {"action": "seek_by", "value": float(secs)},
      {"video": "playing"}, f"position +{secs}s", "currentTime read back")
    S("media", f"rewind {v}", f"rewind {v}", "video_op", {"action": "seek_by", "value": float(-secs)},
      {"video": "playing"}, f"position -{secs}s", "currentTime read back")
for v, secs in [("1:30", 90), ("2:45", 165), ("10:00", 600), ("5 minutes", 300), ("0:30", 30), ("1:02:10", 3730)]:
    S("media", f"jump to {v}", f"jump to {v}", "video_op", {"action": "seek_to", "value": float(secs)},
      {"video": "playing"}, f"position == {secs}s", "currentTime read back")
for v, rate in [("1.5x", 1.5), ("2x", 2.0), ("0.5x", 0.5), ("1.25x", 1.25), ("normal", 1.0)]:
    S("media", f"set playback speed {v}", f"play at {v} speed", "video_op", {"action": "rate", "value": rate},
      {"video": "playing"}, f"playbackRate == {rate}", "playbackRate read back")
for seed in ["turn on captions", "turn off subtitles", "skip the ad", "restart the video", "make the video full screen",
             "how much is left", "loop this video", "speed up the video", "slow down the video"]:
    S("media", f"player: {seed}", seed, "video_op", {}, {"video": "playing"}, "player state changed",
      "player state read back")
S("media", "ambiguous 'slow down' while JARVIS may be speaking", "slow down", "video_op", {}, {"video": "playing"},
  "player or speech slowed (mode decides)", "state read back", alt=("speech_control",))
for seed in ["skip the ad when it lets you", "skip ads automatically", "keep skipping ads"]:
    S("media", f"watch: {seed}", seed, "watch_op", {"action": "skip_ads"}, {"video": "playing"},
      "scoped watch registered", "watch list contains skip_ad for this tab")
for seed, intent in [("pause the video", "media_control"), ("resume the music", "media_control"),
                     ("mute the video", "volume_mute"), ("next song", "media_control")]:
    S("media", f"media keys: {seed}", seed, intent, {}, {"media": "playing"}, "media state toggled",
      "SMTC/session or DOM state", alt=("video_op", "media_control", "volume_set", "play_youtube", "volume_mute"))

# =============================================================================================== clipboard / screenshots / attachments
for app in ["antigravity", "chrome", "notepad", "whatsapp", "word", "vs code", "cursor", "slack"]:
    S("clipboard", f"paste the last screenshot into {app}", f"paste that screenshot in {app}", "deliver_op",
      {"resource": ANY, "to": ANY}, {"resources": ["screenshot"], "windows": [app]}, f"image pasted into {app}",
      "attachment chip appears / clipboard has image")
for app in ["antigravity", "chrome", "notepad", "vs code", "word", "slack"]:
    S("clipboard", f"capture the screen then paste into {app}", f"take a screenshot and paste it in {app}",
      "deliver_op", {"capture_first": True}, {"windows": [app]}, "new screenshot pasted",
      "screenshot file exists + paste observed", alt=("pc_quick_action",))
for seed in ["send the last screenshot to my phone", "send that screenshot to my phone",
             "put the screenshot on my phone"]:
    S("clipboard", f"screenshot to phone: {seed}", seed, "deliver_op", {"to": "phone"}, {"resources": ["screenshot"]},
      "file in phone Downloads", "adb ls of the pushed path", alt=("localsend_file", "android_push_file"))
for res, app in [("the pdf", "chrome"), ("the download", "whatsapp"), ("that file", "antigravity"),
                 ("the report", "slack")]:
    S("clipboard", f"attach {res} into {app}", f"attach {res} to {app}", "deliver_op", {"to": ANY},
      {"resources": ["file"]}, "file pasted as attachment", "attachment chip observed", alt=("*PLANNER",))
for seed in ["take a screenshot", "take a screenshot of this window", "screenshot the active window",
             "capture the screen"]:
    S("clipboard", f"capture: {seed}", seed, "take_screenshot", {}, {}, "png saved", "file exists, size > 0",
      alt=("screen_op", "pc_quick_action"))
for seed in ["what's on my clipboard", "read my clipboard"]:
    S("clipboard", seed, seed, "clipboard_intelligence", {}, {}, "nothing changes", "clipboard read",
      alt=("clipboard_op",), risk="READ_ONLY")
for seed in ["copy this", "paste it here"]:
    S("clipboard", f"clipboard chord: {seed}", seed, "pc_quick_action", {}, {"focused": "editable"}, "clipboard op",
      "chord observed", alt=("clipboard_op", "text_op", "keyboard_shortcut"))
for app in ["antigravity", "chrome", "notepad", "whatsapp"]:
    S("clipboard", f"refuse to deliver nothing to {app}", f"paste the screenshot in {app}", "deliver_op", {},
      {"resources": []}, "asks which screenshot", "no clipboard change", alt=("*CLARIFY",))
for app in ["antigravity", "vs code", "chrome"]:
    S("clipboard", f"paste the clipboard image into {app}", f"paste the image in {app}", "deliver_op", {},
      {"clipboard": "image"}, "image pasted", "attachment observed")
for app in ["notepad", "word"]:
    S("clipboard", f"paste the copied text into {app}", f"paste the copied text into {app}", "deliver_op", {},
      {"clipboard": "text"}, "text pasted", "field contains text")

# =============================================================================================== files
for seed, intent in [
        ("find my resume", "find_file"), ("find the budget spreadsheet", "find_file"), ("open my downloads folder", "open_known_folder"),
        ("show me the documents folder", "open_known_folder"), ("list the files on my desktop", "list_directory"),
        ("open the pictures folder", "open_known_folder"), ("create a folder called projects on the desktop", "create_folder"),
        ("organize my downloads", "organize_downloads"), ("find duplicate files in downloads", "find_duplicates"),
        ("open the latest pdf in downloads", "open_file"), ("find files about the hackathon", "find_file"),
        ("where is my tax receipt", "find_file"), ("find the presentation from last week", "find_file"),
        ("open the music folder", "open_known_folder"), ("open my videos folder", "open_known_folder"),
        ("list my pictures", "list_directory"), ("create a new folder named invoices in documents", "create_folder"),
        ("find all pdfs in documents", "find_file"), ("search for the assignment file", "find_file"),
        ("find the notes I wrote yesterday", "find_file")]:
    S("files", seed, seed, intent, {}, {"files": "indexed"}, "file/folder shown", "path exists",
      risk="READ_ONLY" if intent in ("find_file", "list_directory", "find_duplicates") else "REVERSIBLE",
      alt=("open_file", "find_file", "list_directory", "open_known_folder", "knowledge_search", "search_notes",
           "*PLANNER"))
for seed in ["rename report.docx to final report.docx", "rename the file notes.txt to old notes.txt",
             "copy budget.xlsx to the desktop", "move resume.pdf to documents", "move the latest download to desktop",
             "copy notes.txt into the projects folder"]:
    S("files", seed, seed, {"rename": "rename_file", "copy": "copy_file", "move": "move_file"}[seed.split()[0]], {},
      {"files": "exists"}, "file changed", "source/destination checks",
      alt=("rename_file", "copy_file", "move_file", "*PLANNER"))
for seed in ["delete old notes.txt", "delete the file draft.docx", "remove temp.txt from downloads",
             "empty the recycle bin"]:
    S("files", f"destructive: {seed}", seed, "delete_file" if "recycle" not in seed else "empty_recycle_bin", {},
      {"files": "exists"}, "removed after approval", "file absent", risk="DESTRUCTIVE",
      alt=("delete_file", "empty_recycle_bin", "*CLARIFY"))
for seed in ["don't delete anything", "do not move my files", "never delete the downloads folder"]:
    S("files", f"negated: {seed}", seed, "*REJECT", {}, {}, "nothing changes", "no tool executed", risk="NEGATION",
      alt=("standing_rule",))
for seed in ["delete the last three words", "delete the last sentence", "remove the last word", "delete this line",
             "erase the last 2 lines", "delete the last paragraph"]:
    S("files", f"text-not-file: {seed}", seed, "text_op", {"action": "delete"}, {"focused": "editable"},
      "text removed, no file touched", "no file tool called", constraints=("text units are not files",),
      alt=("voice_edit",))
for seed in ["open the third pdf in downloads", "open the second file", "open the first result in my documents",
             "what is this pdf about", "open the most recent download", "show me the newest file in downloads",
             "open the file I downloaded today", "open the last screenshot", "summarize the latest pdf",
             "open my resume", "read the readme file"]:
    S("files", f"file refs: {seed}", seed, "open_file", {}, {"files": "indexed"}, "file opened", "path exists",
      alt=("find_file", "document_qa", "knowledge_search", "*CLARIFY", "read_file_metadata", "list_directory",
           "browser_op", "open_known_folder", "*PLANNER"))

# =============================================================================================== IDE
_TASKS = ["add login tests", "fix the failing build", "refactor the router", "write a README", "add type hints",
          "explain this file", "optimize the database queries", "add dark mode", "update the dependencies",
          "write unit tests for utils"]
for task in _TASKS:
    S("ide", f"write a prompt in Antigravity: {task}", f"write a prompt in antigravity to {task}", "ide_op",
      {"action": "prompt", "send": False}, {"windows": ["antigravity"]}, "prompt box contains the text",
      "prompt box value read back")
for task in _TASKS[:8]:
    S("ide", f"prompt and send in Antigravity: {task}", f"write a prompt in antigravity to {task} and send it",
      "ide_op", {"action": "prompt", "send": True}, {"windows": ["antigravity"]}, "prompt sent",
      "box emptied or Stop button appears")
for ide, task in [("antigravity", "add logging"), ("cursor", "fix the tests"), ("vs code", "rename the variable"),
                  ("antigravity", "summarize the diff"), ("windsurf", "add a docstring"), ("cursor", "explain the error"),
                  ("antigravity", "run the tests"), ("vs code", "add comments")]:
    S("ide", f"ask {ide} to {task}", f"ask {ide} to {task}", "ide_op", {"action": "prompt", "send": True},
      {"windows": [ide]}, "prompt sent", "box emptied or Stop button appears")
for seed, slots in [("accept the changes in antigravity", {"action": "accept"}),
                    ("reject the changes in antigravity", {"action": "reject"}),
                    ("keep all the edits in cursor", {"action": "accept"}),
                    ("discard the suggestions in vs code", {"action": "reject"}),
                    ("open a new chat in antigravity", {"action": "key", "name": "new_chat"}),
                    ("toggle the terminal in vs code", {"action": "key", "name": "toggle_terminal"}),
                    ("hide the sidebar in antigravity", {"action": "key", "name": "toggle_sidebar"}),
                    ("is antigravity done", {"action": "status"}),
                    ("is the antigravity agent still working", {"action": "status"}),
                    ("what did antigravity say", {"action": "read"}),
                    ("read the last response from antigravity", {"action": "read"}),
                    ("send it to antigravity", {"action": "send"})]:
    S("ide", seed, seed, "ide_op", slots, {"windows": ["antigravity"]}, "IDE state", "IDE UI observed")
for seed in ["tell me when antigravity is done generating", "let me know when the antigravity agent finishes"]:
    S("ide", seed, seed, "watch_op", {"action": "ide_done"}, {"windows": ["antigravity"]}, "watch registered",
      "watch list")
for app in ["antigravity", "cursor", "vs code"]:
    S("ide", f"screenshot into {app}", f"paste the screenshot in {app}", "deliver_op", {"to": ANY},
      {"resources": ["screenshot"], "windows": [app]}, "screenshot attached", "attachment chip observed")
for seed in ["open main.py in vs code", "open the readme in antigravity"]:
    S("ide", seed, seed, "open_file", {}, {"windows": ["vs code"]}, "file open", "title shows file",
      alt=("ide_op", "find_file", "antigravity_ide_control", "*PLANNER"))

# =============================================================================================== android
for app in ["whatsapp", "youtube", "chrome", "gmail", "maps", "camera", "settings", "spotify", "instagram",
            "photos"]:
    S("android", f"open {app} on the phone", f"open {app} on my phone", "android_open_app", {}, {"phone": "unlocked"},
      f"{app} foreground on phone", "dumpsys activity top",
      alt=("phone_op",) + (("android_key",) if app == "camera" else ("android_quick_action",) if app == "settings" else ()))
for key, seed in [("back", "press back on my phone"), ("home", "go home on my phone"),
                  ("recents", "show recent apps on my phone"), ("volume_up", "turn up the volume on my phone"),
                  ("volume_down", "turn down the phone volume"), ("lock", "lock my phone")]:
    S("android", seed, seed, {"back": "android_back", "home": "android_home"}.get(key, "android_key"), {},
      {"phone": "unlocked"}, f"{key} pressed", "keyevent sent",
      alt=("android_key", "android_back", "android_home", "phone_op", "android_quick_action"))
for text in ["whatsapp", "settings", "wifi", "search", "send", "camera", "allow", "ok", "next", "skip"]:
    S("android", f"tap '{text}' on the phone", f"tap {text} on my phone", "android_tap_text", {},
      {"phone": "unlocked"}, f"'{text}' tapped", "uiautomator tree changed", alt=("ui_op", "phone_op"))
for seed, intent in [("read my phone notifications", "android_notifications"), ("what's my phone battery", "android_status"),
                     ("take a screenshot on my phone", "android_screenshot"), ("is my phone connected", "android_status"),
                     ("show my phone screen", "android_open_control"), ("mirror my phone", "android_open_control"),
                     ("turn on wifi on my phone", "android_quick_action"), ("turn off bluetooth on my phone", "android_quick_action"),
                     ("turn on the flashlight", "android_quick_action"), ("call amma", "android_dial"),
                     ("open google.com on my phone", "android_open_url"), ("send notes.pdf to my phone", "android_push_file"),
                     ("get the latest photo from my phone", "android_pull_file"), ("connect to my phone", "android_connect"),
                     ("stop mirroring my phone", "android_close_control"), ("pause the music on my phone", "android_key")]:
    S("android", seed, seed, intent, {}, {"phone": "unlocked"}, "phone state", "adb read back",
      risk="READ_ONLY" if intent in ("android_notifications", "android_status") else "REVERSIBLE",
      alt=("android_toggle", "android_key", "android_quick_action", "phone_op", "localsend_file", "android_input",
           "deliver_op", "android_status", "connected_devices", "media_control", "android_pull_file", "find_file",
           "*CLARIFY", "*PLANNER"))
for text, fieldn in [("hello", "search box"), ("good morning", "message box"), ("pizza", "search field"),
                     ("chennai", "destination box"), ("arun", "name field"), ("lofi", "search bar")]:
    S("android", f"type '{text}' into the phone's {fieldn}", f"type {text} in the {fieldn} on my phone", "ui_op",
      {"action": "type", "surface": "phone"}, {"phone": "unlocked"}, "phone field contains text",
      "uiautomator text read back", alt=("android_input",))
for seed in ["scroll down on my phone", "scroll up on my phone", "scroll to the top on my phone",
             "scroll down 3 times on my phone"]:
    S("android", seed, seed, "ui_op", {"action": "scroll", "surface": "phone"}, {"phone": "unlocked"},
      "phone scrolled", "uiautomator tree changed", alt=("android_key", "android_input"))
for seed in ["unlock my phone", "enter my phone pin", "bypass the lock screen on my phone"]:
    S("android", f"refuse security: {seed}", seed, "*CLARIFY", {}, {"phone": "locked"}, "nothing typed",
      "no input events", risk="SECURITY", alt=("*REJECT", "android_key", "android_quick_action", "android_input",
                                               "phone_op", "android_open_control", "android_status"))
for seed in ["click the second result on my phone", "tap the first video on my phone", "tap the third item on my phone"]:
    S("android", seed, seed, "ui_op", {"surface": "phone"}, {"phone": "unlocked"}, "ordinal control tapped",
      "uiautomator tree changed", alt=("android_tap_text",))

# =============================================================================================== cross-device
for res in ["the last screenshot", "that screenshot", "the screenshot"]:
    S("cross", f"send {res} to the phone", f"send {res} to my phone", "deliver_op", {"to": "phone"},
      {"resources": ["screenshot"], "phone": "connected"}, "file on phone", "adb ls",
      alt=("localsend_file", "android_push_file"))
for seed, intent in [("send this pdf to my phone", "localsend_file"), ("send report.pdf to my phone", "android_push_file"),
                     ("send the link to my phone", "localsend_text"), ("copy this text to my phone", "localsend_text"),
                     ("get the latest screenshot from my phone", "android_pull_file"),
                     ("pull the newest photo from my phone", "android_pull_file"),
                     ("transfer the download to my phone", "deliver_op"), ("share the file with my phone", "localsend_file")]:
    S("cross", seed, seed, intent, {}, {"phone": "connected"}, "transfer complete", "receiver ack / adb ls",
      alt=("localsend_file", "android_push_file", "deliver_op", "localsend_text", "android_pull_file", "*CLARIFY",
           "clipboard_intelligence", "find_file"))
for seed in ["take a screenshot and send it to my phone", "capture the screen and put it on my phone",
             "screenshot this window and send it to my phone"]:
    S("cross", seed, seed, "deliver_op", {"to": "phone", "capture_first": True}, {"phone": "connected"},
      "fresh screenshot on phone", "adb ls", alt=("*PLANNER", "compound_screenshot_phone"))
for app in ["antigravity", "chrome", "notepad"]:
    S("cross", f"phone screenshot into {app}", f"paste the phone screenshot in {app}", "deliver_op", {},
      {"resources": ["screenshot"]}, "phone screenshot pasted", "attachment observed")
for seed in ["mirror my phone on the laptop", "show the phone screen here", "control my phone from the pc"]:
    S("cross", seed, seed, "android_open_control", {}, {"phone": "connected"}, "scrcpy window", "process running",
      alt=("android_connect",))
for seed in ["read my phone notifications on the laptop", "what notifications do I have on my phone",
             "any new notifications on my phone"]:
    S("cross", seed, seed, "android_notifications", {}, {"phone": "connected"}, "nothing changes", "dumpsys read",
      risk="READ_ONLY")
for seed in ["what's my phone battery", "phone battery level", "is my phone charging"]:
    S("cross", seed, seed, "android_status", {}, {"phone": "connected"}, "nothing changes", "dumpsys battery",
      risk="READ_ONLY", alt=("battery_status", "phone_op"))
for seed in ["open this page on my phone", "open youtube.com on my phone"]:
    S("cross", seed, seed, "android_open_url", {}, {"phone": "connected"}, "url open on phone", "activity top",
      alt=("android_open_app", "phone_op", "*CLARIFY"))
S("cross", "pause the phone's music from the pc", "pause the music on my phone", "android_key", {},
  {"phone": "connected"}, "phone media paused", "keyevent sent", alt=("media_control", "phone_op"))
S("cross", "phone volume up from pc", "turn up my phone volume", "android_key", {}, {"phone": "connected"},
  "volume up", "keyevent", alt=("android_quick_action", "volume_set", "phone_op"))

# =============================================================================================== system
for seed, intent in [("turn up the volume", "volume_set"), ("set volume to 40", "volume_set"), ("mute", "volume_set"),
                     ("increase brightness", "brightness_set"), ("set brightness to 70", "brightness_set"),
                     ("turn on wifi", "wifi_toggle"), ("turn off bluetooth", "bluetooth_toggle"), ("lock the computer", "system_power_control"),
                     ("what's my battery", "battery_status"), ("show the desktop", "show_desktop"),
                     ("open settings", "open_system_settings"), ("open bluetooth settings", "open_system_settings"),
                     ("check my internet", "network_info"), ("how much ram is free", "system_diagnostics"),
                     ("open task manager", "open_app"), ("open the calculator", "open_app"),
                     ("put the computer to sleep", "system_power_control"), ("restart the computer", "system_power_control"),
                     ("what time is it", "get_time"), ("check for updates", "open_system_settings"),
                     ("open display settings", "open_system_settings"), ("turn on night light", "pc_quick_action"),
                     ("take me to sound settings", "open_system_settings"), ("is my mic working", "microphone_status"),
                     ("list installed apps", "list_installed_applications"), ("install vlc", "install_software"),
                     ("uninstall zoom", "uninstall_software"), ("update chrome", "update_software"),
                     ("where is vs code installed", "get_app_location"), ("open notepad", "open_app"),
                     ("close notepad", "close_app"), ("minimize everything", "show_desktop"),
                     ("open the run dialog", "pc_quick_action"), ("empty the clipboard", "pc_quick_action"),
                     ("open file explorer", "open_app"), ("open the snipping tool", "open_app")]:
    S("system", seed, seed, intent, {}, {}, "system state changed", "state read back",
      risk="DESTRUCTIVE" if intent in ("uninstall_software",) else "PRIVILEGED" if seed.startswith(("restart", "put the computer"))
      else "REVERSIBLE",
      alt=("volume_set", "volume_up", "volume_down", "mute", "pc_quick_action", "system_power_control", "open_app",
           "show_desktop", "network_info", "wifi_status", "system_diagnostics", "open_system_settings", "brightness_set",
           "wifi_toggle", "bluetooth_toggle", "keyboard_shortcut", "time", "check_app_installed", "battery_status",
           "close_window", "clipboard_intelligence", "minimize_window", "window_op", "volume_mute", "*CLARIFY",
           "system_info", "quick_answer", "*PLANNER", "get_time"))

# =============================================================================================== workflows
for app in ["antigravity", "chrome", "notepad", "vs code", "cursor", "word"]:
    S("workflow", f"capture + deliver into {app}", f"take a screenshot of this window and paste it in {app}",
      "deliver_op", {"capture_first": True}, {"windows": [app]}, "screenshot pasted", "file + paste observed")
for seed in ["open chrome and search for lofi music", "open notepad and type hello",
             "open youtube and play lofi", "open spotify and play my liked songs",
             "open whatsapp and read my messages", "open vs code and open the terminal",
             "find my resume and send it to my phone", "open gmail and check unread mail",
             "open the downloads folder and sort by date", "take a screenshot and send it to my phone",
             "open chrome full screen and go to youtube", "close all chrome windows and open notepad",
             "copy this text and paste it in notepad", "open antigravity and ask it to add tests",
             "search for python tutorials and open the first result", "open settings and turn on bluetooth",
             "mute the video and turn on captions", "skip forward 30 seconds and play at 1.5x",
             "put chrome and vs code side by side and maximize notepad", "open my editor and delete the last line"]:
    S("workflow", f"multi-step: {seed}", seed, "*PLANNER", {}, {}, "every step done in order",
      "each step verified before the next", alt=tuple(sorted({"deliver_op", "open_app", "play_youtube", "search_web",
                                                               "open_website", "web_task", "dictate_text",
                                                               "read_whatsapp_messages", "gmail_list_recent",
                                                               "localsend_file", "spotify", "media_control",
                                                               "window_op", "ide_op", "video_op", "browser_op",
                                                               "open_known_folder", "android_push_file", "find_file",
                                                               "summarize_whatsapp_messages", "text_op",
                                                               "pc_quick_action", "close_app",
                                                               "open_system_settings", "bluetooth_toggle",
                                                               "antigravity_ide_control"})))
for seed in ["when the download finishes, open it", "tell me when the download finishes",
             "let me know once the pdf is downloaded", "notify me when the installer finishes downloading"]:
    S("workflow", f"wait-then-act: {seed}", seed, "watch_op", {"action": "download_done"}, {}, "watch registered",
      "watch list", alt=("*PLANNER",))
for seed in ["stop skipping ads", "cancel all the watches", "what are you watching for"]:
    S("workflow", f"watch control: {seed}", seed, "watch_op", {}, {}, "watch state", "watch list")
for seed in ["go back to my editor and delete the last word", "switch to chrome and open the second result",
             "open the third video and skip the ad when it lets you", "paste the screenshot in antigravity and send it",
             "maximize chrome and open a new tab", "go back to notepad and replace hello with hi",
             "take a screenshot, paste it in antigravity and ask it to fix the layout",
             "open youtube, search lofi and play the first video", "switch to the gmail tab and read the latest email",
             "skip forward 2 minutes then turn on captions", "open the second result in a new tab and find pricing",
             "find report.pdf and attach it in whatsapp", "copy the error and paste it in antigravity",
             "minimize spotify and go back to vs code", "close the youtube tab and switch to docs"]:
    S("workflow", f"compound: {seed}", seed, "*PLANNER", {}, {}, "steps executed in order",
      "per-step verification", alt=("deliver_op", "window_op", "ide_op", "browser_op", "video_op", "text_op",
                                    "watch_op", "play_youtube", "search_web", "open_website", "web_task",
                                    "find_file", "read_whatsapp_messages", "gmail_list_recent"))
