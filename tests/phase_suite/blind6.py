"""BLIND-6: long spoken rambles and mixed Thanglish + English, written after the blind-5 fixes and scored once
before fixing. Same expectation codes as ``cases.py``.
"""
from __future__ import annotations

from tests.phase_suite.blind2 import build_split
from tests.phase_suite.cases import TIERS, T

E, M, H, V = TIERS

POOLS = {
    "app": ["spotify", "chrome", "notepad", "vs code", "excel", "whatsapp", "telegram", "vlc", "calculator", "word"],
    "p": ["kumar", "shalini", "arjun", "amma", "appa", "priya", "thambi", "anna"],
    "n": ["10", "20", "35", "40", "55", "60", "75", "80"],
    "msg": ["i'll be late", "reached home", "call me back", "dinner is ready", "coming in 10 minutes", "sorry i missed your call"],
    "file": ["resume", "fee receipt", "project report", "id card", "bank statement"],
    "fname": ["notes.txt", "resume.pdf", "photo.jpg", "sheet.xlsx", "slides.pptx"],
    "site": ["youtube.com", "gmail.com", "github.com", "amazon.in", "wikipedia.org"],
    "q": ["wireless mouse", "phone cover", "study table", "headphones", "power bank"],
    "song": ["anirudh songs", "lofi music", "a r rahman hits", "sid sriram songs", "melody songs"],
    "city": ["chennai", "coimbatore", "madurai", "trichy"],
    "topic": ["exam date", "fee deadline", "leave rules", "project deadline"],
    "folder": ["downloads", "documents", "pictures", "videos"],
}

PHASES6: dict[str, list[T]] = {
    "p01_core_os": [
        T(H, "okay so basically i was thinking, could you maybe open {app} or something", "open_app"),
        T(H, "uh yeah so i need the volume at like {n}", "volume_set", {"percent": "{n}"}),
        T(V, "hmm what was i going to say, oh yeah, take a screenshot", "take_screenshot"),
        T(H, "so um the sound is kind of too loud right now, can you bring it down a little", "volume_down"),
        T(V, "alright i think i'm done with {app} for now, you can close it", "close_app"),
        T(M, "bro konjam {app} open pannu please", "open_app"),
        T(M, "volume {n} ku set pannu da", "volume_set"),
        T(H, "screen romba bright ah iruku, konjam kammi pannu", "brightness_set"),
        T(M, "{app} close pannu bro", "close_app"),
        T(H, "da pc ah lock pannu, i'm going out", "system_power_control|lock_pc"),
    ],
    "p02_router": [
        T(H, "so i was just wondering, like, what exactly does {app} do", "CHAT"),
        T(M, "{app} na enna bro", "CHAT"),
        T(H, "okay random question, why is the sky blue", "CHAT"),
        T(M, "machine learning na enna", "CHAT"),
    ],
    "p03_files": [
        T(H, "um so i had this {file} somewhere, can you help me find it", "find_file"),
        T(V, "i remember saving {fname} somewhere but i don't know where, can you open it", "open_file|find_file"),
        T(M, "en {file} enga iruku nu thedu", "find_file"),
        T(M, "downloads folder ah organize pannu", "organize_downloads"),
    ],
    "p04_multistep": [
        T(V, "okay so first open {app}, and then after that, can you mute the volume", "MULTI"),
        T(H, "{app} open pannitu volume {n} ku vai", "MULTI"),
    ],
    "p06_voice_input": [
        T(H, "jarvis jarvis are you listening, okay, open {app}", "open_app"),
        T(V, "hey um jarvis so like can you uh set the volume to {n} please thanks", "volume_set"),
        T(M, "jarvis {app} thora", "open_app"),
    ],
    "p07_voice_output": [
        T(H, "okay okay that's enough, you can stop talking now", "CONTROL:stop_speaking"),
        T(M, "pesadha, stop", "CONTROL:stop_speaking|CONTROL:cancel_task"),
        T(M, "thanglish la pesu da", "set_reply_language"),
    ],
    "p08_history": [
        T(H, "wait so what did you actually do just now", "recent_actions"),
        T(M, "message anupchaa", "recent_actions"),
    ],
    "p09_google": [
        T(H, "so do i have any meetings or anything tomorrow", "calendar_list_events"),
        T(M, "inniku calendar la enna iruku", "calendar_list_events"),
    ],
    "p10_browser": [
        T(H, "can you like search google for {q}, i want to buy one", "open_website|search_web"),
        T(M, "youtube la {song} podu bro", "play_youtube"),
        T(M, "google la {q} thedu", "open_website|search_web"),
        T(V, "i'm bored, just play some {song} on youtube", "play_youtube"),
    ],
    "p11_vision": [
        T(H, "hmm what's this thing on my screen, can you tell me", "describe_screen"),
        T(M, "screen la enna iruku", "describe_screen"),
    ],
    "p12_intelligence": [
        T(H, "oh and remind me to call {p} at 6, i keep forgetting", "set_reminder"),
        T(M, "{p} ku call pannanum nu 5 manikku remind pannu", "set_reminder"),
        T(H, "so like add {q} to my shopping list, i need to buy it", "todo"),
    ],
    "x_whatsapp": [
        T(H, "okay so can you tell {p} that {msg}", "send_whatsapp_message", {"recipient": "{p}"}),
        T(M, "{p} ku {msg} nu message pannu", "send_whatsapp_message"),
        T(V, "hey so um message {p} and say {msg}, thanks", "send_whatsapp_message"),
        T(M, "whatsapp la yaar message pannirukka", "summarize_whatsapp_messages|read_whatsapp_messages"),
        T(M, "{p} enna message pannirukanga", "read_whatsapp_messages"),
    ],
    "x_phone": [
        T(H, "my phone's battery is probably dying, how much is left on it", "android_status"),
        T(M, "phone la wifi on pannu", "android_toggle"),
    ],
    "x_automation": [
        T(H, "i need {app} for college, can you install it", "install_software"),
        T(M, "{app} install pannu", "install_software"),
    ],
    "x_chat": [
        T(M, "romba bore adikudhu", "CHAT"),
        T(H, "honestly today was a long day, i'm just exhausted", "CHAT"),
        T(M, "thanks da jarvis", "CHAT"),
    ],
}


def build6() -> list[dict]:
    return build_split(PHASES6, POOLS, "blind6")
