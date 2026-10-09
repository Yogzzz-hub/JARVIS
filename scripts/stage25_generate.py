"""Frame-first, bounded-composition Stage 2.5 candidate generation.

The generated data is machine-validated Q2 only when all deterministic checks
pass. Q2 is still barred from training until an independent 750-row audit.
Public corpora contribute spelling/distribution evidence, not action labels.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from scripts.stage25_gold_data import OUT, PAIRS, Pair, build_row, validate_row

ROOT_SEED = 25025
NAMES = [
    ("Naveen", "நவீன்", "நவீனுக்கு"), ("Arun", "அருண்", "அருணுக்கு"),
    ("Priya", "பிரியா", "பிரியாவுக்கு"), ("Meena", "மீனா", "மீனாவுக்கு"),
    ("Karthik", "கார்த்திக்", "கார்த்திக்குக்கு"), ("Divya", "திவ்யா", "திவ்யாவுக்கு"),
    ("Ravi", "ரவி", "ரவிக்கு"), ("Deepa", "தீபா", "தீபாவுக்கு"),
    ("Mohan", "மோகன்", "மோகனுக்கு"), ("Anu", "அனு", "அனுவுக்கு"),
]
ORDINALS = [("first", "முதல்", 1), ("second", "இரண்டாவது", 2), ("third", "மூன்றாவது", 3), ("last", "கடைசி", -1), ("latest", "சமீபத்திய", "latest")]
DATES = [("nethu", "நேற்று", "yesterday"), ("inniku", "இன்று", "today"), ("naalaiku", "நாளைக்கு", "tomorrow"), ("pona vaaram", "போன வாரம்", "last_week"), ("intha vaaram", "இந்த வாரம்", "this_week")]
FILE_OBJECTS = [("PDF ah", "PDF-ஐ", "PDF"), ("image ah", "படத்தை", "image"), ("report ah", "அறிக்கையை", "report"), ("document ah", "ஆவணத்தை", "document"), ("spreadsheet ah", "விரிதாளை", "spreadsheet"), ("presentation ah", "விளக்கக்காட்சியை", "presentation")]
MESSAGE_OBJECTS = [("message ah", "செய்தியை", "message"), ("voice note ah", "குரல் பதிவை", "voice_note"), ("reply ah", "பதிலை", "reply"), ("chat ah", "உரையாடலை", "chat")]
PROJECTS = [("Atlas", "அட்லஸ்", "Atlas"), ("Orbit", "ஆர்பிட்", "Orbit"), ("Nimbus", "நிம்பஸ்", "Nimbus"), ("Helix", "ஹெலிக்ஸ்", "Helix"), ("Cedar", "சீடர்", "Cedar"), ("Delta", "டெல்டா", "Delta"), ("Phoenix", "பீனிக்ஸ்", "Phoenix"), ("Sigma", "சிக்மா", "Sigma")]
APPS = [("Chrome", "Chrome", "Chrome"), ("Edge", "Edge", "Edge"), ("VS Code", "VS Code", "VS Code"), ("WhatsApp", "WhatsApp", "WhatsApp"), ("Excel", "Excel", "Excel"), ("Notepad", "Notepad", "Notepad"), ("Firefox", "Firefox", "Firefox")]
BROWSERS = [("Chrome", "Chrome", "Chrome"), ("Edge", "Edge", "Edge"), ("Firefox", "Firefox", "Firefox")]
PAGES = [("docs", "ஆவணங்கள்", "docs"), ("dashboard", "டாஷ்போர்டு", "dashboard"), ("settings", "அமைப்புகள்", "settings"), ("mail", "மின்னஞ்சல்", "mail"), ("calendar", "காலெண்டர்", "calendar")]
DEVICES = [("speaker la", "ஸ்பீக்கரில்", "speaker"), ("headphone la", "ஹெட்போனில்", "headphone"), ("laptop la", "லேப்டாப்பில்", "laptop"), ("phone la", "போனில்", "phone")]
SONGS = [("first song ah", "முதல் பாட்டை", "first_song"), ("last song ah", "கடைசி பாட்டை", "last_song"), ("playlist song ah", "பிளேலிஸ்ட் பாட்டை", "playlist_song"), ("saved song ah", "சேமித்த பாட்டை", "saved_song")]
EVENTS = [("meeting ah", "சந்திப்பை", "meeting"), ("review ah", "மதிப்பாய்வை", "review"), ("call ah", "அழைப்பை", "call"), ("reminder ah", "நினைவூட்டலை", "reminder")]
TIMES = [("9 mani", "9 மணிக்கு", "09:00"), ("10 mani", "10 மணிக்கு", "10:00"), ("11 mani", "11 மணிக்கு", "11:00"), ("4 mani", "4 மணிக்கு", "16:00"), ("5:30", "5:30க்கு", "17:30")]
FORMATS = [("Word ku", "Word ஆக", "Word"), ("PDF ku", "PDF ஆக", "PDF"), ("PNG ku", "PNG ஆக", "PNG"), ("JPG ku", "JPG ஆக", "JPG"), ("text ku", "உரையாக", "text")]
UPLOAD_TARGETS = [("Drive la", "Drive-இல்", "Drive"), ("portal la", "போர்டலில்", "portal"), ("server ku", "சர்வருக்கு", "server")]
FOLDERS = [("Reports folder ku", "அறிக்கைகள் கோப்புறைக்கு", "Reports"), ("Downloads folder ku", "பதிவிறக்கங்கள் கோப்புறைக்கு", "Downloads"), ("Archive folder ku", "காப்பகக் கோப்புறைக்கு", "Archive"), ("Project folder ku", "திட்டக் கோப்புறைக்கு", "Project")]
PAGE_OBJECTS = [("docs page ku", "ஆவணப் பக்கத்துக்கு", "docs"), ("dashboard ku", "டாஷ்போர்டுக்கு", "dashboard"), ("settings page ku", "அமைப்புப் பக்கத்துக்கு", "settings"), ("calendar page ku", "காலெண்டர் பக்கத்துக்கு", "calendar"), ("mail page ku", "மின்னஞ்சல் பக்கத்துக்கு", "mail")]
PAGE_SHOW_OBJECTS = [("docs page ah", "ஆவணப் பக்கத்தைக்", "docs"), ("dashboard ah", "டாஷ்போர்டைக்", "dashboard"), ("settings page ah", "அமைப்புப் பக்கத்தைக்", "settings"), ("calendar page ah", "காலெண்டர் பக்கத்தைக்", "calendar"), ("mail page ah", "மின்னஞ்சல் பக்கத்தைக்", "mail")]
SCREEN_OBJECTS = [("screenshot ah", "திரைப் படத்தை", "screenshot"), ("window screenshot ah", "சாளரத் திரைப் படத்தை", "window_screenshot"), ("screen capture ah", "திரைப் பதிவை", "screen_capture")]
FOLDER_OBJECTS = [("Reports folder ah", "அறிக்கைகள் கோப்புறையை", "Reports"), ("Archive folder ah", "காப்பகக் கோப்புறையை", "Archive"), ("Invoices folder ah", "ரசீதுகள் கோப்புறையை", "Invoices"), ("Notes folder ah", "குறிப்புகள் கோப்புறையை", "Notes")]
STYLES = [("professional ah", "தொழில்முறையாக", "professional"), ("short ah", "சுருக்கமாக", "concise"), ("simple ah", "எளிமையாக", "simple"), ("formal ah", "முறையாக", "formal")]
TEXT_OBJECTS = [("sentence ah", "வாக்கியத்தை", "sentence"), ("reply ah", "பதிலை", "reply"), ("note ah", "குறிப்பை", "note")]
DATA_OBJECTS = [("sales data ah", "விற்பனைத் தரவை", "sales"), ("user data ah", "பயனர் தரவை", "user"), ("error logs ah", "பிழைப் பதிவுகளை", "error_logs"), ("records ah", "பதிவுகளை", "records")]
DATA_SOURCES = [("database la irundhu", "தரவுத்தளத்திலிருந்து", "database"), ("logs la irundhu", "பதிவுகளிலிருந்து", "logs"), ("server la irundhu", "சர்வரிலிருந்து", "server")]


@dataclass(frozen=True)
class Scenario:
    key: str
    action: str
    object_type: str
    domain: str
    objects: tuple[tuple[str, str, str], ...]
    object_slot: str
    templates: tuple[tuple[str, str], ...]
    verbs: dict[str, tuple[str, str]]
    quota: int


# Each template is a distinct composition of *compatible* semantic slots. The
# slots themselves are chosen before realization; a template cannot inject a
# random action or target. Nouns are pre-inflected for conversational Tamil.
SCENARIOS = [
    Scenario("send_file", "SEND", "FileRef", "FILES", tuple(FILE_OBJECTS), "file_type", (
        ("{recipient} {object} {verb}", "{recipient} {object} {verb}"),
        ("{ordinal} {object} {recipient} {verb}", "{ordinal} {object} {recipient} {verb}"),
        ("{date} {sender} anupuna {ordinal} {object} {recipient} {verb}", "{date} {sender} அனுப்பிய {ordinal} {object} {recipient} {verb}"),
        ("{sender} oda {object} {recipient} {verb}", "{sender} அனுப்பிய {object} {recipient} {verb}"),
        ("{recipient} {date} vandha {object} {verb}", "{date} வந்த {object} {recipient} {verb}"),
        ("{ordinal} {object} mattum {recipient} {verb}", "{ordinal} {object} மட்டும் {recipient} {verb}"),
        ("{date} {sender} anupuna {object} {recipient} {verb}", "{date} {sender} அனுப்பிய {object} {recipient} {verb}"),
    ), {"COMMAND": ("anuppu", "அனுப்பு"), "NEGATED_COMMAND": ("anuppadha", "அனுப்பாதே"), "STATUS_QUERY": ("anupitiya?", "அனுப்பினாயா?"), "CAPABILITY_QUERY": ("anupa mudiyuma?", "அனுப்ப முடியுமா?"), "HYPOTHETICAL": ("anupuna enna aagum?", "அனுப்பினால் என்ன ஆகும்?")}, 4000),
    Scenario("show_file", "SHOW", "FileRef", "FILES", tuple(FILE_OBJECTS), "file_type", (
        ("{ordinal} {object} {verb}", "{ordinal} {object} {verb}"),
        ("{date} {sender} anupuna {object} {verb}", "{date} {sender} அனுப்பிய {object} {verb}"),
        ("{sender} oda {ordinal} {object} {verb}", "{sender} அனுப்பிய {ordinal} {object} {verb}"),
        ("{object} mattum {verb}", "{object} மட்டும் {verb}"),
        ("{date} vandha {ordinal} {object} {verb}", "{date} வந்த {ordinal} {object} {verb}"),
    ), {"COMMAND": ("kaatu", "காட்டு"), "NEGATED_COMMAND": ("kaatadha", "காட்டாதே"), "STATUS_QUERY": ("kaatiniya?", "காட்டினாயா?")}, 2000),
    Scenario("select_file", "SELECT", "FileRef", "FILES", tuple(FILE_OBJECTS), "file_type", (
        ("{ordinal} {object} {verb}", "{ordinal} {object} {verb}"),
        ("{sender} oda {ordinal} {object} {verb}", "{sender} அனுப்பிய {ordinal} {object} {verb}"),
        ("{date} vandha {ordinal} {object} {verb}", "{date} வந்த {ordinal} {object} {verb}"),
        ("{ordinal} {object} mattum {verb}", "{ordinal} {object} மட்டும் {verb}"),
    ), {"COMMAND": ("eduthu", "எடு"), "NEGATED_COMMAND": ("edukadha", "எடுக்காதே"), "STATUS_QUERY": ("eduthiya?", "எடுத்தாயா?")}, 1250),
    Scenario("convert_file", "CONVERT", "FileRef", "FILES", tuple(FILE_OBJECTS), "file_type", (
        ("{object} {destination} {verb}", "{object} {destination} {verb}"),
        ("{ordinal} {object} {destination} {verb}", "{ordinal} {object} {destination} {verb}"),
        ("{sender} anupuna {object} {destination} {verb}", "{sender} அனுப்பிய {object} {destination} {verb}"),
        ("{date} vandha {object} {destination} {verb}", "{date} வந்த {object} {destination} {verb}"),
    ), {"COMMAND": ("maathu", "மாற்று"), "NEGATED_COMMAND": ("maathadha", "மாற்றாதே"), "STATUS_QUERY": ("maathitiya?", "மாற்றினாயா?")}, 2000),
    Scenario("read_message", "READ", "MessageRef", "MESSAGES", tuple(MESSAGE_OBJECTS), "resource_type", (
        ("{sender} oda {ordinal} {object} {verb}", "{sender} அனுப்பிய {ordinal} {object} {verb}"),
        ("{date} {sender} anupuna {object} {verb}", "{date} {sender} அனுப்பிய {object} {verb}"),
        ("{ordinal} {object} {verb}", "{ordinal} {object} {verb}"),
        ("{date} vandha {ordinal} {object} {verb}", "{date} வந்த {ordinal} {object} {verb}"),
    ), {"COMMAND": ("paaru", "பாரு"), "NEGATED_COMMAND": ("paakadha", "பார்க்காதே"), "STATUS_QUERY": ("paathiya?", "பார்த்தாயா?")}, 1250),
    Scenario("forward_message", "FORWARD", "MessageRef", "MESSAGES", tuple(MESSAGE_OBJECTS), "resource_type", (
        ("{sender} oda {object} {recipient} {verb}", "{sender} அனுப்பிய {object} {recipient} {verb}"),
        ("{ordinal} {object} {recipient} {verb}", "{ordinal} {object} {recipient} {verb}"),
        ("{date} vandha {object} {recipient} {verb}", "{date} வந்த {object} {recipient} {verb}"),
        ("{sender} oda {ordinal} {object} {recipient} {verb}", "{sender} அனுப்பிய {ordinal} {object} {recipient} {verb}"),
    ), {"COMMAND": ("forward pannu", "முன்னனுப்பு"), "NEGATED_COMMAND": ("forward pannadha", "முன்னனுப்பாதே"), "STATUS_QUERY": ("forward pannitiya?", "முன்னனுப்பினாயா?")}, 1750),
    Scenario("run_project", "RUN", "ProjectRef", "IDE", tuple(PROJECTS), "project", (
        ("{object} project ah {verb}", "{object} திட்டத்தை {verb}"),
        ("{date} {object} project ah {verb}", "{date} {object} திட்டத்தை {verb}"),
        ("{object} backend ah {verb}", "{object} பேக்கெண்டை {verb}"),
        ("{object} project mattum {verb}", "{object} திட்டத்தை மட்டும் {verb}"),
    ), {"COMMAND": ("run pannu", "இயக்கு"), "NEGATED_COMMAND": ("run pannadha", "இயக்காதே"), "STATUS_QUERY": ("run pannitiya?", "இயக்கினாயா?")}, 900),
    Scenario("check_project", "CHECK", "ProjectRef", "IDE", tuple(PROJECTS), "project", (
        ("{object} project status {verb}", "{object} திட்ட நிலையை {verb}"),
        ("{date} {object} backend status {verb}", "{date} {object} பேக்கெண்ட் நிலையை {verb}"),
        ("{object} run aagudha {verb}", "{object} ஓடுதா {verb}"),
        ("{object} error iruka {verb}", "{object} பிழை இருக்கா {verb}"),
    ), {"COMMAND": ("paaru", "பாரு"), "NEGATED_COMMAND": ("paakadha", "பார்க்காதே"), "STATUS_QUERY": ("paathiya?", "பார்த்தாயா?")}, 900),
    Scenario("set_volume", "SET", "Volume", "PC", (("volume", "ஒலியை", "volume"),), "resource_type", (
        ("{device} {object} {number} ku {verb}", "{device} {object} {number}க்கு {verb}"),
        ("{object} {number} ku {verb}", "{object} {number}க்கு {verb}"),
        ("{date} {device} {object} {number} ku {verb}", "{date} {device} {object} {number}க்கு {verb}"),
    ), {"COMMAND": ("podu", "வை"), "NEGATED_COMMAND": ("podadha", "வைக்காதே"), "STATUS_QUERY": ("potiya?", "வைத்தாயா?")}, 650),
    Scenario("switch_tab", "SWITCH", "BrowserTabRef", "BROWSER", (("tab ku", "டேப்க்கு", "tab"),), "browser_tab", (
        ("{browser} la {ordinal} {object} {verb}", "{browser} இல் {ordinal} {object} {verb}"),
        ("{ordinal} {object} {verb}", "{ordinal} {object} {verb}"),
        ("{browser} la {page} irukkura {ordinal} {object} {verb}", "{browser} இல் {page} இருக்கும் {ordinal} {object} {verb}"),
    ), {"COMMAND": ("maathu", "மாறு"), "NEGATED_COMMAND": ("maathadha", "மாறாதே"), "STATUS_QUERY": ("maathitiya?", "மாறினாயா?")}, 650),
    Scenario("open_app", "OPEN", "AppRef", "PC", tuple(APPS), "application", (
        ("{object} ah {verb}", "{object} ஐ {verb}"),
        ("{date} {object} ah {verb}", "{date} {object} ஐ {verb}"),
        ("{object} mattum {verb}", "{object} மட்டும் {verb}"),
    ), {"COMMAND": ("open pannu", "திற"), "NEGATED_COMMAND": ("open pannadha", "திறக்காதே"), "STATUS_QUERY": ("open pannitiya?", "திறந்தாயா?")}, 350),
    Scenario("play_song", "PLAY", "AudioRef", "MEDIA", tuple(SONGS), "resource_type", (
        ("{device} {object} {verb}", "{device} {object} {verb}"),
        ("{date} {object} {verb}", "{date} {object} {verb}"),
        ("{object} mattum {verb}", "{object} மட்டும் {verb}"),
    ), {"COMMAND": ("podu", "போடு"), "NEGATED_COMMAND": ("podadha", "போடாதே"), "STATUS_QUERY": ("potiya?", "போட்டாயா?")}, 350),
    Scenario("create_event", "CREATE", "CalendarEventRef", "CALENDAR", tuple(EVENTS), "resource_type", (
        ("{date} {time} {object} calendar la {verb}", "{date} {time} {object} காலெண்டரில் {verb}"),
        ("{recipient} {date} {time} {object} calendar la {verb}", "{recipient} {date} {time} {object} காலெண்டரில் {verb}"),
        ("{date} {object} {time} calendar la {verb}", "{date} {object} {time} காலெண்டரில் {verb}"),
    ), {"COMMAND": ("podu", "போடு"), "NEGATED_COMMAND": ("podadha", "போடாதே"), "STATUS_QUERY": ("potiya?", "போட்டாயா?")}, 1350),
    Scenario("summarize_chat", "SUMMARIZE", "MessageRef", "MESSAGES", (("chat ah", "உரையாடலை", "chat"), ("messages ah", "செய்திகளை", "messages")), "resource_type", (
        ("{sender} oda {object} {verb}", "{sender} உடைய {object} {verb}"),
        ("{date} {sender} oda {object} {verb}", "{date} {sender} உடைய {object} {verb}"),
        ("{sender} oda {ordinal} {object} {verb}", "{sender} உடைய {ordinal} {object} {verb}"),
    ), {"COMMAND": ("summary kudu", "சுருக்கம் கொடு"), "NEGATED_COMMAND": ("summary kudukadha", "சுருக்கம் கொடுக்காதே"), "STATUS_QUERY": ("summary kuduthiya?", "சுருக்கம் கொடுத்தாயா?")}, 800),
]

SCENARIOS.extend([
    Scenario("navigate_page", "NAVIGATE", "BrowserPageRef", "BROWSER", tuple(PAGE_OBJECTS), "resource_type", (
        ("{browser} la {object} {verb}", "{browser} இல் {object} {verb}"),
        ("{object} {verb}", "{object} {verb}"),
        ("{browser} la {ordinal} {object} {verb}", "{browser} இல் {ordinal} {object} {verb}"),
    ), {"COMMAND": ("po", "போ"), "NEGATED_COMMAND": ("pogadha", "போகாதே"), "STATUS_QUERY": ("poniya?", "போனாயா?")}, 550),
    Scenario("upload_file", "UPLOAD", "FileRef", "FILES", tuple(FILE_OBJECTS), "file_type", (
        ("{object} {upload_destination} {verb}", "{object} {upload_destination} {verb}"),
        ("{ordinal} {object} {upload_destination} {verb}", "{ordinal} {object} {upload_destination} {verb}"),
        ("{sender} anupuna {object} {upload_destination} {verb}", "{sender} அனுப்பிய {object} {upload_destination} {verb}"),
        ("{date} vandha {object} {upload_destination} {verb}", "{date} வந்த {object} {upload_destination} {verb}"),
    ), {"COMMAND": ("upload pannu", "பதிவேற்று"), "NEGATED_COMMAND": ("upload pannadha", "பதிவேற்றாதே"), "STATUS_QUERY": ("upload pannitiya?", "பதிவேற்றினாயா?")}, 950),
    Scenario("copy_file", "COPY", "FileRef", "FILES", tuple(FILE_OBJECTS), "file_type", (
        ("{object} {folder_destination} {verb}", "{object} {folder_destination} {verb}"),
        ("{ordinal} {object} {folder_destination} {verb}", "{ordinal} {object} {folder_destination} {verb}"),
        ("{sender} anupuna {object} {folder_destination} {verb}", "{sender} அனுப்பிய {object} {folder_destination} {verb}"),
        ("{date} vandha {object} {folder_destination} {verb}", "{date} வந்த {object} {folder_destination} {verb}"),
    ), {"COMMAND": ("copy pannu", "நகலெடு"), "NEGATED_COMMAND": ("copy pannadha", "நகலெடுக்காதே"), "STATUS_QUERY": ("copy pannitiya?", "நகலெடுத்தாயா?")}, 950),
    Scenario("create_folder", "CREATE", "FolderRef", "FILES", tuple(FOLDER_OBJECTS), "folder", (
        ("{object} {verb}", "{object} {verb}"),
        ("{project} project la {object} {verb}", "{project} திட்டத்தில் {object} {verb}"),
        ("{date} {object} {verb}", "{date} {object} {verb}"),
    ), {"COMMAND": ("create pannu", "உருவாக்கு"), "NEGATED_COMMAND": ("create pannadha", "உருவாக்காதே"), "STATUS_QUERY": ("create pannitiya?", "உருவாக்கினாயா?")}, 450),
    Scenario("capture_screen", "CAPTURE", "ScreenshotRef", "PC", tuple(SCREEN_OBJECTS), "resource_type", (
        ("{object} {verb}", "{object} {verb}"),
        ("{application} la {object} {verb}", "{application} இல் {object} {verb}"),
        ("{date} {application} la {object} {verb}", "{date} {application} இல் {object} {verb}"),
    ), {"COMMAND": ("eduthu", "எடு"), "NEGATED_COMMAND": ("edukadha", "எடுக்காதே"), "STATUS_QUERY": ("eduthiya?", "எடுத்தாயா?")}, 450),
    Scenario("increase_brightness", "INCREASE", "Brightness", "PC", (("brightness ah", "திரை வெளிச்சத்தை", "brightness"),), "resource_type", (
        ("{device} {object} {number} percent {verb}", "{device} {object} {number} சதவீதம் {verb}"),
        ("{object} {number} percent {verb}", "{object} {number} சதவீதம் {verb}"),
    ), {"COMMAND": ("increase pannu", "கூட்டு"), "NEGATED_COMMAND": ("increase pannadha", "கூட்டாதே"), "STATUS_QUERY": ("increase pannitiya?", "கூட்டினாயா?")}, 350),
    Scenario("list_files", "LIST", "FileRef", "FILES", (("PDF files ah", "PDF கோப்புகளை", "PDF"), ("images ah", "படங்களை", "image"), ("reports ah", "அறிக்கைகளை", "report"), ("documents ah", "ஆவணங்களை", "document")), "file_type", (
        ("{folder_destination} irukkura {object} {verb}", "{folder_destination} இருக்கும் {object} {verb}"),
        ("{date} vandha {object} {verb}", "{date} வந்த {object} {verb}"),
        ("{sender} anupuna {object} {verb}", "{sender} அனுப்பிய {object} {verb}"),
    ), {"COMMAND": ("kaatu", "காட்டு"), "NEGATED_COMMAND": ("kaatadha", "காட்டாதே"), "STATUS_QUERY": ("kaatiniya?", "காட்டினாயா?")}, 650),
    Scenario("delete_file", "DELETE", "FileRef", "FILES", tuple(FILE_OBJECTS), "file_type", (
        ("{ordinal} {object} {verb}", "{ordinal} {object} {verb}"),
        ("{sender} anupuna {object} {verb}", "{sender} அனுப்பிய {object} {verb}"),
        ("{date} vandha {object} {verb}", "{date} வந்த {object} {verb}"),
    ), {"COMMAND": ("delete pannu", "அழி"), "NEGATED_COMMAND": ("delete pannadha", "அழிக்காதே"), "STATUS_QUERY": ("delete pannitiya?", "அழித்தாயா?")}, 400),
    Scenario("move_file", "MOVE", "FileRef", "FILES", tuple(FILE_OBJECTS), "file_type", (
        ("{object} {folder_destination} {verb}", "{object} {folder_destination} {verb}"),
        ("{ordinal} {object} {folder_destination} {verb}", "{ordinal} {object} {folder_destination} {verb}"),
        ("{sender} anupuna {object} {folder_destination} {verb}", "{sender} அனுப்பிய {object} {folder_destination} {verb}"),
    ), {"COMMAND": ("maathu", "மாற்று"), "NEGATED_COMMAND": ("maathadha", "மாற்றாதே"), "STATUS_QUERY": ("maathitiya?", "மாற்றினாயா?")}, 850),
    Scenario("change_style", "CHANGE", "TextResource", "FILES", tuple(TEXT_OBJECTS), "resource_type", (
        ("{object} {style} {verb}", "{object} {style} {verb}"),
        ("{style} {object} {verb}", "{style} {object} {verb}"),
    ), {"COMMAND": ("maathu", "மாற்று"), "NEGATED_COMMAND": ("maathadha", "மாற்றாதே"), "STATUS_QUERY": ("maathitiya?", "மாற்றினாயா?")}, 220),
    Scenario("retrieve_data", "RETRIEVE", "DataRef", "IDE", tuple(DATA_OBJECTS), "resource_type", (
        ("{source} {object} {verb}", "{source} {object} {verb}"),
        ("{ordinal} {object} {source} {verb}", "{ordinal} {object} {source} {verb}"),
        ("{source} {date} irundha {object} {verb}", "{source} {date} இருந்த {object} {verb}"),
    ), {"COMMAND": ("eduthu", "எடு"), "NEGATED_COMMAND": ("edukadha", "எடுக்காதே"), "STATUS_QUERY": ("eduthiya?", "எடுத்தாயா?")}, 400),
    Scenario("navigate_page_show", "NAVIGATE", "BrowserPageRef", "BROWSER", tuple(PAGE_SHOW_OBJECTS), "resource_type", (
        ("{browser} la {object} {verb}", "{browser} இல் {object} {verb}"),
        ("{object} {verb}", "{object} {verb}"),
    ), {"COMMAND": ("kaatu", "காட்டு"), "NEGATED_COMMAND": ("kaatadha", "காட்டாதே"), "STATUS_QUERY": ("kaatiniya?", "காட்டினாயா?")}, 300),
    Scenario("send_file_kudu", "SEND", "FileRef", "FILES", tuple(FILE_OBJECTS), "file_type", (
        ("{recipient} {object} {verb}", "{recipient} {object} {verb}"),
        ("{ordinal} {object} {recipient} {verb}", "{ordinal} {object} {recipient} {verb}"),
        ("{sender} anupuna {object} {recipient} {verb}", "{sender} அனுப்பிய {object} {recipient} {verb}"),
    ), {"COMMAND": ("kudu", "கொடு"), "NEGATED_COMMAND": ("kudukadha", "கொடுக்காதே"), "STATUS_QUERY": ("kuduthiya?", "கொடுத்தாயா?")}, 550),
])

# Distinct language-level meanings that the first build barely represented.
# Each entry supplies an object affordance and inflected conversational forms;
# the scene generator varies structure and speech act without changing meaning.
FILE_SHAPES = (
    ("{object} {verb}", "{object} {verb}"),
    ("{ordinal} {object} {verb}", "{ordinal} {object} {verb}"),
    ("{sender} anupuna {object} {verb}", "{sender} அனுப்பிய {object} {verb}"),
    ("{date} vandha {object} {verb}", "{date} வந்த {object} {verb}"),
)
APP_SHAPES = (
    ("{object} ah {verb}", "{object} ஐ {verb}"),
    ("{workspace} {object} ah {verb}", "{workspace} {object} ஐ {verb}"),
    ("{object} mattum {verb}", "{object} மட்டும் {verb}"),
)
PROJECT_SHAPES = (
    ("{object} project ah {verb}", "{object} திட்டத்தை {verb}"),
    ("{workspace} {object} project ah {verb}", "{workspace} {object} திட்டத்தை {verb}"),
    ("{object} backend ah {verb}", "{object} பேக்கெண்டை {verb}"),
)


def extended_scene(key, action, object_type, domain, objects, object_slot, shapes, command, negated, status, capability, quota=140):
    return Scenario(key, action, object_type, domain, tuple(objects), object_slot, shapes,
        {"COMMAND": command, "NEGATED_COMMAND": negated, "STATUS_QUERY": status,
         "CAPABILITY_QUERY": capability}, quota)


SCENARIOS.extend([
    extended_scene("close_app", "CLOSE", "AppRef", "PC", APPS, "application", APP_SHAPES, ("close pannu", "மூடு"), ("close pannadha", "மூடாதே"), ("close pannitiya?", "மூடினாயா?"), ("close panna mudiyuma?", "மூட முடியுமா?")),
    extended_scene("install_app", "INSTALL", "AppRef", "PC", APPS, "application", APP_SHAPES, ("install pannu", "நிறுவு"), ("install pannadha", "நிறுவாதே"), ("install pannitiya?", "நிறுவினாயா?"), ("install panna mudiyuma?", "நிறுவ முடியுமா?")),
    extended_scene("uninstall_app", "UNINSTALL", "AppRef", "PC", APPS, "application", APP_SHAPES, ("uninstall pannu", "நீக்கு"), ("uninstall pannadha", "நீக்காதே"), ("uninstall pannitiya?", "நீக்கினாயா?"), ("uninstall panna mudiyuma?", "நீக்க முடியுமா?")),
    extended_scene("start_project", "START", "ProjectRef", "IDE", PROJECTS, "project", PROJECT_SHAPES, ("start pannu", "தொடங்கு"), ("start pannadha", "தொடங்காதே"), ("start pannitiya?", "தொடங்கினாயா?"), ("start panna mudiyuma?", "தொடங்க முடியுமா?")),
    extended_scene("stop_project", "STOP", "ProjectRef", "IDE", PROJECTS, "project", PROJECT_SHAPES, ("stop pannu", "நிறுத்து"), ("stop pannadha", "நிறுத்தாதே"), ("stop pannitiya?", "நிறுத்தினாயா?"), ("stop panna mudiyuma?", "நிறுத்த முடியுமா?")),
    extended_scene("pause_project", "PAUSE", "ProjectRef", "IDE", PROJECTS, "project", PROJECT_SHAPES, ("pause pannu", "இடைநிறுத்து"), ("pause pannadha", "இடைநிறுத்தாதே"), ("pause pannitiya?", "இடைநிறுத்தினாயா?"), ("pause panna mudiyuma?", "இடைநிறுத்த முடியுமா?")),
    extended_scene("resume_project", "RESUME", "ProjectRef", "IDE", PROJECTS, "project", PROJECT_SHAPES, ("resume pannu", "மீண்டும் தொடங்கு"), ("resume pannadha", "மீண்டும் தொடங்காதே"), ("resume pannitiya?", "மீண்டும் தொடங்கினாயா?"), ("resume panna mudiyuma?", "மீண்டும் தொடங்க முடியுமா?")),
    extended_scene("restart_project", "RESTART", "ProjectRef", "IDE", PROJECTS, "project", PROJECT_SHAPES, ("restart pannu", "மறுதொடக்கம் செய்"), ("restart pannadha", "மறுதொடக்கம் செய்யாதே"), ("restart pannitiya?", "மறுதொடக்கம் செய்தாயா?"), ("restart panna mudiyuma?", "மறுதொடக்கம் செய்ய முடியுமா?")),
    extended_scene("search_files", "SEARCH", "FileRef", "FILES", FILE_OBJECTS, "file_type", FILE_SHAPES, ("search pannu", "தேடு"), ("search pannadha", "தேடாதே"), ("search pannitiya?", "தேடினாயா?"), ("search panna mudiyuma?", "தேட முடியுமா?")),
    extended_scene("find_files", "FIND", "FileRef", "FILES", FILE_OBJECTS, "file_type", FILE_SHAPES, ("kandupidi", "கண்டுபிடி"), ("kandupidikadha", "கண்டுபிடிக்காதே"), ("kandupidichitiya?", "கண்டுபிடித்தாயா?"), ("kandupidikka mudiyuma?", "கண்டுபிடிக்க முடியுமா?")),
    extended_scene("inspect_files", "INSPECT", "FileRef", "FILES", FILE_OBJECTS, "file_type", FILE_SHAPES, ("inspect pannu", "ஆய்வு செய்"), ("inspect pannadha", "ஆய்வு செய்யாதே"), ("inspect pannitiya?", "ஆய்வு செய்தாயா?"), ("inspect panna mudiyuma?", "ஆய்வு செய்ய முடியுமா?")),
    extended_scene("verify_files", "VERIFY", "FileRef", "FILES", FILE_OBJECTS, "file_type", FILE_SHAPES, ("verify pannu", "சரிபார்"), ("verify pannadha", "சரிபார்க்காதே"), ("verify pannitiya?", "சரிபார்த்தாயா?"), ("verify panna mudiyuma?", "சரிபார்க்க முடியுமா?")),
    extended_scene("download_files", "DOWNLOAD", "FileRef", "FILES", FILE_OBJECTS, "file_type", FILE_SHAPES, ("download pannu", "பதிவிறக்கு"), ("download pannadha", "பதிவிறக்காதே"), ("download pannitiya?", "பதிவிறக்கினாயா?"), ("download panna mudiyuma?", "பதிவிறக்க முடியுமா?")),
    extended_scene("save_files", "SAVE", "FileRef", "FILES", FILE_OBJECTS, "file_type", FILE_SHAPES, ("save pannu", "சேமி"), ("save pannadha", "சேமிக்காதே"), ("save pannitiya?", "சேமித்தாயா?"), ("save panna mudiyuma?", "சேமிக்க முடியுமா?")),
    extended_scene("filter_files", "FILTER", "FileRef", "FILES", FILE_OBJECTS, "file_type", FILE_SHAPES, ("filter pannu", "வடிகட்டு"), ("filter pannadha", "வடிகட்டாதே"), ("filter pannitiya?", "வடிகட்டினாயா?"), ("filter panna mudiyuma?", "வடிகட்ட முடியுமா?")),
    extended_scene("sort_files", "SORT", "FileRef", "FILES", FILE_OBJECTS, "file_type", FILE_SHAPES, ("sort pannu", "வரிசைப்படுத்து"), ("sort pannadha", "வரிசைப்படுத்தாதே"), ("sort pannitiya?", "வரிசைப்படுத்தினாயா?"), ("sort panna mudiyuma?", "வரிசைப்படுத்த முடியுமா?")),
    extended_scene("compare_files", "COMPARE", "FileRef", "FILES", FILE_OBJECTS, "file_type", FILE_SHAPES, ("compare pannu", "ஒப்பிடு"), ("compare pannadha", "ஒப்பிடாதே"), ("compare pannitiya?", "ஒப்பிட்டாயா?"), ("compare panna mudiyuma?", "ஒப்பிட முடியுமா?")),
    extended_scene("reply_message", "REPLY", "MessageRef", "MESSAGES", MESSAGE_OBJECTS, "resource_type", FILE_SHAPES, ("reply kudu", "பதில் அனுப்பு"), ("reply kudukadha", "பதில் அனுப்பாதே"), ("reply kuduthiya?", "பதில் அனுப்பினாயா?"), ("reply kudukka mudiyuma?", "பதில் அனுப்ப முடியுமா?")),
    extended_scene("share_files", "SHARE", "FileRef", "FILES", FILE_OBJECTS, "file_type", (("{object} {recipient} {verb}", "{object} {recipient} {verb}"), ("{ordinal} {object} {recipient} {verb}", "{ordinal} {object} {recipient} {verb}")), ("share pannu", "பகிர்"), ("share pannadha", "பகிராதே"), ("share pannitiya?", "பகிர்ந்தாயா?"), ("share panna mudiyuma?", "பகிர முடியுமா?")),
    extended_scene("write_text", "WRITE", "TextResource", "FILES", TEXT_OBJECTS, "resource_type", FILE_SHAPES, ("ezhuthu", "எழுது"), ("ezhuthadha", "எழுதாதே"), ("ezhuthitiya?", "எழுதினாயா?"), ("ezhutha mudiyuma?", "எழுத முடியுமா?")),
    extended_scene("explain_text", "EXPLAIN", "TextResource", "FILES", TEXT_OBJECTS, "resource_type", FILE_SHAPES, ("vilakku", "விளக்கு"), ("vilakkadha", "விளக்காதே"), ("vilakkitiya?", "விளக்கினாயா?"), ("vilakka mudiyuma?", "விளக்க முடியுமா?")),
    extended_scene("provide_answer", "PROVIDE", "AnswerRef", "GENERAL", (("answer ah", "பதிலை", "answer"), ("number ah", "எண்ணை", "number"), ("details ah", "விவரங்களை", "details")), "resource_type", (("{object} {verb}", "{object} {verb}"), ("{project} pathi {object} {verb}", "{project} பற்றி {object} {verb}")), ("kudu", "கொடு"), ("kudukadha", "கொடுக்காதே"), ("kuduthiya?", "கொடுத்தாயா?"), ("kudukkaa mudiyuma?", "கொடுக்க முடியுமா?")),
    extended_scene("decrease_volume", "DECREASE", "Volume", "PC", (("volume ah", "ஒலியை", "volume"),), "resource_type", (("{device} {object} {number} percent {verb}", "{device} {object} {number} சதவீதம் {verb}"), ("{object} {number} percent {verb}", "{object} {number} சதவீதம் {verb}")), ("kammi pannu", "குறை"), ("kammi pannadha", "குறைக்காதே"), ("kammi pannitiya?", "குறைத்தாயா?"), ("kammi panna mudiyuma?", "குறைக்க முடியுமா?")),
    extended_scene("cancel_workflow", "CANCEL", "WorkflowRef", "IDE", PROJECTS, "project", (("{object} workflow ah {verb}", "{object} பணிச்சுற்றை {verb}"), ("{workspace} {object} workflow ah {verb}", "{workspace} {object} பணிச்சுற்றை {verb}")), ("cancel pannu", "ரத்து செய்"), ("cancel pannadha", "ரத்து செய்யாதே"), ("cancel pannitiya?", "ரத்து செய்தாயா?"), ("cancel panna mudiyuma?", "ரத்து செய்ய முடியுமா?")),
    extended_scene("click_button", "CLICK", "UIElementRef", "BROWSER", (("next button ah", "அடுத்து பொத்தானை", "next"), ("menu button ah", "மெனு பொத்தானை", "menu"), ("details button ah", "விவரங்கள் பொத்தானை", "details"), ("back button ah", "பின்செல் பொத்தானை", "back"), ("search button ah", "தேடல் பொத்தானை", "search"), ("help button ah", "உதவி பொத்தானை", "help")), "resource_type", (("{browser} la {object} {verb}", "{browser} இல் {object} {verb}"), ("{object} {verb}", "{object} {verb}")), ("click pannu", "அழுத்து"), ("click pannadha", "அழுத்தாதே"), ("click pannitiya?", "அழுத்தினாயா?"), ("click panna mudiyuma?", "அழுத்த முடியுமா?")),
    extended_scene("call_contact", "CALL", "ContactRef", "PHONE", [(n[0] + " ku", n[2], n[0]) for n in NAMES], "contact", (("{object} {verb}", "{object} {verb}"), ("{phone_line} {object} {verb}", "{phone_line} {object} {verb}")), ("call pannu", "அழை"), ("call pannadha", "அழைக்காதே"), ("call pannitiya?", "அழைத்தாயா?"), ("call panna mudiyuma?", "அழைக்க முடியுமா?")),
    extended_scene("search_messages", "SEARCH", "MessageRef", "MESSAGES", MESSAGE_OBJECTS, "resource_type", FILE_SHAPES, ("search pannu", "தேடு"), ("search pannadha", "தேடாதே"), ("search pannitiya?", "தேடினாயா?"), ("search panna mudiyuma?", "தேட முடியுமா?")),
    extended_scene("search_projects", "SEARCH", "ProjectRef", "IDE", PROJECTS, "project", PROJECT_SHAPES, ("search pannu", "தேடு"), ("search pannadha", "தேடாதே"), ("search pannitiya?", "தேடினாயா?"), ("search panna mudiyuma?", "தேட முடியுமா?")),
    extended_scene("open_urls", "OPEN", "URLRef", "BROWSER", [(f"https://site{i}.example.org", f"https://site{i}.example.org", f"https://site{i}.example.org") for i in range(40)], "URL", (("{browser} la {object} {verb}", "{browser} இல் {object} {verb}"), ("{object} {verb}", "{object} {verb}")), ("open pannu", "திற"), ("open pannadha", "திறக்காதே"), ("open pannitiya?", "திறந்தாயா?"), ("open panna mudiyuma?", "திறக்க முடியுமா?")),
    extended_scene("check_messages", "CHECK", "MessageRef", "MESSAGES", MESSAGE_OBJECTS, "resource_type", FILE_SHAPES, ("status check pannu", "நிலையைச் சரிபார்"), ("status check pannadha", "நிலையைச் சரிபார்க்காதே"), ("status check pannitiya?", "நிலையைச் சரிபார்த்தாயா?"), ("status check panna mudiyuma?", "நிலையைச் சரிபார்க்க முடியுமா?")),
    extended_scene("check_files", "CHECK", "FileRef", "FILES", FILE_OBJECTS, "file_type", FILE_SHAPES, ("status check pannu", "நிலையைச் சரிபார்"), ("status check pannadha", "நிலையைச் சரிபார்க்காதே"), ("status check pannitiya?", "நிலையைச் சரிபார்த்தாயா?"), ("status check panna mudiyuma?", "நிலையைச் சரிபார்க்க முடியுமா?")),
    extended_scene("check_system", "CHECK", "SystemStatusRef", "PC", (("battery status ah", "மின்கல நிலையை", "battery"), ("network status ah", "இணைய நிலையை", "network"), ("memory status ah", "நினைவக நிலையை", "memory"), ("disk status ah", "வட்டு நிலையை", "disk")), "resource_type", (("{object} {verb}", "{object} {verb}"), ("{workspace} {object} {verb}", "{workspace} {object} {verb}")), ("check pannu", "சரிபார்"), ("check pannadha", "சரிபார்க்காதே"), ("check pannitiya?", "சரிபார்த்தாயா?"), ("check panna mudiyuma?", "சரிபார்க்க முடியுமா?")),
    extended_scene("tell_answer", "PROVIDE", "AnswerRef", "GENERAL", (("answer ah", "பதிலை", "answer"), ("details ah", "விவரங்களை", "details"), ("number ah", "எண்ணை", "number")), "resource_type", (("{object} {verb}", "{object} {verb}"), ("{project} pathi {object} {verb}", "{project} பற்றி {object} {verb}")), ("sollu", "சொல்"), ("solladha", "சொல்லாதே"), ("sonniya?", "சொன்னாயா?"), ("solla mudiyuma?", "சொல்ல முடியுமா?")),
    extended_scene("tell_reason", "EXPLAIN", "TextResource", "GENERAL", (("error reason ah", "பிழைக்கான காரணத்தை", "error_reason"), ("bug reason ah", "பிழையின் காரணத்தை", "bug_reason"), ("meaning ah", "அர்த்தத்தை", "meaning")), "resource_type", (("{object} {verb}", "{object} {verb}"), ("{project} la {object} {verb}", "{project} இல் {object} {verb}")), ("sollu", "சொல்"), ("solladha", "சொல்லாதே"), ("sonniya?", "சொன்னாயா?"), ("solla mudiyuma?", "சொல்ல முடியுமா?")),
    extended_scene("tell_message", "READ", "MessageRef", "MESSAGES", MESSAGE_OBJECTS, "resource_type", FILE_SHAPES, ("sollu", "சொல்"), ("solladha", "சொல்லாதே"), ("sonniya?", "சொன்னாயா?"), ("solla mudiyuma?", "சொல்ல முடியுமா?")),
])

OPTIONS = {
    "recipient": [(n[0] + " ku", n[2], n[0]) for n in NAMES],
    "sender": [(n[0], n[1], n[0]) for n in NAMES],
    "ordinal": ORDINALS,
    "date": DATES,
    "destination": FORMATS,
    "device": DEVICES,
    "browser": BROWSERS,
    "page": PAGES,
    "number": [(str(n), str(n), n) for n in range(10, 101, 10)],
    "time": TIMES,
    "upload_destination": UPLOAD_TARGETS,
    "folder_destination": FOLDERS,
    "project": PROJECTS,
    "application": APPS,
    "style": STYLES,
    "source": DATA_SOURCES,
    "workspace": [("desktop la", "டெஸ்க்டாப்பில்", "desktop"), ("laptop la", "லேப்டாப்பில்", "laptop"), ("office PC la", "அலுவலக கணினியில்", "office_pc"), ("indha system la", "இந்த கணினியில்", "current_pc")],
    "phone_line": [("phone la", "போனில்", "phone"), ("mobile la", "மொபைலில்", "mobile"), ("primary SIM la", "முதன்மை சிம்மில்", "primary_sim"), ("second SIM la", "இரண்டாம் சிம்மில்", "secondary_sim")],
}
SLOT_FOR = {"recipient": "recipient", "sender": "sender", "ordinal": "ordinal", "date": "date", "destination": "destination", "device": "device", "browser": "browser", "page": "browser_tab", "number": "number", "time": "time", "upload_destination": "destination", "folder_destination": "destination", "project": "project", "application": "application", "style": "destination", "source": "source", "workspace": "device", "phone_line": "device"}
STATEMENT_VERBS = {
    "SEND": ("anupinen", "அனுப்பினேன்"), "SHOW": ("kaatinen", "காட்டினேன்"),
    "SELECT": ("eduthen", "எடுத்தேன்"), "CONVERT": ("maathinen", "மாற்றினேன்"),
    "READ": ("paathen", "பார்த்தேன்"), "FORWARD": ("forward panninen", "முன்னனுப்பினேன்"),
    "RUN": ("run panninen", "இயக்கினேன்"), "CHECK": ("check panninen", "சரிபார்த்தேன்"),
    "SET": ("poten", "வைத்தேன்"), "SWITCH": ("maathinen", "மாறினேன்"),
    "OPEN": ("open panninen", "திறந்தேன்"), "PLAY": ("poten", "போட்டேன்"),
    "CREATE": ("poten", "போட்டேன்"), "SUMMARIZE": ("summary kuduthen", "சுருக்கம் கொடுத்தேன்"),
    "NAVIGATE": ("ponen", "போனேன்"), "UPLOAD": ("upload panninen", "பதிவேற்றினேன்"),
    "COPY": ("copy panninen", "நகலெடுத்தேன்"), "CAPTURE": ("eduthen", "எடுத்தேன்"),
    "INCREASE": ("increase panninen", "கூட்டினேன்"), "LIST": ("kaatinen", "காட்டினேன்"),
    "DELETE": ("delete panninen", "அழித்தேன்"),
    "MOVE": ("maathinen", "மாற்றினேன்"), "CHANGE": ("maathinen", "மாற்றினேன்"),
    "RETRIEVE": ("eduthen", "எடுத்தேன்"),
}
SPEECH_WEIGHTS = {"COMMAND": 5, "NEGATED_COMMAND": 2, "STATUS_QUERY": 2, "CAPABILITY_QUERY": 1, "HYPOTHETICAL": 1, "STATEMENT": 2}


def make_pair(scene: Scenario, template_index: int, speech: str, values: dict[str, tuple[str, str, object]], serial: int) -> Pair:
    templates = scene.templates[template_index]
    verb = (("kaatinen", "காட்டினேன்") if scene.key == "navigate_page_show" else STATEMENT_VERBS[scene.action]) if speech == "STATEMENT" else scene.verbs[speech]
    for language_idx in (0, 1):
        for key in re.findall(r"\{(\w+)\}", templates[language_idx]):
            if key not in values and key != "verb":
                raise ValueError(f"Missing {key} in {scene.key}")
    tanglish = templates[0].format(**{k: v[0] for k, v in values.items()}, verb=verb[0])
    tamil = templates[1].format(**{k: v[1] for k, v in values.items()}, verb=verb[1])
    used = set(re.findall(r"\{(\w+)\}", templates[0])) - {"verb"}
    slots = tuple((scene.object_slot if k == "object" else SLOT_FOR[k], values[k][0], values[k][1], values[k][2]) for k in values if k in used)
    return Pair(f"{scene.key}:{template_index}:{speech}:{serial}", tanglish, tamil, speech, scene.action, scene.object_type, slots, negated=speech == "NEGATED_COMMAND")


def generate_scene(scene: Scenario, rng: random.Random) -> list[tuple[dict, dict, str]]:
    results = []
    seen = set()
    attempts = 0
    while len(results) < scene.quota and attempts < scene.quota * 100:
        attempts += 1
        template_index = rng.randrange(len(scene.templates))
        speech_choices = [item for speech, weight in SPEECH_WEIGHTS.items() if speech in scene.verbs or (speech == "STATEMENT" and scene.action in STATEMENT_VERBS) for item in [speech] * weight]
        speech = rng.choice(speech_choices)
        template = scene.templates[template_index][0]
        keys = set(re.findall(r"\{(\w+)\}", template)) - {"verb"}
        values = {"object": rng.choice(scene.objects)}
        for key in sorted(keys - {"object"}):
            choices = OPTIONS[key]
            if key == "date":
                if speech == "STATEMENT":
                    choices = [x for x in DATES if x[2] in {"yesterday", "today", "last_week"}]
                elif scene.key in {"send_file", "show_file", "select_file", "convert_file", "read_message", "forward_message", "summarize_chat", "upload_file", "copy_file", "list_files", "delete_file"}:
                    choices = [x for x in DATES if x[2] in {"yesterday", "today", "last_week", "this_week"}]
                elif scene.key == "create_event":
                    choices = [x for x in DATES if x[2] in {"today", "tomorrow", "this_week"}]
                elif scene.key in {"run_project", "open_app", "play_song", "set_volume", "create_folder", "capture_screen"}:
                    choices = [x for x in DATES if x[2] == "today"]
            values[key] = rng.choice(choices)
        if scene.key == "send_file" and speech == "CAPABILITY_QUERY":
            continue  # recipient + resource is commonly a polite request, not a pure ability question
        if scene.key == "convert_file" and values.get("destination", (None, None, None))[2] == values["object"][2]:
            continue
        if "sender" in values and "recipient" in values and values["sender"][2] == values["recipient"][2]:
            continue
        pair = make_pair(scene, template_index, speech, values, attempts)
        key = (pair.tanglish.casefold(), pair.tamil.casefold())
        if key in seen:
            continue
        seen.add(key)
        left, right = build_row(pair, "TANGLISH"), build_row(pair, "TAMIL")
        family = f"{scene.key}:{template_index}:{speech}:{','.join(sorted(keys))}"
        for row in (left, right):
            row["isolation_group"] = family
            row["frame"]["domain"] = scene.domain
            row["generation_family"] = scene.key
            row["construction_family"] = family
        results.append((left, right, family))
    return results


def correction_rows(rng: random.Random, count: int = 1400) -> list[tuple[dict, dict, str]]:
    rows = []
    seen = set()
    for serial in range(count * 15):
        old, new = rng.sample(NAMES, 2)
        obj = rng.choice(FILE_OBJECTS)
        ordinal = rng.choice(ORDINALS)
        date = rng.choice(DATES)
        shape = serial % 4
        if shape == 0:
            tan = f"{obj[0]} {old[0]} ku anuppu... illa {new[0]} ku"
            tam = f"{obj[1]} {old[2]} அனுப்பு... இல்லை {new[2]}"
            slots = (("file_type", obj[0], obj[1], obj[2]), ("recipient", new[0], new[2], new[0]))
        elif shape == 1:
            tan = f"{ordinal[0]} {obj[0]} {old[0]} ku... sorry {new[0]} ku anuppu"
            tam = f"{ordinal[1]} {obj[1]} {old[2]}... மன்னிக்கவும் {new[2]} அனுப்பு"
            slots = (("ordinal", ordinal[0], ordinal[1], ordinal[2]), ("file_type", obj[0], obj[1], obj[2]), ("recipient", new[0], new[2], new[0]))
        elif shape == 2:
            tan = f"{date[0]} vandha {obj[0]} {old[0]} ku... illa {new[0]} ku anuppu"
            tam = f"{date[1]} வந்த {obj[1]} {old[2]}... இல்லை {new[2]} அனுப்பு"
            slots = (("date", date[0], date[1], date[2]), ("file_type", obj[0], obj[1], obj[2]), ("recipient", new[0], new[2], new[0]))
        else:
            tan = f"{old[0]} ku venam, {new[0]} ku {ordinal[0]} {obj[0]} anuppu"
            tam = f"{old[2]} வேண்டாம், {new[2]} {ordinal[1]} {obj[1]} அனுப்பு"
            slots = (("recipient", new[0], new[2], new[0]), ("ordinal", ordinal[0], ordinal[1], ordinal[2]), ("file_type", obj[0], obj[1], obj[2]))
        if (tan, tam) in seen:
            continue
        seen.add((tan, tam))
        pair = Pair(f"correction_send:{serial}", tan, tam, "CORRECTION", "SEND", "FileRef", slots, superseded=("recipient", old[0], old[2], old[0]))
        left, right = build_row(pair, "TANGLISH"), build_row(pair, "TAMIL")
        for row in (left, right):
            row["isolation_group"] = f"correction_send:{shape}"
            row["frame"]["domain"] = "FILES"
            row["generation_family"] = "correction_send"
            row["construction_family"] = f"correction_send:{shape}"
        rows.append((left, right, f"correction_send:{shape}"))
        if len(rows) >= count:
            break
    return rows


def rebalanced_correction_rows(rng: random.Random, per_kind: int = 150) -> list[tuple[dict, dict, str]]:
    """Corrections with active and superseded values across six slot types."""
    pairs: list[tuple[Pair, str]] = []
    seen = set()
    for kind in ("recipient", "file_type", "application", "time", "number", "destination"):
        made = 0
        attempts = 0
        while made < per_kind and attempts < per_kind * 100:
            attempts += 1
            name = rng.choice(NAMES)
            obj = rng.choice(FILE_OBJECTS)
            ordinal = rng.choice(ORDINALS)
            if kind == "recipient":
                old, new = rng.sample(NAMES, 2)
                tan = f"{ordinal[0]} {obj[0]} {old[0]} ku... illa {new[0]} ku anuppu"
                tam = f"{ordinal[1]} {obj[1]} {old[2]}... இல்லை {new[2]} அனுப்பு"
                slots = (("ordinal", ordinal[0], ordinal[1], ordinal[2]), ("file_type", obj[0], obj[1], obj[2]), ("recipient", new[0], new[2], new[0]))
                old_slot = ("recipient", old[0], old[2], old[0])
                action, obj_type = "SEND", "FileRef"
            elif kind == "file_type":
                old, new = rng.sample(FILE_OBJECTS, 2)
                tan = f"{name[0]} oda {old[0]}... illa {new[0]} kaatu"
                tam = f"{name[1]} அனுப்பிய {old[1]}... இல்லை {new[1]} காட்டு"
                slots = (("sender", name[0], name[1], name[0]), ("file_type", new[0], new[1], new[2]))
                old_slot = ("file_type", old[0], old[1], old[2])
                action, obj_type = "SHOW", "FileRef"
            elif kind == "application":
                old, new = rng.sample(APPS, 2)
                workspace = rng.choice(OPTIONS["workspace"])
                tan = f"{workspace[0]} {old[0]} ah... sorry {new[0]} ah open pannu"
                tam = f"{workspace[1]} {old[1]} ஐ... இல்லை {new[1]} ஐ திற"
                slots = (("device", workspace[0], workspace[1], workspace[2]), ("application", new[0], new[1], new[2]))
                old_slot = ("application", old[0], old[1], old[2])
                action, obj_type = "OPEN", "AppRef"
            elif kind == "time":
                old, new = rng.sample(TIMES, 2)
                event = rng.choice(EVENTS)
                date = rng.choice(DATES[1:3])
                tan = f"{date[0]} {event[0]} {old[0]}... illa {new[0]} calendar la podu"
                tam = f"{date[1]} {event[1]} {old[1]}... இல்லை {new[1]} காலெண்டரில் போடு"
                slots = (("date", date[0], date[1], date[2]), ("resource_type", event[0], event[1], event[2]), ("time", new[0], new[1], new[2]))
                old_slot = ("time", old[0], old[1], old[2])
                action, obj_type = "CREATE", "CalendarEventRef"
            elif kind == "number":
                old, new = rng.sample(OPTIONS["number"][:-1], 2)
                device = rng.choice(DEVICES)
                tan = f"{device[0]} volume {old[0]}... illa {new[0]} ku podu"
                tam = f"{device[1]} ஒலியை {old[1]}... இல்லை {new[1]}க்கு வை"
                slots = (("device", device[0], device[1], device[2]), ("number", new[0], new[1], new[2]))
                old_slot = ("number", old[0], old[1], old[2])
                action, obj_type = "SET", "Volume"
            else:
                old, new = rng.sample(FOLDERS, 2)
                tan = f"{ordinal[0]} {obj[0]} {old[0]}... illa {new[0]} move pannu"
                tam = f"{ordinal[1]} {obj[1]} {old[1]}... இல்லை {new[1]} நகர்த்து"
                slots = (("ordinal", ordinal[0], ordinal[1], ordinal[2]), ("file_type", obj[0], obj[1], obj[2]), ("destination", new[0], new[1], new[2]))
                old_slot = ("destination", old[0], old[1], old[2])
                action, obj_type = "MOVE", "FileRef"
            if (tan, tam) in seen:
                continue
            seen.add((tan, tam))
            pair = Pair(f"correction_{kind}:{made}", tan, tam, "CORRECTION", action, obj_type, slots, superseded=old_slot)
            pairs.append((pair, f"correction_{kind}"))
            made += 1
        if made < per_kind:
            raise RuntimeError(f"Could generate only {made} corrections for {kind}")
    results = []
    for pair, group in pairs:
        left, right = build_row(pair, "TANGLISH"), build_row(pair, "TAMIL")
        for row in (left, right):
            row["generation_family"] = group
            row["construction_family"] = group + ":" + str(int(pair.family.rsplit(":", 1)[-1]) % 12)
            row["isolation_group"] = row["construction_family"]
        results.append((left, right, group))
    return results


def context_rows(rng: random.Random, count: int = 1800) -> list[tuple[dict, dict, str]]:
    rows = []
    seen = set()
    for serial in range(count * 12):
        sender, recipient = rng.sample(NAMES, 2)
        obj = rng.choice(FILE_OBJECTS)
        ordinal = rng.choice(ORDINALS)
        date = rng.choice(DATES)
        shape = serial % 8
        tan = [
            f"atha {recipient[0]} ku anuppu", f"{recipient[0]} ku atha anuppu",
            f"antha {ordinal[0]} one ah {recipient[0]} ku anuppu",
            f"selected file ah {recipient[0]} ku anuppu", f"athaye {recipient[0]} ku anuppidu",
            f"munnadi eduthatha {recipient[0]} ku anuppu", f"same file ah {recipient[0]} ku anuppu",
            f"{recipient[0]} ku antha file ah anuppu",
        ][shape]
        tam = [
            f"அதை {recipient[2]} அனுப்பு", f"{recipient[2]} அதை அனுப்பு",
            f"அந்த {ordinal[1]} ஒன்றை {recipient[2]} அனுப்பு",
            f"தேர்ந்தெடுத்த கோப்பை {recipient[2]} அனுப்பு", f"அதையே {recipient[2]} அனுப்பு",
            f"முன்னாடி எடுத்ததை {recipient[2]} அனுப்பு", f"அதே கோப்பை {recipient[2]} அனுப்பு",
            f"{recipient[2]} அந்த கோப்பை அனுப்பு",
        ][shape]
        key = (tan, tam, sender[0], obj[2], ordinal[2], date[2])
        if key in seen:
            continue
        seen.add(key)
        slots = [("recipient", recipient[0], recipient[2], recipient[0])]
        if shape == 2:
            slots.append(("ordinal", ordinal[0], ordinal[1], ordinal[2]))
        context = {"selected_resource": {"type": "FileRef", "file_type": obj[2], "sender": sender[0], "ordinal": ordinal[2], "date": date[2]}, "previous_turns": {"TANGLISH": [f"{date[0]} {sender[0]} anupuna {obj[0]} kaatu", f"{ordinal[0]} one"], "TAMIL": [f"{date[1]} {sender[1]} அனுப்பிய {obj[1]} காட்டு", ordinal[1]]}}
        pair = Pair(f"context_send:{serial}", tan, tam, "COMMAND", "SEND", "FileRef", tuple(slots), context_required=True, working_context=context)
        left, right = build_row(pair, "TANGLISH"), build_row(pair, "TAMIL")
        for row in (left, right):
            row["isolation_group"] = f"context_send:{shape}"
            row["frame"]["domain"] = "FILES"
            row["generation_family"] = "context_send"
            row["construction_family"] = f"context_send:{shape}"
        rows.append((left, right, f"context_send:{shape}"))
        if len(rows) >= count:
            break
    return rows


def special_rows(rng: random.Random) -> list[tuple[dict, dict, str]]:
    """Small independently specified speech and grounding contrasts."""
    pairs: list[tuple[Pair, str]] = []
    for project in PROJECTS:
        pairs.extend([
            (Pair(f"question_meaning:{project[2]}", f"{project[0]} nu sonna enna artham?", f"{project[1]} என்றால் என்ன அர்த்தம்?", "QUESTION", None, None, (("project", project[0], project[1], project[2]),)), "question_meaning"),
            (Pair(f"ack_project:{project[2]}", f"seri, {project[0]} pathi purinjiduchu", f"சரி, {project[1]} பற்றி புரிஞ்சுது", "ACKNOWLEDGEMENT", None, None, (("project", project[0], project[1], project[2]),)), "ack_project"),
            (Pair(f"confirm_project:{project[2]}", f"aama, {project[0]} than", f"ஆமாம், {project[1]} தான்", "CONFIRMATION", None, None, (("project", project[0], project[1], project[2]),)), "confirm_project"),
        ])
    for name in NAMES:
        pairs.append((Pair(f"chat_contact:{name[0]}", f"{name[0]} epdi irukaru?", f"{name[1]} எப்படி இருக்கிறார்?", "CHAT", None, None, (("contact", name[0], name[1], name[0]),)), "chat_contact"))
    for obj in FILE_OBJECTS:
        pairs.extend([
            (Pair(f"ambiguous_send:{obj[2]}", f"{obj[0]} anupa mudiyuma?", f"{obj[1]} அனுப்ப முடியுமா?", "AMBIGUOUS", "SEND", "FileRef", (("file_type", obj[0], obj[1], obj[2]),)), "ambiguous_send"),
            (Pair(f"capability_send:{obj[2]}", f"unakku {obj[0]} anupa capability iruka?", f"உனக்கு {obj[1]} அனுப்பும் வசதி இருக்கா?", "CAPABILITY_QUERY", "SEND", "FileRef", (("file_type", obj[0], obj[1], obj[2]),)), "capability_send"),
        ])
        for name in NAMES:
            pairs.append((Pair(f"ambiguous_recipient:{obj[2]}:{name[0]}", f"{obj[0]} {name[0]} ku anupa mudiyuma?", f"{obj[1]} {name[2]} அனுப்ப முடியுமா?", "AMBIGUOUS", "SEND", "FileRef", (("file_type", obj[0], obj[1], obj[2]), ("recipient", name[0], name[2], name[0]))), "ambiguous_recipient"))
    capability_forms = {
        "SHOW": ("kaata mudiyuma?", "காட்ட முடியுமா?"),
        "SELECT": ("edukka mudiyuma?", "எடுக்க முடியுமா?"),
        "CONVERT": ("maatha mudiyuma?", "மாற்ற முடியுமா?"),
        "READ": ("padikka mudiyuma?", "படிக்க முடியுமா?"),
        "FORWARD": ("forward panna mudiyuma?", "முன்னனுப்ப முடியுமா?"),
        "RUN": ("run panna mudiyuma?", "இயக்க முடியுமா?"),
        "CHECK": ("check panna mudiyuma?", "சரிபார்க்க முடியுமா?"),
        "OPEN": ("open panna mudiyuma?", "திறக்க முடியுமா?"),
        "NAVIGATE": ("poga mudiyuma?", "போக முடியுமா?"),
        "UPLOAD": ("upload panna mudiyuma?", "பதிவேற்ற முடியுமா?"),
        "COPY": ("copy panna mudiyuma?", "நகலெடுக்க முடியுமா?"),
        "CREATE": ("create panna mudiyuma?", "உருவாக்க முடியுமா?"),
        "CAPTURE": ("edukka mudiyuma?", "எடுக்க முடியுமா?"),
        "DELETE": ("delete panna mudiyuma?", "அழிக்க முடியுமா?"),
    }
    for scene in SCENARIOS:
        forms = capability_forms.get(scene.action)
        if scene.key == "navigate_page_show":
            forms = ("kaata mudiyuma?", "காட்ட முடியுமா?")
        if not forms:
            continue
        for obj in scene.objects:
            pairs.append((Pair(f"capability_scene:{scene.key}:{obj[2]}", f"unakku {obj[0]} {forms[0]}", f"உன்னால் {obj[1]} {forms[1]}", "CAPABILITY_QUERY", scene.action, scene.object_type, ((scene.object_slot, obj[0], obj[1], obj[2]),)), "capability_scene:" + scene.key))
    for name in NAMES:
        for obj in FILE_OBJECTS:
            context = {"selected_resource": {"type": "FileRef", "file_type": obj[2]}, "previous_turns": {"TANGLISH": [f"indha {obj[0]} kaatu"], "TAMIL": [f"இந்த {obj[1]} காட்டு"]}}
            pairs.append((Pair(f"polite_grounded:{name[0]}:{obj[2]}", f"indha {obj[0]} {name[0]} ku anupa mudiyuma?", f"இந்த {obj[1]} {name[2]} அனுப்ப முடியுமா?", "COMMAND", "SEND", "FileRef", (("file_type", obj[0], obj[1], obj[2]), ("recipient", name[0], name[2], name[0])), context_required=True, working_context=context), "polite_grounded"))
    for project in PROJECTS:
        context = {"selected_resource": {"type": "WorkflowRef", "project": project[2]}, "previous_turns": {"TANGLISH": [f"{project[0]} build start pannu"], "TAMIL": [f"{project[1]} உருவாக்கத்தை தொடங்கு"]}}
        for shape, (tan, tam) in enumerate((
            ("munnadi sonna velaiya cancel pannu", "முன்னாடி சொன்ன வேலையை ரத்து செய்"),
            ("andha request ah niruthu", "அந்த கோரிக்கையை நிறுத்து"),
            ("last task ah cancel pannu", "கடைசி வேலையை ரத்து செய்"),
            ("athu venam, cancel pannu", "அது வேண்டாம், ரத்து செய்"),
        )):
            pairs.append((Pair(f"meta_cancel:{project[2]}:{shape}", tan, tam, "META_CONTROL", "CANCEL", "WorkflowRef", context_required=True, working_context=context), "meta_cancel:" + str(shape)))
    rows = []
    for pair, group in pairs:
        left, right = build_row(pair, "TANGLISH"), build_row(pair, "TAMIL")
        for row in (left, right):
            row["isolation_group"] = group
            row["generation_family"] = group
            row["construction_family"] = group
            row["frame"]["domain"] = "GENERAL" if pair.action is None else "FILES" if pair.action == "SEND" else "CONTROL" if pair.action == "CANCEL" else "GENERAL"
        rows.append((left, right, group))
    return rows


def slot_coverage_rows() -> list[tuple[dict, dict, str]]:
    """Explicit complex frames for slots absent from the broad grammar."""
    previous = {"selected_resource": {"type": "FileRef", "selector": "current attachment"}, "previous_turns": {"TANGLISH": ["attachment kaatu"], "TAMIL": ["இணைப்பைக் காட்டு"]}}
    pairs = [
        next(p for p in PAIRS if p.family == "send_pdf_yesterday"),
        Pair("slot_search_query", "Atlas error pathi search pannu", "Atlas பிழையைத் தேடு", "COMMAND", "SEARCH", "WebQueryRef", (("query", "Atlas error", "Atlas பிழையைத்", "Atlas error"),)),
        Pair("slot_url", "https://example.com page ku po", "https://example.com பக்கத்துக்கு போ", "COMMAND", "NAVIGATE", "URLRef", (("URL", "https://example.com", "https://example.com", "https://example.com"),)),
        Pair("slot_message_content", "Naveen ku 'seri' nu message anuppu", "நவீனுக்கு 'சரி' என்று செய்தி அனுப்பு", "COMMAND", "SEND", "MessageRef", (("recipient", "Naveen", "நவீனு", "Naveen"), ("message_content", "seri", "சரி", "okay"))),
        Pair("slot_attachment", "indha attachment ah Naveen ku anuppu", "இந்த இணைப்பை நவீனுக்கு அனுப்பு", "COMMAND", "SEND", "FileRef", (("attachment", "attachment", "இணைப்பை", "current_attachment"), ("recipient", "Naveen", "நவீனு", "Naveen")), context_required=True, working_context=previous),
        Pair("slot_file", "budget report file ah open pannu", "பட்ஜெட் அறிக்கை கோப்பை திற", "COMMAND", "OPEN", "FileRef", (("file", "budget report", "பட்ஜெட் அறிக்கை", "budget report"),)),
        Pair("slot_count", "last 3 messages kaatu", "கடைசி 3 செய்திகளைக் காட்டு", "COMMAND", "SHOW", "MessageRef", (("count", "3", "3", 3),)),
        Pair("slot_quantity", "volume konjam kammi pannu", "ஒலியை கொஞ்சம் குறை", "COMMAND", "DECREASE", "Volume", (("quantity", "konjam", "கொஞ்சம்", "small_relative"),)),
        Pair("slot_percentage", "brightness 50% ku maathu", "திரை வெளிச்சத்தை 50% ஆக மாற்று", "COMMAND", "SET", "Brightness", (("percentage", "50%", "50%", 50),)),
        Pair("slot_date_range", "pona vaaram irundhu inniku varaikum messages kaatu", "போன வாரம் முதல் இன்று வரை செய்திகளைக் காட்டு", "COMMAND", "SHOW", "MessageRef", (("date_range", "pona vaaram irundhu inniku varaikum", "போன வாரம் முதல் இன்று வரை", {"from": "last_week", "to": "today"}),)),
        Pair("slot_time_range", "9 mani irundhu 5 mani varaikum calendar events kaatu", "9 மணி முதல் 5 மணி வரை காலெண்டர் நிகழ்வுகளைக் காட்டு", "COMMAND", "LIST", "CalendarEventRef", (("time_range", "9 mani irundhu 5 mani varaikum", "9 மணி முதல் 5 மணி வரை", {"from": "09:00", "to": "17:00"}),)),
        Pair("slot_workflow", "Atlas workflow run pannu", "Atlas பணிச்சுற்றை இயக்கு", "COMMAND", "RUN", "WorkflowRef", (("workflow", "Atlas workflow", "Atlas பணிச்சுற்றை", "Atlas"),)),
        Pair("slot_spatial", "file ah Reports folder kulla podu", "கோப்பை Reports கோப்புறைக்குள் வை", "COMMAND", "MOVE", "FileRef", (("spatial_relation", "folder kulla", "கோப்புறைக்குள்", "inside"), ("folder", "Reports folder", "Reports கோப்புறை", "Reports"))),
        Pair("slot_quoted", "quoted message ah kaatu", "மேற்கோள் செய்தியைக் காட்டு", "COMMAND", "SHOW", "MessageRef", (("quoted_resource", "quoted message", "மேற்கோள் செய்தியை", "quoted_message"),)),
        Pair("slot_include_exclude", "PDF mattum kaatu, screenshot venam", "PDF மட்டும் காட்டு, screenshot வேண்டாம்", "COMMAND", "SHOW", "FileRef", (("include_constraint", "PDF mattum", "PDF மட்டும்", "PDF"), ("exclude_constraint", "screenshot venam", "screenshot வேண்டாம்", "screenshot"))),
    ]
    rows = []
    for pair in pairs:
        left, right = build_row(pair, "TANGLISH"), build_row(pair, "TAMIL")
        for row in (left, right):
            row["isolation_group"] = "slot_coverage:" + pair.family
            row["construction_family"] = "slot_coverage:" + pair.family
            row["generation_family"] = "slot_coverage"
        rows.append((left, right, "slot_coverage:" + pair.family))
    return rows


def rebalanced_slot_rows() -> list[tuple[dict, dict, str]]:
    """Grounded multi-slot constructions for the sparse parts of the schema."""
    pairs: list[tuple[Pair, str]] = []

    def add(group: str, serial: str, tan: str, tam: str, action: str, obj: str, slots: tuple, *, negated: bool = False) -> None:
        pairs.append((Pair(f"rebalance:{group}:{serial}", tan, tam,
                           "NEGATED_COMMAND" if negated else "COMMAND", action, obj,
                           slots, negated=negated), group))

    for i in range(65):
        url = f"https://docs{i}.example.org/guide"
        browser = BROWSERS[i % len(BROWSERS)]
        add("url_navigation", str(i), f"{browser[0]} la {url} open pannu", f"{browser[1]} இல் {url} ஐ திற",
            "NAVIGATE", "URLRef", (("browser", browser[0], browser[1], browser[2]), ("URL", url, url, url)))
        topic = f"Atlas error {i}"
        add("web_query", str(i), f"{topic} pathi web la search pannu", f"{topic} பற்றி இணையத்தில் தேடு",
            "SEARCH", "WebQueryRef", (("query", topic, topic, topic),))
        filename = f"budget_{i:02d}.pdf"
        add("named_file", str(i), f"{filename} file ah open pannu", f"{filename} கோப்பை திற",
            "OPEN", "FileRef", (("file", filename, filename, filename),))

    for i in range(60):
        n = NAMES[i % len(NAMES)]
        obj = FILE_OBJECTS[i % len(FILE_OBJECTS)]
        content = f"status {i}"
        add("message_content", str(i), f"{n[0]} ku '{content}' nu message anuppu", f"{n[2]} '{content}' என்று செய்தி அனுப்பு",
            "SEND", "MessageRef", (("recipient", n[0], n[2], n[0]), ("message_content", content, content, content)))
        add("count_messages", str(i), f"{n[0]} oda last {i + 2} messages kaatu", f"{n[1]} அனுப்பிய கடைசி {i + 2} செய்திகளைக் காட்டு",
            "SHOW", "MessageRef", (("sender", n[0], n[1], n[0]), ("count", str(i + 2), str(i + 2), i + 2)))
        add("quoted_message", str(i), f"{n[0]} oda quoted message {i + 1} kaatu", f"{n[1]} அனுப்பிய மேற்கோள் செய்தி {i + 1} ஐ காட்டு",
            "SHOW", "MessageRef", (("sender", n[0], n[1], n[0]), ("quoted_resource", f"quoted message {i + 1}", f"மேற்கோள் செய்தி {i + 1}", f"quote_{i + 1}")))
        folder = FOLDER_OBJECTS[i % len(FOLDER_OBJECTS)]
        filename = f"document_{i:02d}.pdf"
        add("spatial_move", str(i), f"{filename} {folder[0]} kulla podu", f"{filename} {folder[1]} உள்ளே வை",
            "MOVE", "FileRef", (("file", filename, filename, filename), ("folder", folder[0], folder[1], folder[2]), ("spatial_relation", "kulla", "உள்ளே", "inside")))
        add("contact_summary", str(i), f"{n[0]} oda last {i + 2} messages summary kudu", f"{n[1]} அனுப்பிய கடைசி {i + 2} செய்திகளைச் சுருக்கி கொடு",
            "SUMMARIZE", "MessageRef", (("contact", n[0], n[1], n[0]), ("count", str(i + 2), str(i + 2), i + 2)))

    for i in range(80):
        level = i + 10
        setting = ("brightness", "திரை வெளிச்சத்தை", "brightness") if i % 2 else ("volume", "ஒலியை", "volume")
        add("percentage_setting", str(i), f"{setting[0]} {level}% ku podu", f"{setting[1]} {level}% ஆக வை",
            "SET", "Brightness" if i % 2 else "Volume", (("resource_type", setting[0], setting[1], setting[2]), ("percentage", f"{level}%", f"{level}%", level)))
        relative = [("konjam", "கொஞ்சம்", "small_relative"), ("romba", "ரொம்ப", "large_relative"), ("paadhi", "பாதி", "half"), ("oru padi", "ஒரு படி", "one_step"), ("rendu padi", "இரண்டு படி", "two_steps")][i % 5]
        act = "DECREASE" if i % 2 else "INCREASE"
        verb = ("kammi pannu", "குறை") if act == "DECREASE" else ("adhigam pannu", "கூட்டு")
        device = [("phone la", "போனில்", "phone"), ("laptop la", "லேப்டாப்பில்", "laptop")][i % 2] if i % 2 else DEVICES[(i // 2) % len(DEVICES)]
        when = [("ippo", "இப்போ"), ("inniku", "இன்று"), ("konja nerathula", "கொஞ்ச நேரத்தில்")][(i // 10) % 3]
        add("relative_quantity", str(i), f"{when[0]} {device[0]} {setting[0]} {relative[0]} {verb[0]}", f"{when[1]} {device[1]} {setting[1]} {relative[1]} {verb[1]}",
            act, "Brightness" if i % 2 else "Volume", (("device", device[0], device[1], device[2]), ("resource_type", setting[0], setting[1], setting[2]), ("quantity", relative[0], relative[1], relative[2])))

    for i in range(80):
        n = NAMES[i % len(NAMES)]
        start_day = i % 25 + 1
        end_day = start_day + 2
        tan_range = f"2026-09-{start_day:02d} lendhu 2026-09-{end_day:02d} varaikum"
        tam_range = f"2026-09-{start_day:02d} முதல் 2026-09-{end_day:02d} வரை"
        add("date_range_messages", str(i), f"{n[0]} oda {tan_range} messages kaatu", f"{n[1]} அனுப்பிய {tam_range} செய்திகளைக் காட்டு",
            "SHOW", "MessageRef", (("sender", n[0], n[1], n[0]), ("date_range", tan_range, tam_range, {"from": f"2026-09-{start_day:02d}", "to": f"2026-09-{end_day:02d}"})))
        hour = 7 + i % 11
        until = min(hour + 2, 21)
        tan_time = f"{hour} mani irundhu {until} mani varaikum"
        tam_time = f"{hour} மணி முதல் {until} மணி வரை"
        project = PROJECTS[i % len(PROJECTS)]
        add("time_range_events", str(i), f"{project[0]} {tan_time} calendar events kaatu", f"{project[1]} {tam_time} காலெண்டர் நிகழ்வுகளைக் காட்டு",
            "LIST", "CalendarEventRef", (("project", project[0], project[1], project[2]), ("time_range", tan_time, tam_time, {"from": f"{hour:02d}:00", "to": f"{until:02d}:00"})))
        obj = FILE_OBJECTS[i % len(FILE_OBJECTS)]
        excluded = ("screenshot", "screenshot", "screenshot") if i >= 30 else ("draft", "வரைவு", "draft")
        add("file_constraints", str(i), f"{n[0]} oda {obj[0]} mattum kaatu, {excluded[0]} venam", f"{n[1]} அனுப்பிய {obj[1]} மட்டும் காட்டு, {excluded[1]} வேண்டாம்",
            "SHOW", "FileRef", (("sender", n[0], n[1], n[0]), ("include_constraint", obj[0] + " mattum", obj[1] + " மட்டும்", obj[2]), ("exclude_constraint", excluded[0] + " venam", excluded[1] + " வேண்டாம்", excluded[2])))
        attachment_name = f"attachment_{i:02d}.pdf"
        add("attachment_draft", str(i), f"{project[0]} draft mail la {n[0]} ku {attachment_name} attachment ah attach pannu", f"{project[1]} வரைவு மின்னஞ்சலில் {n[2]} {attachment_name} இணைப்பாக சேர்",
            "ATTACH", "FileRef", (("project", project[0], project[1], project[2]), ("recipient", n[0], n[2], n[0]), ("file", attachment_name, attachment_name, attachment_name), ("attachment", "attachment", "இணைப்பாக", attachment_name)))
        add("workflow_run", str(i), f"{project[0]} workflow ah {i + 1} thadava run pannu", f"{project[1]} பணிச்சுற்றை {i + 1} முறை இயக்கு",
            "RUN", "WorkflowRef", (("workflow", project[0] + " workflow", project[1] + " பணிச்சுற்றை", project[2]), ("count", str(i + 1), str(i + 1), i + 1)))

    results = []
    for pair, group in pairs:
        left, right = build_row(pair, "TANGLISH"), build_row(pair, "TAMIL")
        for row in (left, right):
            row["generation_family"] = group
            row["construction_family"] = group + ":" + str(int(pair.family.rsplit(":", 1)[-1]) % 8)
            row["isolation_group"] = row["construction_family"]
        results.append((left, right, group))
    return results


def rebalanced_action_rows() -> list[tuple[dict, dict, str]]:
    """Semantically distinct actions that need a named destination or input."""
    pairs: list[tuple[Pair, str]] = []
    for i in range(100):
        name = NAMES[i % len(NAMES)]
        obj = FILE_OBJECTS[i % len(FILE_OBJECTS)]
        project = PROJECTS[(i // len(NAMES)) % len(PROJECTS)]
        filename = f"report_{i:02d}.pdf"
        new_name = f"final_{i:02d}.pdf"
        pairs.append((Pair(f"rename_file:{i}", f"{filename} file ah {new_name} nu rename pannu", f"{filename} கோப்பை {new_name} என்று பெயர் மாற்று",
            "COMMAND", "RENAME", "FileRef", (("file", filename, filename, filename), ("destination", new_name, new_name, new_name))), "rename_file"))
        old = NAMES[i % len(NAMES)]
        new = NAMES[(i // 10 + i % 10 + 1) % len(NAMES)]
        if old[0] == new[0]:
            new = NAMES[(i + 1) % len(NAMES)]
        pairs.append((Pair(f"replace_text:{i}", f"{project[0]} note la {old[0]} ah {new[0]} nu replace pannu", f"{project[1]} குறிப்பில் {old[1]} ஐ {new[1]} ஆக மாற்று",
            "COMMAND", "REPLACE", "TextResource", (("project", project[0], project[1], project[2]), ("contact", old[0], old[1], old[0]), ("recipient", new[0], new[1], new[0]))), "replace_text"))
        content = f"code {i:03d}"
        pairs.append((Pair(f"enter_text:{i}", f"{project[0]} form la '{content}' type pannu", f"{project[1]} படிவத்தில் '{content}' ஐ உள்ளிடு",
            "COMMAND", "ENTER", "TextResource", (("project", project[0], project[1], project[2]), ("message_content", content, content, content))), "enter_text"))
        media = [("call", "அழைப்பை", "call"), ("meeting", "சந்திப்பை", "meeting"), ("song", "பாடலை", "song"), ("video", "காணொளியை", "video")][i % 4]
        device = DEVICES[(i // 4) % len(DEVICES)]
        for action, tan_verb, tam_verb in (("MUTE", "mute pannu", "ஒலியை முடக்கு"), ("UNMUTE", "unmute pannu", "ஒலியை இயக்கு")):
            pairs.append((Pair(f"{action.lower()}_media:{i}", f"{device[0]} {project[0]} {media[0]} audio {tan_verb}", f"{device[1]} {project[1]} {media[1]} {tam_verb}",
                "COMMAND", action, "Volume", (("device", device[0], device[1], device[2]), ("project", project[0], project[1], project[2]), ("resource_type", media[0], media[1], media[2]))), action.lower() + "_media"))
    results = []
    for pair, group in pairs:
        left, right = build_row(pair, "TANGLISH"), build_row(pair, "TAMIL")
        for row in (left, right):
            row["generation_family"] = group
            row["construction_family"] = group + ":" + str(int(pair.family.rsplit(":", 1)[-1]) % 10)
            row["isolation_group"] = row["construction_family"]
        results.append((left, right, group))
    return results


def rebalanced_context_rows(rng: random.Random, count: int = 1100) -> list[tuple[dict, dict, str]]:
    """Typed selected-file references spread across several action senses."""
    forms = (
        ("SHOW", "kaatu", "காட்டு", "FileRef"),
        ("OPEN", "open pannu", "திற", "FileRef"),
        ("DELETE", "delete pannu", "அழி", "FileRef"),
        ("READ", "paaru", "பாரு", "FileRef"),
        ("SAVE", "save pannu", "சேமி", "FileRef"),
    )
    rows = []
    seen = set()
    for attempt in range(count * 30):
        action, tan_verb, tam_verb, obj_type = forms[attempt % len(forms)]
        sender = rng.choice(NAMES)
        obj = rng.choice(FILE_OBJECTS)
        ordinal = rng.choice(ORDINALS)
        date = rng.choice(DATES)
        shape = (attempt // len(forms)) % 5
        tan_obj = ("atha", "antha file ah", "previous one ah", "selected file ah", "ithaye")[shape]
        tam_obj = ("அதை", "அந்த கோப்பை", "முந்தையதை", "தேர்ந்தெடுத்த கோப்பை", "இதையே")[shape]
        tan = f"{tan_obj} {tan_verb}"
        tam = f"{tam_obj} {tam_verb}"
        key = (action, tan, sender[0], obj[2], ordinal[2], date[2])
        if key in seen:
            continue
        seen.add(key)
        context = {"selected_resource": {"type": "FileRef", "file_type": obj[2], "sender": sender[0], "ordinal": ordinal[2], "date": date[2]},
                   "previous_turns": {"TANGLISH": [f"{date[0]} {sender[0]} anupuna {obj[0]} kaatu", f"{ordinal[0]} one"],
                                      "TAMIL": [f"{date[1]} {sender[1]} அனுப்பிய {obj[1]} காட்டு", ordinal[1]]}}
        pair = Pair(f"context_{action.lower()}:{attempt}", tan, tam, "COMMAND", action, obj_type,
                    context_required=True, working_context=context)
        left, right = build_row(pair, "TANGLISH"), build_row(pair, "TAMIL")
        group = f"context_{action.lower()}:{shape}"
        for row in (left, right):
            row["generation_family"] = "context_" + action.lower()
            row["construction_family"] = group
            row["isolation_group"] = group
        rows.append((left, right, group))
        if len(rows) >= count:
            break
    return rows


def typed_context_rows() -> list[tuple[dict, dict, str]]:
    """Ellipsis grounded in thread, app, project, tab and prior-result context."""
    kinds = (
        ("active_thread", "MessageRef", "SUMMARIZE", "MessageRef", "indha chat summary kudu", "இந்த உரையாடலைச் சுருக்கி கொடு", "indha chat summary kudukadha", "இந்த உரையாடலைச் சுருக்கி கொடுக்காதே"),
        ("active_app", "AppRef", "CLOSE", "AppRef", "current app ah close pannu", "தற்போதைய செயலியை மூடு", "current app ah close pannadha", "தற்போதைய செயலியை மூடாதே"),
        ("current_project", "ProjectRef", "RESTART", "ProjectRef", "indha project restart pannu", "இந்தத் திட்டத்தை மறுதொடக்கம் செய்", "indha project restart pannadha", "இந்தத் திட்டத்தை மறுதொடக்கம் செய்யாதே"),
        ("browser_tab", "BrowserTabRef", "SWITCH", "BrowserTabRef", "andha tab ku maathu", "அந்த டேபுக்கு மாறு", "andha tab ku maathadha", "அந்த டேபுக்கு மாறாதே"),
        ("previous_result", "FileRef", "OPEN", "FileRef", "last result ah open pannu", "கடைசி முடிவை திற", "last result ah open pannadha", "கடைசி முடிவை திறக்காதே"),
    )
    results = []
    for kind, ref_type, action, object_type, tan_yes, tam_yes, tan_no, tam_no in kinds:
        for i in range(100):
            project = PROJECTS[i % len(PROJECTS)]
            obj = FILE_OBJECTS[(i // len(PROJECTS)) % len(FILE_OBJECTS)]
            n = NAMES[i % len(NAMES)]
            selector = {"type": ref_type, "project": project[2], "file_type": obj[2], "contact": n[0], "ordinal": i % 5 + 1}
            previous = {"TANGLISH": [f"{project[0]} {obj[0]} kaatu", f"{i % 5 + 1}th one"],
                        "TAMIL": [f"{project[1]} {obj[1]} காட்டு", f"{i % 5 + 1}வது"]}
            context = {kind: selector, "previous_turns": previous}
            negated = i % 5 == 0
            pair = Pair(f"typed_context:{kind}:{i}", tan_no if negated else tan_yes,
                        tam_no if negated else tam_yes, "NEGATED_COMMAND" if negated else "COMMAND",
                        action, object_type, negated=negated, context_required=True,
                        working_context=context, context_key=kind)
            left, right = build_row(pair, "TANGLISH"), build_row(pair, "TAMIL")
            group = f"typed_context:{kind}:{i % 10}"
            for row in (left, right):
                row["generation_family"] = "typed_context_" + kind
                row["construction_family"] = group
                row["isolation_group"] = group
            results.append((left, right, group))
    return results


def metalinguistic_rows(pairs: list[tuple[dict, dict, str]], count: int = 300) -> list[tuple[dict, dict, str]]:
    """Action words inside questions and counterfactuals must not trigger tools."""
    by_action = defaultdict(list)
    for left, right, _ in pairs:
        if left["frame"]["speech_act"] == "COMMAND" and left["frame"]["action_concept"] is not None:
            by_action[left["frame"]["action_concept"]].append((left, right))
    for action in by_action:
        by_action[action].sort(key=lambda pair: hashlib.sha256(pair[0]["id"].encode()).hexdigest())
    selected = []
    for index in range(count):
        available = [(action, group[index // len(by_action)]) for action, group in sorted(by_action.items()) if index // len(by_action) < len(group)]
        if not available:
            break
        selected.append(available[index % len(available)][1])
    if len(selected) < count:
        raise RuntimeError("Insufficient command diversity for metalinguistic contrasts")
    result = []
    for left, right in selected:
        for speech, suffix in (("QUESTION", ("nu sonna enna artham?", "என்று சொன்னால் என்ன அர்த்தம்?")),
                               ("HYPOTHETICAL", ("nu sonna enna nadakkum?", "என்று சொன்னால் என்ன நடக்கும்?"))):
            generated = []
            for source, ending in ((left, suffix[0]), (right, suffix[1])):
                row = copy.deepcopy(source)
                row["id"] = hashlib.sha256((source["id"] + ":" + speech).encode()).hexdigest()[:16]
                row["family"] += ":" + speech.lower()
                row["text"] += " " + ending
                row["frame"]["speech_act"] = speech
                row["frame"]["coarse_speech_act"] = "NON_ACTION"
                row["frame"]["should_execute"] = False
                row["generation_family"] = "meta_question" if speech == "QUESTION" else "hypothetical_action"
                row["construction_family"] += ":" + speech.lower()
                row["rebalance_mandatory"] = True
                generated.append(row)
            result.append((generated[0], generated[1], left["isolation_group"]))
    return result


def ambiguous_transfer_rows() -> list[tuple[dict, dict, str]]:
    """A named resource without a recipient can still need clarification."""
    results = []
    for i in range(80):
        filename = f"report_{i:02d}.pdf"
        pair = Pair(f"ambiguous_transfer:{i}", f"{filename} anupa mudiyuma?",
                    f"{filename} அனுப்ப முடியுமா?", "AMBIGUOUS", "SEND", "FileRef",
                    (("file", filename, filename, filename),))
        left, right = build_row(pair, "TANGLISH"), build_row(pair, "TAMIL")
        group = f"ambiguous_transfer:{i % 8}"
        for row in (left, right):
            row["generation_family"] = "ambiguous_transfer"
            row["construction_family"] = group
            row["isolation_group"] = group
            row["rebalance_mandatory"] = True
        results.append((left, right, group))
    return results


def asr_augment(rows: list[dict], count: int = 1500) -> list[dict]:
    variants = (("anuppu", "anupu"), ("kaatu", "kaattu"), ("maathu", "mathu"), ("pannu", "panu"), ("paaru", "paru"), ("nethu", "nethi"), ("inniku", "innaiku"))
    generated = []
    seen = {(r["language"], r["text"].casefold()) for r in rows}
    for parent in rows:
        if parent["language"] != "TANGLISH" or parent["frame"]["speech_act"] in {"NEGATED_COMMAND", "CORRECTION", "AMBIGUOUS"}:
            continue
        for old, new in variants:
            if old not in parent["text"]:
                continue
            noisy = parent["text"].replace(old, new, 1)
            key = ("TANGLISH", noisy.casefold())
            if key in seen:
                continue
            child = copy.deepcopy(parent)
            child["id"] = hashlib.sha256((parent["id"] + ":asr:" + old + ":" + new).encode()).hexdigest()[:16]
            child["text"] = noisy
            child["family"] += ":asr"
            child["generation_family"] = "asr_meaning_preserving"
            child["construction_family"] = parent["construction_family"] + ":asr"
            child["isolation_group"] = parent["isolation_group"]
            for slot in child["frame"]["slots"]:
                if slot["source"] == "CONTEXT":
                    continue
                start = noisy.find(slot["surface"])
                if start < 0:
                    break
                slot["start"], slot["end"] = start, start + len(slot["surface"])
            else:
                child["asr_pair"] = {"clean_text": parent["text"], "noisy_text": noisy, "clean_frame": copy.deepcopy(parent["frame"]), "noisy_frame": copy.deepcopy(child["frame"]), "meaning_preserved": True, "parent_id": parent["id"]}
                if not validate_row(child):
                    generated.append(child)
                    seen.add(key)
                    if len(generated) >= count:
                        return generated
    return generated


def select_rebalanced_rows(pool: list[dict], target_tanglish: int, target_tamil: int) -> list[dict]:
    """Constrained family-first selection; never use input order as a quota."""
    if target_tanglish != 18_000 or target_tamil != 12_000:
        raise ValueError("Stage 2.5 rebalance is calibrated for the 18k/12k target")
    by_id = {row["id"]: row for row in pool}
    groups = defaultdict(dict)
    for row in pool:
        if not row.get("asr_pair"):
            groups[row["family"]][row["language"]] = row
    candidate_pairs = [(group["TANGLISH"], group["TAMIL"]) for group in groups.values() if {"TANGLISH", "TAMIL"} <= group.keys()]
    stable = lambda row: hashlib.sha256(row["id"].encode()).hexdigest()
    candidate_pairs.sort(key=lambda pair: stable(pair[0]))
    chosen: dict[str, dict] = {}
    chosen_text = set()
    chosen_pair_ids = set()
    action_count, speech_count, family_count, lang_count = Counter(), Counter(), Counter(), Counter()
    transfer_rows = 0
    transfer = {"SEND", "SHARE", "FORWARD"}

    def text_key(row: dict) -> tuple:
        norm = " ".join(re.findall(r"[\w\u0b80-\u0bff]+", unicodedata.normalize("NFKC", row["text"]).casefold()))
        return (row["language"], norm, json.dumps(row.get("working_context"), sort_keys=True, ensure_ascii=False))

    def add(row: dict) -> None:
        nonlocal transfer_rows
        chosen[row["id"]] = row
        chosen_text.add(text_key(row))
        lang_count[row["language"]] += 1
        action_count[row["frame"]["action_concept"]] += 1
        speech_count[row["frame"]["speech_act"]] += 1
        family_count[row["construction_family"]] += 1
        if row["frame"]["action_concept"] in transfer:
            transfer_rows += 1

    def add_pair(pair: tuple[dict, dict], *, mandatory: bool = False) -> bool:
        left, right = pair
        if left["id"] in chosen:
            return False
        if text_key(left) in chosen_text or text_key(right) in chosen_text:
            return False
        if transfer_rows + (2 if left["frame"]["action_concept"] in transfer else 0) > 5_400:
            return False
        if not mandatory and family_count[left["construction_family"]] >= 240:
            return False
        add(left)
        add(right)
        chosen_pair_ids.add(left["family"])
        return True

    mandatory_generations = {"question_meaning", "ack_project", "confirm_project", "chat_contact", "ambiguous_send", "capability_send", "polite_grounded", "meta_cancel", "slot_coverage"}
    mandatory_pairs = [pair for pair in candidate_pairs if pair[0].get("rebalance_mandatory") or pair[0]["generation_family"] in mandatory_generations]
    for pair in mandatory_pairs:
        if not add_pair(pair, mandatory=True):
            raise RuntimeError("Mandatory rebalance pair violates transfer cap or duplicate selection")

    buckets = defaultdict(list)
    for pair in candidate_pairs:
        if pair[0]["id"] not in chosen:
            frame = pair[0]["frame"]
            buckets[(frame["action_concept"], frame["speech_act"])].append(pair)
    pointers = defaultdict(int)
    while len(chosen_pair_ids) < target_tamil:
        progress = False
        for key in sorted(buckets, key=lambda k: (action_count[k[0]], speech_count[k[1]], str(k))):
            if len(chosen_pair_ids) >= target_tamil:
                break
            group = buckets[key]
            while pointers[key] < len(group):
                pair = group[pointers[key]]
                pointers[key] += 1
                if add_pair(pair):
                    progress = True
                    break
        if not progress:
            raise RuntimeError(f"Only {len(chosen_pair_ids)} complete pairs fit constrained selection")

    asr = sorted((r for r in pool if r.get("asr_pair")), key=lambda r: (r["frame"]["action_concept"] in transfer, action_count[r["frame"]["action_concept"]], stable(r)))
    for child in asr:
        if lang_count["TANGLISH"] >= target_tanglish:
            break
        parent = by_id.get(child["asr_pair"]["parent_id"])
        if parent is None or parent["language"] != "TANGLISH":
            continue
        extra = [row for row in (parent, child) if row["id"] not in chosen]
        if lang_count["TANGLISH"] + len(extra) > target_tanglish:
            continue
        if transfer_rows + sum(row["frame"]["action_concept"] in transfer for row in extra) > 5_400:
            continue
        if any(text_key(row) in chosen_text for row in extra):
            continue
        if any(family_count[row["construction_family"]] >= 240 for row in extra):
            continue
        for row in extra:
            add(row)

    extras = sorted((r for r in pool if r["language"] == "TANGLISH" and not r.get("asr_pair") and r["id"] not in chosen), key=lambda r: (action_count[r["frame"]["action_concept"]], family_count[r["construction_family"]], stable(r)))
    for row in extras:
        if lang_count["TANGLISH"] >= target_tanglish:
            break
        if row["frame"]["action_concept"] in transfer and transfer_rows >= 5_400:
            continue
        if text_key(row) in chosen_text:
            continue
        if family_count[row["construction_family"]] >= 240:
            continue
        add(row)
    result = list(chosen.values())
    counts = Counter(r["language"] for r in result)
    if counts != {"TANGLISH": target_tanglish, "TAMIL": target_tamil}:
        raise RuntimeError(f"Constrained selection incomplete: {dict(counts)}")
    return result


def build(target_tanglish: int = 18_000, target_tamil: int = 12_000) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(ROOT_SEED)
    pairs: list[tuple[dict, dict, str]] = []
    priority_matrix_scenes = {"search_messages", "search_projects", "open_urls", "check_messages", "check_files", "check_system"}
    for scene in SCENARIOS:
        made = generate_scene(scene, rng)
        if scene.key in priority_matrix_scenes:
            for left, right, _ in made:
                left["rebalance_mandatory"] = right["rebalance_mandatory"] = True
        pairs.extend(made)
    pairs.extend(correction_rows(rng))
    pairs.extend(context_rows(rng))
    pairs.extend(special_rows(rng))
    pairs.extend(slot_coverage_rows())
    repaired = rebalanced_correction_rows(rng) + rebalanced_context_rows(rng) + typed_context_rows() + rebalanced_slot_rows() + rebalanced_action_rows()
    for left, right, _ in repaired:
        left["rebalance_mandatory"] = right["rebalance_mandatory"] = True
    pairs.extend(repaired)
    pairs.extend(metalinguistic_rows(pairs))
    pairs.extend(ambiguous_transfer_rows())
    rng.shuffle(pairs)
    rows = [row for left, right, _ in pairs for row in (left, right)]
    seen = set()
    accepted_pool, rejected = [], []
    for row in rows:
        reasons = validate_row(row)
        key = (row["language"], " ".join(row["text"].casefold().split()), json.dumps(row.get("working_context"), sort_keys=True, ensure_ascii=False))
        if key in seen:
            reasons.append("duplicate_surface_and_context")
        seen.add(key)
        if reasons:
            row["quality"] = "Q0"
            row["validation_status"] = "REJECTED"
            row["reasons"] = reasons
            rejected.append(row)
        else:
            row["quality"] = "Q2"
            row["validation_status"] = "PASSED"
            row["review_status"] = "UNREVIEWED"
            accepted_pool.append(row)
    asr = asr_augment(accepted_pool)
    for child in asr:
        child["quality"] = "Q2"
        child["validation_status"] = "PASSED"
        child["review_status"] = "UNREVIEWED"
    accepted_pool.extend(asr)
    accepted = select_rebalanced_rows(accepted_pool, target_tanglish, target_tamil)
    family_frequency = Counter(r["construction_family"] for r in accepted)
    slot_frequency = Counter(s["slot"] for r in accepted for s in r["frame"]["slots"])
    for row in accepted:
        flags = []
        if family_frequency[row["construction_family"]] > 250:
            flags.append("DENSE_CONSTRUCTION_FAMILY")
        if any(slot_frequency[s["slot"]] < 50 for s in row["frame"]["slots"]):
            flags.append("RARE_SLOT")
        if row["frame"]["context_required"]:
            flags.append("CONTEXT_DEPENDENT")
        if row.get("asr_pair"):
            flags.append("ASR_POSITIVE")
        if row["frame"]["action_concept"] in {"SEND", "FORWARD", "UPLOAD", "DELETE"}:
            flags.append("EXTERNAL_OR_DESTRUCTIVE_CONCEPT")
        row["quality_flags"] = flags
    for filename, content in (("stage25_candidates.jsonl", accepted), ("stage25_rejected.jsonl", rejected)):
        (OUT / filename).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in content), encoding="utf-8")
    skeleton = Counter(r["construction_family"] for r in accepted)
    summary = {"target": {"TANGLISH": target_tanglish, "TAMIL": target_tamil}, "generated": len(rows) + len(asr), "validator_passed_pool": len(accepted_pool), "validator_passed_q2": len(accepted), "rejected": len(rejected), "language": dict(Counter(r["language"] for r in accepted)), "speech_act": dict(Counter(r["frame"]["speech_act"] for r in accepted)), "action_concept": dict(Counter(str(r["frame"]["action_concept"]) for r in accepted)), "generation_family": dict(Counter(r["generation_family"] for r in accepted)), "construction_families": len(skeleton), "largest_construction_family": skeleton.most_common(1), "context_rows": sum(bool(r["frame"]["context_required"]) for r in accepted), "asr_rows": sum(bool(r.get("asr_pair")) for r in accepted), "sha256": hashlib.sha256((OUT / "stage25_candidates.jsonl").read_bytes()).hexdigest(), "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "validator_sha256": hashlib.sha256((Path(__file__).parent / "stage25_gold_data.py").read_bytes()).hexdigest(), "audit_completed": 0, "training_admitted": False}
    (OUT / "stage25_generation_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=True, indent=2))
