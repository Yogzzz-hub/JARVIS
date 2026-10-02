"""Context-2: unseen multi-turn conversations, written and frozen before the generalisation work they measure.

Each template is a conversation; {slots} are filled from POOLS (2 fills). The follow-up turns are also said in other
surface forms (wake word, filler, courtesy, typo). Templates are split by hash into dev / holdout: fixes may use only
the dev failures; the holdout is the unseen number.

Expectation per turn:
- "tool" or ("tool|alt", {arg: value})   the tool reached (run, or waiting for confirmation), args by substring
- "CLARIFY"                              no tool runs
- "NOT:tool|tool"                        none of these tools is reached (an unsafe follow-up is never resolved)
"""
from __future__ import annotations

POOLS = {
    "a1": ["notepad", "calculator", "paint", "word", "excel", "spotify", "vlc", "teams"],
    "a2": ["outlook", "discord", "zoom", "edge", "firefox", "telegram", "obs studio", "file explorer"],
    "n": ["15", "25", "35", "45", "65", "75", "85"],
    "n2": ["10", "20", "50", "55", "70", "80", "90"],
    "p": ["kavya", "suresh", "divya", "rahul", "amma", "appa"],
    "p2": ["nithya", "karthik", "meera", "vinoth"],
    "msg": ["i'll be late", "call me back", "dinner at 8", "reached safely", "on the way"],
    "q": ["python decorators", "best phones under 20000", "how to bake bread", "tamil movies 2024"],
    "q2": ["java streams", "best earphones", "how to make pasta", "hindi movies 2024"],
    "c": ["chennai", "madurai", "salem", "vellore"],
    "c2": ["pune", "kochi", "mysore", "goa"],
    "song": ["lofi beats", "ar rahman hits", "jazz piano", "workout music"],
    "f": ["invoice.pdf", "notes.txt", "budget.xlsx", "photo.png"],
    "t": ["5 pm", "7 pm", "9 am", "11 am"],
    "t2": ["6 pm", "8 pm", "10 am", "noon"],
    "task": ["call the bank", "pay rent", "take medicine", "water the plants"],
}

OPEN1 = ("open {a1}", ("open_app", {"name": "{a1}"}))
OPEN2 = ("open {a2}", ("open_app", {"name": "{a2}"}))
VOL = ("set volume to {n}", ("volume_set", {"percent": "{n}"}))
BRI = ("set brightness to {n}", ("brightness_set", {}))
SEND = ("send {p} {msg}", ("send_whatsapp_message", {"recipient": "{p}"}))
SEARCH = ("search for {q}", ("search_web", {"query": "{q}"}))
WEATHER = ("what's the weather in {c}", "ollama_chat|search_web|quick_answer")
REMIND = ("remind me to {task} at {t}", "set_reminder")
YT = ("open youtube", "open_website|open_app")
FIND = ("find {f}", ("find_file", {}))
PLAY = ("play {song}", "play_youtube|media_control")

V_NUM = ("volume_set", {"percent": "{n2}"})
OPEN_A2 = ("open_app", {"name": "{a2}"})
CLOSE_A1 = ("close_app", {"name": "{a1}"})
UNSAFE = "NOT:delete_file|uninstall_software|send_whatsapp_message|share_file|android_push_file"

CONVERSATIONS: list[list[tuple[str, object]]] = [
    # ---- a new number for the setting just changed
    [VOL, ("make it {n2}", V_NUM)],
    [VOL, ("change it to {n2}", V_NUM)],
    [VOL, ("set it to {n2}", V_NUM)],
    [VOL, ("no, {n2}", V_NUM)],
    [VOL, ("actually make that {n2}", V_NUM)],
    [VOL, ("can you make it {n2} instead", V_NUM)],
    [VOL, ("hmm, {n2} percent", V_NUM)],
    [VOL, ("put it at {n2}", V_NUM)],
    [VOL, ("i said {n2}", V_NUM)],
    [VOL, ("too loud", "volume_down|volume_set")],
    [VOL, ("a little more", "volume_up|volume_set")],
    [VOL, ("turn it down a bit", "volume_down|volume_set")],
    [VOL, ("bit higher", "volume_up|volume_set")],
    [VOL, ("lower", "volume_down|volume_set")],
    [BRI, ("make it {n2}", ("brightness_set", {"percent": "{n2}"}))],
    [BRI, ("a bit brighter", "brightness_set|brightness_up")],
    [BRI, ("too bright", "brightness_set|brightness_down")],
    [REMIND, ("make it {t2}", ("set_reminder", {"text": "{t2}"}))],
    [REMIND, ("actually at {t2}", ("set_reminder", {"text": "{t2}"}))],
    [REMIND, ("change the time to {t2}", ("set_reminder", {"text": "{t2}"}))],
    # ---- the same action, a new target
    [OPEN1, ("same for {a2}", OPEN_A2)],
    [OPEN1, ("do that for {a2} too", OPEN_A2)],
    [OPEN1, ("{a2} too", OPEN_A2)],
    [OPEN1, ("and {a2}", OPEN_A2)],
    [OPEN1, ("{a2} as well", OPEN_A2)],
    [OPEN1, ("also {a2}", OPEN_A2)],
    [OPEN1, ("now {a2}", OPEN_A2)],
    [OPEN1, ("now do {a2}", OPEN_A2)],
    [OPEN1, ("repeat that for {a2}", OPEN_A2)],
    [OPEN1, ("and then {a2}", OPEN_A2)],
    [("close {a1}", CLOSE_A1), ("same with {a2}", ("close_app", {"name": "{a2}"}))],
    [("close {a1}", CLOSE_A1), ("{a2} too", ("close_app", {"name": "{a2}"}))],
    [SEARCH, ("now {q2}", ("search_web", {"query": "{q2}"}))],
    [SEARCH, ("what about {q2}", ("search_web", {"query": "{q2}"}))],
    [SEARCH, ("try {q2}", ("search_web", {"query": "{q2}"}))],
    [SEARCH, ("search {q2} instead", ("search_web", {"query": "{q2}"}))],
    [WEATHER, ("and in {c2}?", ("ollama_chat|search_web|quick_answer", {"query": "{c2}"}))],
    [WEATHER, ("what about {c2}", ("ollama_chat|search_web|quick_answer", {"query": "{c2}"}))],
    [WEATHER, ("how about in {c2}", ("ollama_chat|search_web|quick_answer", {"query": "{c2}"}))],
    [SEND, ("also to {p2}", ("send_whatsapp_message", {"recipient": "{p2}", "message": "{msg}"}))],
    [SEND, ("send the same to {p2}", ("send_whatsapp_message", {"recipient": "{p2}", "message": "{msg}"}))],
    [SEND, ("and {p2} too", ("send_whatsapp_message", {"recipient": "{p2}", "message": "{msg}"}))],
    [SEND, ("same message to {p2}", ("send_whatsapp_message", {"recipient": "{p2}", "message": "{msg}"}))],
    # ---- corrections after an action
    [OPEN1, ("no, {a2}", OPEN_A2)],
    [OPEN1, ("i meant {a2}", OPEN_A2)],
    [OPEN1, ("sorry, {a2}", OPEN_A2)],
    [OPEN1, ("not {a1}, {a2}", OPEN_A2)],
    [OPEN1, ("wrong one, i said {a2}", OPEN_A2)],
    [OPEN1, ("oops i meant {a2}", OPEN_A2)],
    [OPEN1, ("no no, open {a2}", OPEN_A2)],
    [SEND, ("no, send it to {p2}", ("send_whatsapp_message", {"recipient": "{p2}"}))],
    # ---- pronouns for the app just opened
    [OPEN1, ("close it", CLOSE_A1)],
    [OPEN1, ("shut it", CLOSE_A1)],
    [OPEN1, ("close that", CLOSE_A1)],
    [OPEN1, ("quit it", CLOSE_A1)],
    [OPEN1, ("kill it", CLOSE_A1)],
    [OPEN1, ("close this app", CLOSE_A1)],
    [OPEN1, ("ok close it now", CLOSE_A1)],
    [OPEN1, ("minimize it", "minimize_window|window_op")],
    [OPEN1, ("maximise it", "maximize_window|window_op")],
    [OPEN1, ("make it full screen", "maximize_window|window_op|keyboard_shortcut")],
    [OPEN1, ("restart it", "system_op|restart_app")],
    [OPEN1, ("hide it", "minimize_window|window_op")],
    [OPEN1, ("snap it to the left", "window_op|arrange_windows|snap_window")],
    [YT, ("play {song} on it", ("play_youtube", {"query": "{song}"}))],
    [YT, ("search {q} there", ("open_website|search_web|play_youtube", {}))],
    [FIND, ("open it", ("open_file|find_file", {}))],
    [FIND, ("open that file", ("open_file|find_file", {}))],
    [PLAY, ("pause it", "media_control|video_op")],
    [PLAY, ("skip this one", "media_control|video_op")],
    [PLAY, ("louder", "volume_up|volume_set|speech_control")],
    # ---- ordinals over the apps opened
    [OPEN1, OPEN2, ("close the first one", CLOSE_A1)],
    [OPEN1, OPEN2, ("close the second one", ("close_app", {"name": "{a2}"}))],
    [OPEN1, OPEN2, ("close the last one", ("close_app", {"name": "{a2}"}))],
    [OPEN1, OPEN2, ("close both", "close_app")],
    [OPEN1, OPEN2, ("close them both", "close_app")],
    [OPEN1, OPEN2, ("close all of them", "close_app")],
    [OPEN1, OPEN2, ("minimize the first one", "minimize_window|window_op")],
    [OPEN1, OPEN2, ("switch to the first one", "switch_window|window_op|focus_app")],
    [OPEN1, OPEN2, ("close the other one", CLOSE_A1)],
    # ---- context must not leak into a complete, unrelated command
    [OPEN1, ("what time is it", "get_time")],
    [OPEN1, ("set volume to {n2}", V_NUM)],
    [VOL, ("open {a2}", OPEN_A2)],
    [SEARCH, ("open {a1}", ("open_app", {"name": "{a1}"}))],
    [SEND, ("what's the weather in {c}", "ollama_chat|search_web|quick_answer")],
    [OPEN1, ("take a screenshot", "take_screenshot|screen_op")],
    # ---- unsafe follow-ups are never resolved from context
    [OPEN1, ("delete it", UNSAFE)],
    [OPEN1, ("uninstall it", UNSAFE)],
    [FIND, ("delete that", "NOT:uninstall_software|send_whatsapp_message")],
    [OPEN1, ("send it to {p}", UNSAFE)],
    [OPEN1, ("no, don't", "NOT:open_app")],
    [OPEN1, ("thanks", "NOT:open_app|close_app")],
]
