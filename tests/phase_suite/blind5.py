"""BLIND-5: fifth held-out set in a more conversational style (context before the command, longer sentences),
written after the blind-4 fixes and scored once before fixing. Same expectation codes as ``cases.py``.
"""
from __future__ import annotations

from tests.phase_suite.blind2 import build_split
from tests.phase_suite.cases import TIERS, T

E, M, H, V = TIERS

POOLS = {
    "app": ["audacity", "vlc", "brave", "discord", "notion", "gimp", "steam", "spotify", "telegram", "zoom"],
    "p": ["senthil", "nandhini", "gokul", "divyaa", "ramesh", "periyamma", "anni", "machan"],
    "n": ["9", "14", "26", "37", "44", "58", "73", "92"],
    "msg": ["i'm on the way home", "don't forget the keys", "the exam got postponed", "call amma once", "pay the eb bill",
            "i reached safely"],
    "file": ["water bill", "medical prescription", "offer letter pdf", "semester marksheet", "voter id scan"],
    "fname": ["notes_final.docx", "photo_001.jpg", "timetable.pdf", "data.csv", "recording.mp3"],
    "folder": ["downloads", "documents", "pictures", "videos"],
    "site": ["geeksforgeeks.org", "w3schools.com", "espncricinfo.com", "zerodha.com", "udemy.com"],
    "q": ["bluetooth earbuds", "study lamp", "laptop cooling pad", "yoga block", "usb webcam"],
    "song": ["ilayaraja melodies", "coke studio", "lofi for studying", "vijay antony songs", "rain music"],
    "city": ["erode", "thanjavur", "pondicherry", "munnar"],
    "topic": ["leave encashment", "lab timings", "semester fees", "internship rules"],
}

PHASES5: dict[str, list[T]] = {
    "p01_core_os": [
        T(E, "fire {app} up", "open_app"),
        T(E, "shut {app}", "close_app"),
        T(E, "turn it down a bit", "volume_down"),
        T(M, "i need the volume at {n} percent", "volume_set", {"percent": "{n}"}),
        T(M, "can you make the screen a little dimmer", "brightness_set"),
        T(M, "my battery is dying, how much is left", "battery_status"),
        T(H, "i'm going to sleep, put the computer to sleep", "system_power_control"),
        T(H, "someone's coming, quickly minimize everything", "show_desktop"),
        T(H, "it's too quiet in here, turn up the sound", "volume_up"),
        T(V, "the music is killing my ears, lower it", "volume_down"),
        T(V, "i'm done for today, shut down the laptop", "system_power_control"),
    ],
    "p02_router": [
        T(E, "what can you do", "CHAT"),
        T(M, "is {app} a good app for beginners", "CHAT"),
        T(M, "how does {app} compare to {app2}", "CHAT"),
        T(H, "i'm curious, what does {app} actually do", "CHAT"),
        T(H, "i need {app} open for my class", "open_app"),
        T(V, "before i forget, open {app}", "open_app"),
    ],
    "p03_files": [
        T(E, "search my pc for {file}", "find_file"),
        T(M, "i think i downloaded my {file} last week, where is it", "find_file"),
        T(M, "put {fname} in the documents folder", "move_file"),
        T(M, "make a copy of {fname} on the desktop", "copy_file"),
        T(H, "my downloads folder is a mess, organize it", "organize_downloads"),
        T(H, "change {fname}'s name to backup", "rename_file"),
        T(V, "i need a new folder for {topic}, call it {topic}", "create_folder"),
    ],
    "p04_multistep": [
        T(M, "open {app}, then mute the sound", "MULTI"),
        T(H, "lock the screen after closing {app}", "MULTI|close_app"),
        T(V, "take a screenshot, open {app} and set the brightness to {n}", "MULTI"),
    ],
    "p05_safety": [
        T(M, "no, don't close {app}", "REJECT|CONTROL:reject_ticket"),
        T(H, "please do not open {app}", "REJECT"),
    ],
    "p06_voice_input": [
        T(E, "hey jarvis, would you open {app}", "open_app"),
        T(M, "jarvis, uh, turn the volume to {n}", "volume_set"),
        T(H, "okay so, jarvis, open {app} please", "open_app"),
        T(V, "jarvis are you there, open {app}", "open_app"),
        T(M, "can you hear me jarvis", "microphone_status"),
    ],
    "p07_voice_output": [
        T(E, "shush", "CONTROL:stop_speaking"),
        T(M, "stop talking please jarvis", "CONTROL:stop_speaking"),
        T(M, "use a man's voice", "set_voice"),
        T(H, "i didn't catch that, say it again", "recent_actions"),
        T(M, "answer me in thanglish", "set_reply_language"),
    ],
    "p08_history": [
        T(M, "what have you done so far", "recent_actions|command_history"),
        T(H, "wait, did you message {p} already", "recent_actions"),
        T(H, "who was the last message sent to", "recent_actions"),
        T(M, "show me the history of my commands", "command_history"),
    ],
    "p09_google": [
        T(E, "open my inbox", "gmail_list_recent|open_app|open_website"),
        T(M, "did i get any mail from {p}", "gmail_list_recent"),
        T(M, "what's on my calendar for next week", "calendar_list_events"),
        T(H, "do i have anything on wednesday afternoon", "calendar_list_events"),
        T(H, "add a meeting with {p} on thursday at 5 pm to my calendar", "calendar_create_event+clarify"),
    ],
    "p10_browser": [
        T(E, "visit {site}", "open_website"),
        T(M, "search the web for {q}", "open_website|search_web"),
        T(M, "i want to watch {song} on youtube", "play_youtube"),
        T(M, "go back to the last page", "browser_quick_action"),
        T(H, "open a new tab and go to {site}", "MULTI|open_website"),
        T(M, "what's happening in {city}", "search_news|search_web|CHAT"),
    ],
    "p11_vision": [
        T(M, "tell me what's on my screen right now", "describe_screen"),
        T(M, "click the close button on {app}", "screen_click|close_app"),
        T(H, "what's that error on my screen", "describe_screen|diagnose_error"),
    ],
    "p12_intelligence": [
        T(E, "remind me at 8 to take my medicine", "set_reminder"),
        T(M, "put {q} on my shopping list", "todo"),
        T(M, "don't let me forget to call {p} tomorrow", "set_reminder"),
        T(M, "remember that i parked on level 3", "remember_fact"),
        T(M, "start a 10 minute timer", "set_reminder"),
        T(H, "what did i ask you to remember", "recall_facts"),
    ],
    "x_whatsapp": [
        T(E, "whatsapp {p} saying {msg}", "send_whatsapp_message", {"recipient": "{p}"}),
        T(M, "just let {p} know {msg}", "send_whatsapp_message"),
        T(M, "any messages from {p}", "read_whatsapp_messages"),
        T(H, "read out the latest whatsapp messages", "read_whatsapp_messages"),
        T(H, "text {p} and tell them {msg}", "send_whatsapp_message"),
        T(V, "can you quickly send {p} a whatsapp that {msg}", "send_whatsapp_message"),
    ],
    "x_phone": [
        T(E, "phone battery level", "android_status"),
        T(M, "turn on the flashlight on my phone", "android_toggle|android_quick_action"),
        T(M, "open instagram on my mobile", "android_open_app"),
        T(H, "copy the latest screenshot from my phone to the pc", "android_pull_file"),
    ],
    "x_automation": [
        T(E, "install {app} on my pc", "install_software"),
        T(M, "get rid of {app} from my laptop", "uninstall_software+clarify"),
        T(M, "is {app} on this computer", "check_app_installed"),
        T(M, "update all the apps on my computer", "update_software"),
        T(H, "start a focus session of 25 minutes for maths", "start_study_focus"),
    ],
    "x_thanglish": [
        T(E, "{app} thora", "open_app"),
        T(M, "sound konjam korachidu", "volume_down"),
        T(M, "{app} moodu", "close_app"),
        T(H, "{p} kitta {msg} nu solliru", "send_whatsapp_message"),
        T(M, "screenshot edu da", "take_screenshot"),
    ],
    "x_chat": [
        T(E, "you're the best", "CHAT"),
        T(M, "i'm so tired today", "CHAT"),
        T(M, "tell me an interesting fact about space", "CHAT"),
        T(H, "what do you think about ai taking jobs", "CHAT"),
        T(M, "how old are you jarvis", "CHAT"),
    ],
}


def build5() -> list[dict]:
    return build_split(PHASES5, POOLS, "blind5")
