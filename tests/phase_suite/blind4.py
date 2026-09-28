"""BLIND-4: the final held-out check, written after all blind-3 fixes and scored once for the report (never tuned on).

New phrasings and new names/apps/files for every phase. Same expectation codes as ``cases.py``.
"""
from __future__ import annotations

from tests.phase_suite.blind2 import build_split
from tests.phase_suite.cases import TIERS, T

E, M, H, V = TIERS

POOLS = {
    "app": ["tableau", "anki", "notepad plus plus", "vmware", "rufus", "qbittorrent", "sharex", "greenshot", "wireshark", "cursor"],
    "p": ["bala", "revathi", "sathish", "janani", "murali", "pooja", "chithi", "mama"],
    "n": ["7", "16", "28", "39", "51", "69", "83", "96"],
    "msg": ["reached the station", "bring some snacks", "meeting starts at 10", "i'll call you tonight", "the wifi is down",
            "happy anniversary"],
    "file": ["insurance policy", "rent receipt", "degree certificate", "tax form", "bank passbook"],
    "fname": ["summary.txt", "invoice_march.pdf", "slides_v2.pptx", "profile.png", "budget.xlsx"],
    "folder": ["downloads", "documents", "pictures", "videos"],
    "site": ["quora.com", "kaggle.com", "bookmyshow.com", "dev.to", "imdb.com"],
    "q": ["standing desk", "hdmi cable", "green tea", "graphics tablet", "phone tripod"],
    "song": ["melody songs", "a r rahman bgm", "arijit singh", "chill beats", "old hindi songs"],
    "city": ["tirunelveli", "mysore", "kanyakumari", "shimla"],
    "topic": ["overtime policy", "exam results", "hostel fees", "bonus dates"],
}

PHASES4: dict[str, list[T]] = {
    "p01_core_os": [
        T(E, "open up {app}", "open_app", {"name": "{app}"}),
        T(E, "exit out of {app}", "close_app"),
        T(E, "make it quieter", "volume_down"),
        T(E, "volume to {n} percent", "volume_set", {"percent": "{n}"}),
        T(E, "take a screen capture", "take_screenshot"),
        T(M, "could you bump the volume up", "volume_up"),
        T(M, "turn the sound off", "volume_mute|mute"),
        T(M, "bring the brightness down to {n}", "brightness_set", {"percent": "{n}"}),
        T(M, "is the charger plugged in", "battery_status"),
        T(M, "open the videos folder", "open_known_folder"),
        T(H, "my ears hurt, it's way too loud", "volume_down"),
        T(H, "kill {app}", "close_app"),
        T(V, "i'm heading out, lock the pc", "system_power_control|lock_pc"),
    ],
    "p02_router": [
        T(E, "what does {app} do exactly", "CHAT"),
        T(M, "how do i uninstall {app}", "CHAT"),
        T(M, "tell me about the history of {city}", "CHAT|search_web"),
        T(M, "is it bad to keep my laptop plugged in", "CHAT"),
        T(H, "why does {app} keep crashing", "CHAT"),
        T(H, "i'd like to open {app}", "open_app"),
        T(V, "which is lighter, {app} or {app2}", "CHAT"),
    ],
    "p03_files": [
        T(E, "find my {file} file", "find_file"),
        T(M, "open the file {fname}", "open_file|find_file"),
        T(M, "copy {fname} into downloads", "copy_file"),
        T(M, "move {fname} over to the desktop", "move_file"),
        T(M, "rename {fname} to old version", "rename_file"),
        T(M, "make a folder called {topic}", "create_folder"),
        T(H, "where did i keep my {file}", "find_file"),
        T(H, "clean up the downloads folder", "organize_downloads"),
        T(V, "i can't find my {file} anywhere", "find_file"),
    ],
    "p04_multistep": [
        T(E, "open {app} and mute", "MULTI"),
        T(M, "take a screenshot and open {app}", "MULTI"),
        T(H, "close {app} then lock the computer", "MULTI"),
        T(V, "open {site}, then set brightness to {n} and mute", "MULTI"),
    ],
    "p05_safety": [
        T(E, "don't close {app} please", "REJECT"),
        T(M, "never delete {fname}", "REJECT"),
    ],
    "p06_voice_input": [
        T(E, "jarvis launch {app}", "open_app"),
        T(M, "okay jarvis, set volume {n}", "volume_set"),
        T(H, "uh so like open {app}", "open_app"),
        T(H, "Jarvis? Open {App}!", "open_app"),
        T(V, "hmm jarvis uh mute", "volume_mute|mute"),
        T(M, "is the mic working", "microphone_status"),
        T(M, "stop voice typing", "dictation_mode_control"),
    ],
    "p07_voice_output": [
        T(E, "stop speaking now", "CONTROL:stop_speaking"),
        T(M, "can you talk in a lady's voice", "set_voice"),
        T(M, "say it again please", "recent_actions"),
        T(M, "speak to me in english", "set_reply_language"),
        T(H, "okay stop reading", "CONTROL:stop_speaking"),
    ],
    "p08_history": [
        T(E, "what have you done just now", "recent_actions"),
        T(M, "what commands did i give you today", "command_history"),
        T(H, "did my text to {p} go", "recent_actions"),
        T(H, "was the message delivered to {p}", "recent_actions"),
        T(V, "wait who did you text just now", "recent_actions"),
    ],
    "p09_google": [
        T(E, "any new mail", "gmail_list_recent"),
        T(M, "show me emails from {p}", "gmail_list_recent"),
        T(M, "what meetings do i have on friday", "calendar_list_events"),
        T(M, "am i free tomorrow morning", "calendar_list_events"),
        T(H, "schedule a review with {p} tomorrow at 2 pm", "calendar_create_event+clarify"),
        T(H, "write an email to {p} about {topic}", "gmail_create_draft+clarify"),
    ],
    "p10_browser": [
        T(E, "go to {site} please", "open_website"),
        T(E, "close tab", "browser_quick_action"),
        T(M, "look up {q} online", "open_website|search_web"),
        T(M, "play {song} on youtube for me", "play_youtube"),
        T(M, "refresh this page", "browser_quick_action"),
        T(H, "check amazon for a {q}", "open_website|web_task"),
        T(M, "any news about {city} today", "search_news|search_web"),
    ],
    "p11_vision": [
        T(E, "what's on the screen", "describe_screen"),
        T(M, "click the {app} button", "screen_click"),
        T(H, "what does this message on the screen say", "describe_screen"),
        T(H, "double click on {app}", "screen_click"),
    ],
    "p12_intelligence": [
        T(E, "remind me to call {p} at 7", "set_reminder"),
        T(E, "add {q} to my todo list", "todo"),
        T(M, "remember that the spare key is in the drawer", "remember_fact"),
        T(M, "set a timer for 15 minutes", "set_reminder"),
        T(M, "list all my reminders", "list_reminders"),
        T(M, "generate a secure password", "generate_password"),
        T(H, "what's on my to do list today", "todo"),
    ],
    "x_whatsapp": [
        T(E, "message {p} that {msg}", "send_whatsapp_message", {"recipient": "{p}"}),
        T(M, "send {p} a text saying {msg}", "send_whatsapp_message", {"recipient": "{p}"}),
        T(M, "let {p} know that {msg}", "send_whatsapp_message", {"recipient": "{p}"}),
        T(M, "check my whatsapp messages", "read_whatsapp_messages"),
        T(H, "what did {p} message me", "read_whatsapp_messages", {"sender": "{p}"}),
        T(H, "how many unread whatsapp messages", "read_whatsapp_messages"),
        T(V, "drop {p} a quick text that {msg}", "send_whatsapp_message"),
    ],
    "x_phone": [
        T(E, "my phone's battery", "android_status"),
        T(M, "turn on wifi on my mobile", "android_toggle"),
        T(M, "open youtube on my phone", "android_open_app"),
        T(M, "show notifications from my phone", "android_notifications"),
        T(H, "transfer {fname} to my phone", "android_push_file|localsend_file"),
    ],
    "x_automation": [
        T(E, "install {app} please", "install_software"),
        T(M, "remove {app} from this pc", "uninstall_software+clarify"),
        T(M, "upgrade {app}", "update_software"),
        T(M, "is {app} installed on this pc", "check_app_installed"),
        T(M, "organise my downloads", "organize_downloads"),
        T(M, "start a study session for 30 minutes", "start_study_focus"),
    ],
    "x_thanglish": [
        T(E, "{app} open pannu da", "open_app"),
        T(M, "volume {n} ku vechidu", "volume_set"),
        T(M, "sound kammi pannu da", "volume_down"),
        T(H, "{p} ku {msg} nu anuppu da", "send_whatsapp_message"),
        T(M, "{app} ah moodu da", "close_app"),
    ],
    "x_chat": [
        T(E, "thanks a lot", "CHAT"),
        T(E, "good evening", "CHAT"),
        T(M, "tell me something funny", "CHAT"),
        T(M, "what is quantum computing", "CHAT"),
        T(H, "i feel lonely today", "CHAT"),
        T(M, "what's your favourite movie", "CHAT"),
    ],
}


def build4() -> list[dict]:
    return build_split(PHASES4, POOLS, "blind4")
