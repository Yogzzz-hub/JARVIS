"""Generate docs/UNIVERSAL_OPERATOR_CAPABILITY_CATALOG.md from the primitive families.

Each behavior is a (family, behavior, capability, slots, references, risk, verification, example) row. Behaviors are
compositions of the ~30 primitives in jarvis/core/operator - the catalog documents what they cover; it is not a list
of handlers. Run:  python scripts/gen_operator_catalog.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

ROWS: list[tuple[str, str, str, str, str, str, str, str]] = []


def B(fam, behavior, cap, slots="", refs="", risk="REVERSIBLE", verify="", ex=""):
    ROWS.append((fam, behavior, cap, slots, refs, risk, verify, ex))


# ------------------------------------------------------------------------------------------------ Desktop / windows
APPS = ["Chrome", "Edge", "Firefox", "Notepad", "VS Code", "Antigravity", "Cursor", "Word", "Excel", "PowerPoint",
        "Spotify", "WhatsApp", "File Explorer", "Terminal"]
for a in APPS:
    B("Desktop", f"Focus {a} by name", "window_op.focus", "target=app", "foreground history", verify="foreground hwnd == target",
      ex=f"switch to {a.lower()}")
for fam, word in [("editor", "my editor"), ("browser", "the browser"), ("ide", "my IDE"), ("media", "the player"),
                  ("files", "the file manager"), ("chat", "the chat app"), ("previous", "the previous window")]:
    B("Desktop", f"Return to {word}", "window_op.focus", "target=family|previous", "foreground history (JARVIS excluded)",
      verify="foreground == most recent window of that family", ex=f"go back to {word}")
for state in ["maximize", "minimize", "restore", "fullscreen", "close"]:
    for a in ["Chrome", "Notepad", "VS Code", "Spotify", "Excel", "a named window"]:
        B("Desktop", f"{state.title()} {a}", f"window_op.{state}", "target", "window resolver",
          "REVERSIBLE" if state != "close" else "EXTERNAL_EFFECT",
          verify="IsIconic/IsZoomed read back" if state != "close" else "window gone or app asks to save",
          ex=f"{state} {a.lower()}")
for lay in ["left half", "right half", "top half", "bottom half", "top-left quarter", "top-right quarter",
            "bottom-left quarter", "bottom-right quarter", "centre", "next monitor", "previous monitor"]:
    B("Desktop", f"Place a window: {lay}", "window_op.arrange", "target, layout", "monitor work area",
      verify="window rect within 16 px", ex=f"snap chrome to the {lay}")
for pair in [("Chrome", "Notepad"), ("VS Code", "Chrome"), ("Antigravity", "Chrome"), ("Word", "Excel")]:
    B("Desktop", f"Side by side: {pair[0]} + {pair[1]}", "window_op.arrange", "targets[], layout=side_by_side",
      "launch if not open", verify="two rects", ex=f"put {pair[0].lower()} and {pair[1].lower()} side by side")
    B("Desktop", f"Stacked: {pair[0]} over {pair[1]}", "window_op.arrange", "targets[], layout=stack", "",
      verify="two rects", ex=f"put {pair[0].lower()} on top of {pair[1].lower()}")
for x in ["Launch an app straight into full screen", "Launch an app maximised", "Launch an app on the other monitor",
          "Second window of the same app (ordinal)", "Window whose title contains a word", "List open windows",
          "Quad layout for four windows", "Bring back the window minimised earlier", "Show the desktop",
          "Alt-Tab equivalent (previous window)", "Ask which window when two match equally",
          "Refuse to type when focus moved away", "Resolve 'this window' while JARVIS is in front"]:
    B("Desktop", x, "window_op.*", "target/layout", "foreground history, title match",
      verify="foreground/rect/state read back", ex=x.lower())

# ------------------------------------------------------------------------------------------------ Keyboard / text / dictation
for op in ["delete", "select", "copy", "cut"]:
    for unit in ["character", "word", "line", "sentence", "paragraph"]:
        for n in ("1", "N"):
            B("Keyboard/Text/Dictation", f"{op.title()} the last {n} {unit}(s)", f"text_op.{op}", f"unit={unit}, n",
              "caret position", verify="field value read back (UIA) or chord log", ex=f"{op} the last {'3' if n == 'N' else ''} {unit}".replace("  ", " "))
for x in ["Delete the next word", "Select the current line", "Select everything typed", "Replace X with Y (nearest)",
          "Replace every X with Y", "Uppercase the last word", "Lowercase that", "Capitalise the last word",
          "Make the selection bold", "Italic", "Underline", "Undo N changes", "Redo N changes", "New line", "New paragraph",
          "Press a named key (enter/escape/tab)", "Save the document (Ctrl+S)", "Find in document (Ctrl+F)",
          "Insert typed text into the focused field"]:
    B("Keyboard/Text/Dictation", x, "text_op.*", "op, unit, n, find, replace_with", "focused field",
      verify="field read back when readable", ex=x.lower())
for x in ["Start dictation in the window in front", "Start dictation in a named app", "Stop dictation",
          "Pause dictation", "Resume dictation", "Live typing of stable words while speaking",
          "Hold back a possible command word ('new', 'question')", "Spoken punctuation (comma, full stop, question mark)",
          "Mixed speech: 'new paragraph, add ...'", "Type literally (no command parsing)",
          "Trailing 'stop typing' ends dictation after the words", "Final transcript reconciles revised words",
          "Pause with words kept when focus is lost (TARGET_LOST)", "Code mode symbols", "Spelling mode",
          "Number mode", "Edit command during dictation (delete last word)", "Replace during dictation",
          "Global stop during dictation ('stop typing and open chrome')", "Never type into JARVIS's own window"]:
    B("Keyboard/Text/Dictation", x, "dictate / LiveDictation", "stable prefix, mode", "DictationController target hwnd",
      verify="focus checked before every insertion; typed once per utterance", ex=x.lower())

# ------------------------------------------------------------------------------------------------ UIA / mouse
for role in ["button", "link", "tab", "checkbox", "radio button", "menu item", "list item", "dropdown", "text field",
             "search box", "toggle switch", "icon"]:
    B("UIA/Mouse", f"Click a {role} by name", "ui_op.click", "target=name+role", "UIA/DOM/uiautomator tree",
      verify="pattern result + tree change", ex=f"click the save {role}")
    B("UIA/Mouse", f"Click the Nth {role}", "ui_op.click", "ordinal+role", "document order", verify="tree change",
      ex=f"click the second {role}")
for x in ["Type into a named field", "Type into the Nth field", "Check a checkbox (idempotent)", "Uncheck a checkbox",
          "Toggle a switch", "Control next to a label ('checkbox next to Remember me')", "Read a control's value",
          "Find a control without acting", "Scroll a window", "Scroll N pages", "Scroll to top/bottom",
          "Ask when two controls tie", "Refuse password/OTP/PIN/CVV fields", "Pause for CAPTCHA",
          "Approval before Pay/Delete account/Submit order", "Disabled control reported, not clicked",
          "Vision only as validated fallback (no coordinate clicks)", "Right/double click via the screen tool",
          "Stale snapshot re-resolved", "Control inside the IDE", "Control on a web page", "Control on the phone",
          "Control in a named window", "Ordinal among search results", "Approval re-runs the same prepared call",
          "Report 'can't read controls' instead of guessing", "Typed text read back to verify",
          "Pattern choice: Invoke/Toggle/Select/Expand", "Menu item by path", "Tab item by name",
          "Dialog button (OK/Cancel/Allow) in front", "Send button with verified send", "Combobox option",
          "Hyperlink in a document", "Tree item in Explorer", "Button by automation id", "Fuzzy name (one typo)"]:
    B("UIA/Mouse", x, "ui_op.*", "target, text", "adapter snapshot", "REVERSIBLE" if "Pay" not in x else "EXTERNAL_EFFECT",
      verify="effect observed or honest failure", ex=x.lower())

# ------------------------------------------------------------------------------------------------ Browser
SITES = ["Gmail", "YouTube", "GitHub", "Docs", "Drive", "Calendar", "ChatGPT", "Claude", "LinkedIn", "Reddit",
         "Stack Overflow", "Wikipedia", "Amazon", "Maps", "WhatsApp Web"]
for site in SITES:
    B("Browser", f"Open {site}", "browser_op.open / open_website", "target=site", "site table", verify="tab URL host",
      ex=f"open {site.lower()}")
    B("Browser", f"Switch to the open {site} tab", "browser_op.tab_switch", "which=title word", "tab list",
      verify="active tab title", ex=f"switch to the {site.lower()} tab")
    B("Browser", f"Close the {site} tab", "browser_op.tab_close", "which", "tab list", verify="tab gone",
      ex=f"close the {site.lower()} tab")
for eng in ["Google", "YouTube", "GitHub", "Wikipedia", "Amazon", "Maps", "Images", "News", "Scholar", "Reddit"]:
    B("Browser", f"Search {eng}", "browser_op.search / search_web", "target, engine", "engine table",
      verify="results page open", ex=f"search {eng.lower()} for lofi")
for o in ["first", "second", "third", "fourth", "fifth", "last", "Nth by title"]:
    for kind in ["result", "video", "link"]:
        B("Browser", f"Open the {o} {kind}", "browser_op.open_result", "ordinal|title, new_tab", "page result list",
          verify="tab URL changed to the link", ex=f"open the {o} {kind}")
for x in ["Open result in a new tab", "List open tabs", "Count open tabs", "Next tab", "Previous tab", "Tab by number",
          "Reopen closed tab", "New tab", "Back", "Forward", "Reload", "Hard reload", "Find text on page",
          "Read the page (untrusted)", "List search results", "Scroll the page", "Zoom in/out", "Bookmark page",
          "Open downloads page", "Open history", "Private window", "Fill a field on the page", "Click a page button",
          "Never fill password fields", "Login/CAPTCHA paused for owner", "Attach to owner's Chrome via DevTools",
          "Keyboard fallback when DevTools is off", "Page text never treated as instructions"]:
    B("Browser", x, "browser_op.* / browser_quick_action", "", "tab/page", verify="URL/title/DOM read back", ex=x.lower())

# ------------------------------------------------------------------------------------------------ Media
for x, cap in [("Play", "play"), ("Pause", "pause"), ("Toggle play/pause", "toggle"), ("Seek to a time (1:30)", "seek_to"),
               ("Skip forward N seconds", "seek_by"), ("Rewind N seconds", "seek_by"), ("Skip forward N minutes", "seek_by"),
               ("Jump to the start", "restart"), ("Speed 1.5x", "rate"), ("Speed 2x", "rate"), ("Half speed", "rate"),
               ("Normal speed", "rate"), ("Speed up a step", "rate"), ("Slow down a step", "rate"), ("Mute", "mute"),
               ("Unmute", "unmute"), ("Player volume %", "volume"), ("Captions on/off", "captions"),
               ("Full screen video", "fullscreen"), ("Next video", "next"), ("Previous video", "previous"),
               ("Loop video", "loop"), ("Where am I / time left", "state"), ("Skip a skippable ad now", "skip_ad"),
               ("Media keys for desktop players", "play/pause/next")]:
    B("Media", x, f"video_op.{cap}", "value", "page <video> or media session", verify="player state read back",
      ex=x.lower())
for x in ["Skip ads whenever the Skip button appears (scoped watch)", "Stop skipping ads", "Watch ends when the video changes",
          "Watch time-limited (default 60 min)", "No network ad blocking - visible Skip control only",
          "Control video in a background tab", "Media keys fallback reported as unverified",
          "Spotify/VLC via media keys", "YouTube play by query", "Phone media keys", "Resume the music"]:
    B("Media", x, "watch_op / video_op / media_control", "", "MediaResource", verify="state read back or honest note",
      ex=x.lower())

# ------------------------------------------------------------------------------------------------ Clipboard / screenshot / attachments
for x in ["Screenshot of the whole screen", "Screenshot of the active window", "Screenshot of a named window",
          "Screenshot to clipboard", "Screenshot recorded as 'that screenshot'", "Read the clipboard (typed resource)",
          "Copy the selection (waits for clipboard change)", "Put text on the clipboard", "Restore the previous clipboard",
          "Clipboard image recognised", "Clipboard files recognised"]:
    B("Clipboard/Screenshot/Attachments", x, "screen_op / clipboard_op", "scope, to_clipboard", "ScreenshotResource",
      "READ_ONLY" if "Read" in x else "REVERSIBLE", verify="file exists / clipboard read back", ex=x.lower())
for app in ["Antigravity", "VS Code", "Cursor", "Chrome", "Notepad", "Word", "WhatsApp", "Slack", "Teams", "Paint"]:
    B("Clipboard/Screenshot/Attachments", f"Paste the last screenshot into {app}", "deliver_op (paste)",
      "resource, to", "resource memory", verify="attachment chip / field change, else 'can't confirm'",
      ex=f"paste that screenshot in {app.lower()}")
    B("Clipboard/Screenshot/Attachments", f"Take a screenshot and paste it into {app}",
      "pc_quick_action.screenshot_paste / deliver_op", "capture_first", "new ScreenshotResource",
      verify="file + paste observed", ex=f"take a screenshot and paste it in {app.lower()}")
for x in ["Attach a file into an app (CF_HDROP paste)", "Attach the download into a chat", "Paste copied text into an app",
          "Copy here, paste there", "Upload into a web file input (planner + browser)", "Send = separate approved step",
          "Missing file reported instead of pasting", "Ask which screenshot when none exists", "Phone screenshot to PC app",
          "Screenshot to phone", "Answer text pasted into editor", "Link of current tab pasted", "Clipboard to phone",
          "Paste into a named field (prompt box)", "Focus re-checked right before Ctrl+V", "Verified via attachment chip",
          "Image paste into IDE prompt", "Text paste verified by field read-back", "Refuse when target window lost focus"]:
    B("Clipboard/Screenshot/Attachments", x, "deliver_op / clip", "", "resource memory", verify="observed effect", ex=x.lower())

# ------------------------------------------------------------------------------------------------ Files
for x in ["Find a file by name", "Find by type (pdf, docx)", "Find by time (yesterday, last week)", "Find by folder",
          "Find by content (semantic)", "Open a file", "Open the Nth result", "Open the latest download",
          "Open a known folder", "List a folder", "Create a folder", "Rename a file", "Copy a file", "Move a file",
          "Delete a file (approval, recycle bin)", "Empty recycle bin (approval)", "Organise downloads", "Find duplicates",
          "File metadata", "Document question answering", "Summarise a document", "Open with a specific app",
          "Reveal in Explorer", "Batch rename", "Create shortcut", "Delete shortcut", "Text units are never files",
          "Resolver-made paths checked before delete", "TOCTOU check on destructive ops", "Download recorded as resource",
          "Download watch: tell me when done", "Open file in IDE via Quick Open", "Send file to phone (LocalSend)",
          "Pull latest phone photo", "Search notes", "Knowledge search", "Index new files", "Recent files list",
          "Open containing folder", "Copy path", "Zip a folder (planner)", "Extract audio", "Trim media clip",
          "Find large files (planner)", "Open the screenshot folder", "Rename screenshot", "Move screenshot to folder",
          "Find the report I worked on (action log)", "Open my resume (planner find+open)", "File in another app -> planner"]:
    B("Files", x, "file tools / find_file / open_file", "", "FileCatalog/RAG",
      "DESTRUCTIVE" if "Delete" in x or "Empty" in x else "REVERSIBLE", verify="path exists / absent", ex=x.lower())

# ------------------------------------------------------------------------------------------------ IDE
for ide in ["Antigravity", "VS Code", "Cursor", "Windsurf"]:
    for x, cap in [("Write a prompt (not sent)", "ide_op.prompt"), ("Write and send a prompt", "ide_op.prompt+send"),
                   ("Ask the agent to do X", "ide_op.prompt+send"), ("Send the written prompt", "ide_op.send"),
                   ("Accept the agent's changes", "ide_op.accept"), ("Reject the agent's changes", "ide_op.reject"),
                   ("New agent chat", "ide_op.key.new_chat"), ("Toggle terminal", "ide_op.key.toggle_terminal"),
                   ("Is the agent done?", "ide_op.status"), ("Read the agent's last reply", "ide_op.read"),
                   ("Attach a screenshot to the prompt", "ide_op.attach")]:
        B("IDE", f"{ide}: {x}", cap, "ide, text, send", "IDE window + UIA prompt box",
          verify="prompt read back / box emptied or Stop shown / chip appears", ex=f"{x.lower()} in {ide.lower()}")
for x in ["Open a file via Quick Open (title verified)", "Run a palette command (destructive ones refused)",
          "Tell me when the agent finishes (watch)", "Toggle sidebar", "Find in files", "Format document",
          "Go to line", "Split editor", "Save all", "Never claim success without seeing it"]:
    B("IDE", x, "ide_op.* / watch_op.ide_done", "", "IDE window", verify="title/UI observed", ex=x.lower())

# ------------------------------------------------------------------------------------------------ Android
PAPPS = ["WhatsApp", "YouTube", "Chrome", "Gmail", "Maps", "Camera", "Settings", "Spotify", "Instagram", "Photos",
         "Telegram", "Calendar", "Clock", "Files", "Play Store"]
for a in PAPPS:
    B("Android", f"Open {a} on the phone", "android_open_app / phone_op.open_app", "app", "package table",
      verify="monkey result", ex=f"open {a.lower()} on my phone")
    B("Android", f"Close {a} on the phone", "phone_op.close_app", "app", "package table", verify="force-stop sent",
      ex=f"close {a.lower()} on my phone")
for k in ["back", "home", "recents", "enter", "volume up", "volume down", "mute", "play/pause", "next", "previous",
          "wake", "lock", "notifications shade", "quick settings", "screenshot key", "camera key"]:
    B("Android", f"Phone key: {k}", "phone_op.key / android_key", "key", "fixed keycode table",
      verify="keyevent sent (works locked only for media/volume/wake/lock)", ex=f"press {k} on my phone")
for x in ["Tap a control by its text", "Tap the Nth item", "Type into a named field", "Scroll down/up", "Scroll to top",
          "Read notifications (untrusted)", "Battery level", "Is it charging", "Phone screenshot -> resource",
          "Push a file to Downloads (verified with ls)", "Pull latest photo", "Open a URL on the phone",
          "Wi-Fi/Bluetooth/flashlight/DND quick toggles", "Dial a contact", "Mirror the screen (scrcpy)", "Stop mirroring",
          "Connect over Wi-Fi ADB", "Device status", "Logcat (bounded, read-only)", "List user apps",
          "Install a local APK (approval)", "Uninstall an app (approval)", "Clear app data (approval)", "Storage",
          "Device info", "Locked phone: pause for owner, never enter PIN", "Unauthorized device refused",
          "Allow-listed serials only", "Password field on phone refused", "Typed text escaped for ADB (no shell)",
          "CAPTCHA on phone paused", "Consequential phone button needs approval", "Phone media keys from PC",
          "Phone volume from PC"]:
    B("Android", x, "phone_op.* / android_*", "", "uiautomator tree / dumpsys", verify="adb read back", ex=x.lower())

# ------------------------------------------------------------------------------------------------ Cross-device
for x in ["Send the last screenshot to the phone", "Take a screenshot and send it to the phone", "Send a file to the phone",
          "Send a link to the phone", "Send copied text to the phone", "Pull the newest phone photo to the PC",
          "Pull the latest phone screenshot", "Paste a phone screenshot into a PC app", "Open the current page on the phone",
          "Mirror and control the phone from the PC", "Read phone notifications on the PC", "Phone battery on the PC",
          "Pause phone music from the PC", "Phone volume from the PC", "Transfer the download to the phone",
          "Share a file with the phone (LocalSend)", "Phone photo into WhatsApp desktop", "Phone screenshot into the IDE",
          "PC clipboard to phone clipboard (LocalSend text)", "Phone notification -> summary on PC",
          "Open a phone app from the PC", "Tap on the phone from the PC", "Type on the phone from the PC",
          "Phone screenshot recorded as resource", "Phone file pushed is verified", "Locked phone stops the flow",
          "Unauthorized phone refused", "Wi-Fi ADB reconnect", "Device picker when two phones", "Phone URL validated"]:
    B("Cross-device", x, "deliver_op.to_phone / localsend / android_*", "", "resources + device", verify="receiver/adb check",
      ex=x.lower())

# ------------------------------------------------------------------------------------------------ System
for x in ["Volume up/down/set", "Mute/unmute", "Brightness set", "Wi-Fi status", "Network info", "Bluetooth settings",
          "Display settings", "Sound settings", "Windows Update settings ('check for updates')", "Battery status",
          "System diagnostics", "Free RAM", "Lock the PC", "Sleep (approval)", "Restart (approval)", "Shut down (approval)",
          "Show desktop", "Task Manager", "Run dialog", "Snipping tool", "Clipboard history", "Emoji panel",
          "Virtual desktops", "Notification centre", "Quick settings", "Microphone status", "Installed apps list",
          "Install software (approval)", "Uninstall software (approval)", "Update software", "Where is an app installed",
          "Night light", "Focus session", "Time", "Never bypass UAC - pause for the owner"]:
    B("System", x, "system tools", "", "", "PRIVILEGED" if any(k in x for k in ("Sleep", "Restart", "Shut", "Install",
                                                                             "Uninstall")) else "REVERSIBLE",
      verify="state read back", ex=x.lower())

# ------------------------------------------------------------------------------------------------ Workflow
for x in ["Go back to editor, then edit text", "Switch to Chrome, open result N", "Open video N, then skip ads when possible",
          "Paste screenshot in IDE and send (approval)", "Maximise Chrome and open a tab", "Go back to Notepad and replace text",
          "Screenshot -> IDE -> ask agent to fix", "Open YouTube, search, play result 1", "Switch to Gmail tab, read latest",
          "Skip forward, then captions on", "Open result in new tab, then find text", "Find a file, attach it in WhatsApp",
          "Copy the error, paste it in the IDE", "Minimise Spotify, return to VS Code", "Close a tab, switch to Docs",
          "Open app and type", "Open app full screen and navigate", "Side-by-side then focus one",
          "Download, then open when done", "Tell me when download finishes", "Tell me when IDE agent is done",
          "Dictate into a named app", "Screenshot this window and send to phone", "Search and open first result",
          "Copy here, paste into Notepad", "Open settings and toggle Bluetooth", "Mute video and captions on",
          "Find report and send to phone", "Open my editor and delete the last line", "Stop skipping ads",
          "Cancel all watches", "List watches", "Every step verified before the next", "Deterministic steps run without a model",
          "Mixed steps go to the planner with operator tools", "Corrections ('no wait') never split into steps",
          "Message words never split into steps", "Negated workflow runs nothing", "Standing rule: approve first applies",
          "One command id -> one final response"]:
    B("Workflow", x, "compound / planner over operator tools", "", "", verify="per-step verification", ex=x.lower())


def main() -> None:
    fams = Counter(r[0] for r in ROWS)
    out = ["# Universal Operator - Capability Catalog", "",
           f"**{len(ROWS)} behaviors**, generated by `scripts/gen_operator_catalog.py` from the primitive families in "
           "`jarvis/core/operator`. Each behavior is a composition of typed primitives (window, ui, text, dictate, clip, "
           "screen, deliver, browser, media, watch, ide, device) - not a handler of its own. Wording is resolved by the "
           "operator parser (`jarvis/core/router/operator_intents.py`) and the existing router; execution always goes "
           "through schema validation, policy, a registered tool and a verifier.", "",
           "| Family | Behaviors | Minimum |", "|---|---:|---:|"]
    mins = {"Desktop": 70, "Keyboard/Text/Dictation": 70, "UIA/Mouse": 60, "Browser": 90, "Media": 35,
            "Clipboard/Screenshot/Attachments": 40, "Files": 50, "IDE": 45, "Android": 80, "Cross-device": 30,
            "System": 35, "Workflow": 40}
    for f, m in mins.items():
        out.append(f"| {f} | {fams.get(f, 0)} | {m} |")
    out += ["", "Columns: capability (tool.action), slots, references used, risk, verification, example wording.", ""]
    for fam in mins:
        out += [f"## {fam}", "", "| # | Behavior | Capability | Slots | Refs | Risk | Verification | Example |",
                "|---:|---|---|---|---|---|---|---|"]
        i = 0
        for r in ROWS:
            if r[0] == fam:
                i += 1
                out.append(f"| {i} | " + " | ".join(c.replace("|", "/") for c in r[1:]) + " |")
        out.append("")
    path = Path(__file__).resolve().parents[1] / "docs" / "UNIVERSAL_OPERATOR_CAPABILITY_CATALOG.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print(len(ROWS), dict(fams))
    short = {f: (fams.get(f, 0), m) for f, m in mins.items() if fams.get(f, 0) < m}
    if short:
        raise SystemExit(f"below minimum: {short}")


if __name__ == "__main__":
    main()
