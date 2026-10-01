"""Typed references the primitives produce and consume (stored in working memory so "it", "that", "the second
one" resolve by type, never by guessing)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from jarvis.core.context.models import BaseResourceRef, MediaResourceRef, ScreenshotResourceRef  # noqa: F401 (re-export)

# Application families decide what an ambiguous verb means ("go back" in a browser is page-back; in a phone
# session it is the phone's back key).
BROWSER_PROCS = ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe", "arc.exe")
EDITOR_PROCS = ("notepad.exe", "notepad++.exe", "wordpad.exe", "winword.exe", "sublime_text.exe", "obsidian.exe")
IDE_PROCS = ("antigravity.exe", "code.exe", "cursor.exe", "windsurf.exe", "pycharm64.exe", "idea64.exe", "devenv.exe")
MEDIA_PROCS = ("vlc.exe", "spotify.exe", "wmplayer.exe", "music.ui.exe", "video.ui.exe", "mpc-hc64.exe")
FILE_PROCS = ("explorer.exe",)
CHAT_PROCS = ("whatsapp.exe", "telegram.exe", "slack.exe", "teams.exe", "ms-teams.exe", "discord.exe")


def app_family(process: str, title: str = "") -> str:
    p = (process or "").lower()
    t = (title or "").lower()
    if p in BROWSER_PROCS:
        return "media" if ("youtube" in t or "netflix" in t or "prime video" in t) else "browser"
    if p in IDE_PROCS:
        return "ide"
    if p in EDITOR_PROCS:
        return "editor"
    if p in MEDIA_PROCS:
        return "media"
    if p in FILE_PROCS:
        return "files"
    if p in CHAT_PROCS:
        return "chat"
    return "app" if p else ""


@dataclass
class WindowRef(BaseResourceRef):
    """A top-level window: its handle is only trusted together with the process and title it had."""
    hwnd: int = 0
    process: str = ""
    title: str = ""
    pid: int = 0
    family: str = ""
    seen_at: float = field(default_factory=time.time)

    def __post_init__(self):
        self.resource_type = "WINDOW"
        self.family = self.family or app_family(self.process, self.title)
        self.canonical_identifier = self.canonical_identifier or f"{self.process}:{self.hwnd}"
        self.display_name = self.display_name or (self.title or self.process)


@dataclass
class ControlRef(BaseResourceRef):
    """A control inside a window, a web page or a phone screen, found semantically (role + name), never by x/y."""
    platform: str = ""          # "uia" | "web" | "android" | "fake"
    role: str = ""              # button, link, textbox, checkbox, tab, menuitem, listitem, ...
    name: str = ""
    automation_id: str = ""
    selector: str = ""          # adapter-specific locator (UIA runtime id, CSS/role selector, uiautomator bounds)
    enabled: bool = True
    visible: bool = True
    editable: bool = False
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)
    scope: str = ""             # window / page / device it belongs to
    generation: int = 0         # snapshot generation it came from (stale refs are re-resolved)
    score: float = 0.0

    def __post_init__(self):
        self.resource_type = "CONTROL"
        self.display_name = self.display_name or f"{self.name or self.role}"


@dataclass
class ClipboardResource(BaseResourceRef):
    kind: str = "text"          # text | image | files
    text: str = ""
    image_path: str = ""
    files: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.resource_type = "CLIPBOARD"
        self.display_name = self.display_name or (self.text[:40] if self.kind == "text" else self.kind)


@dataclass
class DownloadResource(BaseResourceRef):
    path: str = ""
    source_url: str = ""
    filename: str = ""
    status: str = "complete"    # in_progress | complete | failed

    def __post_init__(self):
        self.resource_type = "DOWNLOAD"
        self.canonical_identifier = self.canonical_identifier or self.path
        self.display_name = self.display_name or self.filename


@dataclass
class BrowserTabRef(BaseResourceRef):
    index: int = 0
    title: str = ""
    url: str = ""
    browser: str = ""

    def __post_init__(self):
        self.resource_type = "BROWSER_TAB"
        self.canonical_identifier = self.canonical_identifier or self.url
        self.display_name = self.display_name or self.title


@dataclass
class LinkRef(BaseResourceRef):
    """One entry of a result list on a page (search results, video results): "open the third one"."""
    title: str = ""
    url: str = ""
    selector: str = ""

    def __post_init__(self):
        self.resource_type = "LINK"
        self.canonical_identifier = self.canonical_identifier or self.url
        self.display_name = self.display_name or self.title


@dataclass
class OperatorOutcome:
    """What a primitive really did (the verifier's evidence travels with it)."""
    ok: bool
    message: str
    resource: Optional[BaseResourceRef] = None
    evidence: dict[str, Any] = field(default_factory=dict)
    needs: str = ""             # "clarify" | "user" (login/captcha/UAC) | "" - what is needed when not ok
    candidates: list[Any] = field(default_factory=list)
