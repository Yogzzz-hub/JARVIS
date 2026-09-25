"""Connector Tools for JARVIS EDGE.

Wraps the Local Connector Framework into typed, policy-checked, verified Tool
instances conforming to ToolDefinition and Contract schemas.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional
from pydantic import Field

from jarvis.tools.base import Contract, RiskLevel, Tool, ToolDefinition
from jarvis.connectors.manager import get_connector_manager

logger = logging.getLogger("jarvis.tools.connectors")


# =====================================================================
# Contracts
# =====================================================================

class EmptyInput(Contract):
    pass


# Android Contracts
class AndroidAppInput(Contract):
    app_name: str = Field(description="Name or package name of the app to open, e.g. 'Spotify', 'camera', 'settings'")


class AndroidActionResult(Contract):
    success: bool
    message: str
    data: dict = Field(default_factory=dict)


# LocalSend Contracts
class LocalSendFileInput(Contract):
    path: str = Field(default="", description="Path to the file to send. If empty, resolves from active file or recent files.")
    target_alias: Optional[str] = Field(default=None, description="Optional target device alias")


class LocalSendTextInput(Contract):
    text: str = Field(description="Text or URL to send to phone")
    target_alias: Optional[str] = Field(default=None, description="Optional target device alias")


class LocalSendResult(Contract):
    success: bool
    message: str
    bytes_transferred: int = 0


# Browser Contracts
class BrowserOpenInput(Contract):
    url: str = Field(description="URL to open in the browser")


class BrowserExtractInput(Contract):
    url: Optional[str] = Field(default=None, description="URL to extract text from, or current page if omitted")


class BrowserExtractResult(Contract):
    title: str = ""
    url: str = ""
    content: str = ""
    success: bool = True


class BrowserDownloadInput(Contract):
    timeout_seconds: float = Field(default=30.0, description="Max seconds to wait for download")


# FreshRSS Contracts
class RssQueryInput(Contract):
    query: str = Field(default="", description="Query or topic to filter, e.g. 'AI', 'tech'")
    limit: int = Field(default=5, ge=1, le=20, description="Max number of items to return")


class RssFeedResult(Contract):
    items: List[dict] = Field(default_factory=list)
    count: int = 0
    source: str = "rss"


# Notification Contracts
class NotificationInput(Contract):
    title: str = Field(default="JARVIS Alert", description="Notification title")
    message: str = Field(description="Message body to send")
    priority: int = Field(default=3, ge=1, le=5, description="Priority 1-5")


class NotificationResult(Contract):
    success: bool
    message: str


# Memos Contracts
class MemosCreateInput(Contract):
    content: str = Field(description="Note text to save to Memos")
    tags: List[str] = Field(default_factory=list, description="Optional tags for the note")


class MemosQueryInput(Contract):
    query: str = Field(default="", description="Search query")
    limit: int = Field(default=5, ge=1, le=20, description="Max number of notes")


class MemosResult(Contract):
    notes: List[dict] = Field(default_factory=list)
    count: int = 0
    message: str = ""


# Node-RED Contracts
class NodeRedTriggerInput(Contract):
    event_type: str = Field(description="Event name, e.g. 'briefing_requested', 'status_check'")
    payload: dict = Field(default_factory=dict, description="Safe event payload")


# =====================================================================
# Tools Implementation
# =====================================================================

def _coerce_args(cls, args):
    if isinstance(args, cls):
        return args
    if isinstance(args, dict):
        return cls(**args)
    return cls()


class AndroidStatusTool(Tool):

    def __init__(self):
        super().__init__()
        self.definition = ToolDefinition(
            name="android_status",
            description="Check Android device connection, scrcpy availability, and battery status",
            input_model=EmptyInput,
            output_model=AndroidActionResult,
            risk=RiskLevel.READ_ONLY,
            tags=("android", "mobile"),
            read_only=True,
        )

    def run(self, arguments: EmptyInput) -> dict:
        mgr = get_connector_manager()
        c = mgr.get_connector("android")
        h = c.health_check() if c else {}
        adb_ready = h.get("status") == "ready"
        adb_dev = h.get("device", "none")

        # Check WhatsApp phone connection
        wa_connected = False
        wa_phone = ""
        try:
            import websockets, uuid, json, asyncio
            async def _check_wa():
                async with websockets.connect("ws://127.0.0.1:8768", open_timeout=1.5) as ws:
                    req_id = str(uuid.uuid4())
                    await ws.send(json.dumps({"id": req_id, "action": "get_status"}))
                    while True:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.5)
                        msg = json.loads(raw)
                        if msg.get("action") == "get_status" or msg.get("type") == "status_update":
                            payload = msg.get("payload") or msg.get("result") or {}
                            if payload.get("state") == "CONNECTED":
                                user = payload.get("user") or {}
                                return True, user.get("id", "916381456199")
                            return False, ""
            wa_connected, wa_phone = asyncio.run(_check_wa())
        except Exception:
            pass

        if adb_ready:
            msg = f"Your Android phone is connected ({adb_dev})."
            if wa_connected:
                msg += " WhatsApp is also active."
            return {"success": True, "message": msg, "data": h}
        elif wa_connected:
            phone_num = wa_phone.split(":")[0].split("@")[0]
            clean_num = f"+{phone_num}" if not phone_num.startswith("+") else phone_num
            return {
                "success": True,
                "message": f"Your phone ({clean_num}) is connected via WhatsApp. No Android USB device is connected via ADB.",
                "data": {"status": "CONNECTED", "whatsapp_connected": True, "phone": clean_num, "adb_status": h}
            }
        else:
            return {
                "success": False,
                "message": "No phone is currently connected (ADB: no device found, WhatsApp: disconnected).",
                "data": h
            }


class AndroidOpenControlTool(Tool):
    def __init__(self):
        super().__init__()
        self.definition = ToolDefinition(
            name="android_open_control",
            description="Show Android phone screen on PC desktop via scrcpy (mirror phone)",
            input_model=EmptyInput,
            output_model=AndroidActionResult,
            risk=RiskLevel.REVERSIBLE,
            tags=("android", "mobile", "scrcpy"),
            read_only=False,
        )

    def run(self, arguments: EmptyInput) -> dict:
        mgr = get_connector_manager()
        c = mgr.get_connector("android")
        if not c:
            return {"success": False, "message": "Android connector disabled"}
        res = c.execute("open_control")
        return {
            "success": res.get("success", False),
            "message": res.get("message", "Screen mirror requested"),
            "data": res,
        }


class AndroidCloseControlTool(Tool):
    def __init__(self):
        super().__init__()
        self.definition = ToolDefinition(
            name="android_close_control",
            description="Close phone screen mirror / scrcpy window",
            input_model=EmptyInput,
            output_model=AndroidActionResult,
            risk=RiskLevel.REVERSIBLE,
            tags=("android", "mobile", "scrcpy"),
            read_only=False,
        )

    def run(self, arguments: EmptyInput) -> dict:
        mgr = get_connector_manager()
        c = mgr.get_connector("android")
        if not c:
            return {"success": False, "message": "Android connector disabled"}
        res = c.execute("close_control")
        return {
            "success": res.get("success", False),
            "message": res.get("message", "Closed phone mirror"),
            "data": res,
        }


class AndroidOpenAppTool(Tool):
    def __init__(self):
        super().__init__()
        self.definition = ToolDefinition(
            name="android_open_app",
            description="Launch an application on connected Android phone",
            input_model=AndroidAppInput,
            output_model=AndroidActionResult,
            risk=RiskLevel.REVERSIBLE,
            tags=("android", "mobile"),
            read_only=False,
        )

    def run(self, arguments: AndroidAppInput) -> dict:
        arguments = _coerce_args(AndroidAppInput, arguments)
        mgr = get_connector_manager()
        c = mgr.get_connector("android")
        if not c:
            return {"success": False, "message": "Android connector disabled"}
        res = c.execute("open_app", app_name=arguments.app_name)
        return {
            "success": res.get("success", False),
            "message": res.get("message", f"Launched {arguments.app_name}"),
            "data": res,
        }


class AndroidHomeTool(Tool):
    def __init__(self):
        super().__init__()
        self.definition = ToolDefinition(
            name="android_home",
            description="Press Home button on connected Android phone",
            input_model=EmptyInput,
            output_model=AndroidActionResult,
            risk=RiskLevel.REVERSIBLE,
            tags=("android", "mobile"),
            read_only=False,
        )

    def run(self, arguments: EmptyInput) -> dict:
        mgr = get_connector_manager()
        c = mgr.get_connector("android")
        if not c:
            return {"success": False, "message": "Android connector disabled"}
        res = c.execute("home")
        return {"success": res.get("success", False), "message": "Pressed Home on phone", "data": res}


class AndroidBackTool(Tool):
    def __init__(self):
        super().__init__()
        self.definition = ToolDefinition(
            name="android_back",
            description="Press Back button on connected Android phone",
            input_model=EmptyInput,
            output_model=AndroidActionResult,
            risk=RiskLevel.REVERSIBLE,
            tags=("android", "mobile"),
            read_only=False,
        )

    def run(self, arguments: EmptyInput) -> dict:
        mgr = get_connector_manager()
        c = mgr.get_connector("android")
        if not c:
            return {"success": False, "message": "Android connector disabled"}
        res = c.execute("back")
        return {"success": res.get("success", False), "message": "Pressed Back on phone", "data": res}


# ---------------------------------------------------------------------
# LocalSend Tools
# ---------------------------------------------------------------------

class LocalSendFileTool(Tool):
    def __init__(self, working_memory=None):
        super().__init__()
        self.working_memory = working_memory
        self.definition = ToolDefinition(
            name="localsend_file",
            description="Send a file to Android phone via LocalSend over local Wi-Fi / LAN",
            input_model=LocalSendFileInput,
            output_model=LocalSendResult,
            risk=RiskLevel.REVERSIBLE,
            tags=("localsend", "transfer", "file"),
            read_only=False,
        )

    def run(self, arguments: LocalSendFileInput) -> dict:
        arguments = _coerce_args(LocalSendFileInput, arguments)
        path = arguments.path.strip()
        if not path and self.working_memory:
            # Resolve from active resource or recent search result
            ref = getattr(self.working_memory, "active_resource", None)
            if ref and getattr(ref, "uri", None):
                path = str(ref.uri)
            elif hasattr(self.working_memory, "last_search_results") and self.working_memory.last_search_results:
                path = str(self.working_memory.last_search_results[0])

        if not path:
            return {"success": False, "message": "No file path provided or found in recent context", "bytes_transferred": 0}

        mgr = get_connector_manager()
        c = mgr.get_connector("localsend")
        if not c:
            return {"success": False, "message": "LocalSend connector disabled", "bytes_transferred": 0}

        res = c.execute("send_file", file_path=path, target_alias=arguments.target_alias)
        return {
            "success": res.get("success", False),
            "message": res.get("message", "Transfer processed"),
            "bytes_transferred": res.get("bytes_transferred", 0),
        }


class LocalSendTextTool(Tool):
    def __init__(self):
        super().__init__()
        self.definition = ToolDefinition(
            name="localsend_text",
            description="Send text, clipboard content, or URL to phone via LocalSend",
            input_model=LocalSendTextInput,
            output_model=LocalSendResult,
            risk=RiskLevel.REVERSIBLE,
            tags=("localsend", "transfer", "text"),
            read_only=False,
        )

    def run(self, arguments: LocalSendTextInput) -> dict:
        arguments = _coerce_args(LocalSendTextInput, arguments)
        mgr = get_connector_manager()
        c = mgr.get_connector("localsend")
        if not c:
            return {"success": False, "message": "LocalSend connector disabled", "bytes_transferred": 0}

        res = c.execute("send_text", text=arguments.text, target_alias=arguments.target_alias)
        return {
            "success": res.get("success", False),
            "message": res.get("message", "Text sent via LocalSend"),
            "bytes_transferred": len(arguments.text.encode("utf-8")),
        }


# ---------------------------------------------------------------------
# FreshRSS Tools
# ---------------------------------------------------------------------

class RssLatestTool(Tool):
    def __init__(self, working_memory=None):
        super().__init__()
        self.working_memory = working_memory
        self.definition = ToolDefinition(
            name="rss_latest",
            description="Fetch the latest news headlines and articles from FreshRSS feeds",
            input_model=RssQueryInput,
            output_model=RssFeedResult,
            risk=RiskLevel.READ_ONLY,
            tags=("rss", "news", "freshrss"),
            read_only=True,
        )

    def run(self, arguments: RssQueryInput) -> dict:
        arguments = _coerce_args(RssQueryInput, arguments)
        mgr = get_connector_manager()
        c = mgr.get_connector("rss")
        if not c:
            return {"items": [], "count": 0, "source": "disabled"}

        if arguments.query:
            res = c.execute("search", query=arguments.query, limit=arguments.limit)
        else:
            res = c.execute("latest", limit=arguments.limit)

        items = res.get("items", [])
        # Update working memory with latest feed items so ordinal follow-ups work!
        if self.working_memory and hasattr(self.working_memory, "set_feed_items"):
            self.working_memory.set_feed_items(items)

        return {
            "items": items,
            "count": len(items),
            "source": res.get("source", "rss"),
        }


# ---------------------------------------------------------------------
# Notification Tools
# ---------------------------------------------------------------------

class NotificationSendTool(Tool):
    def __init__(self):
        super().__init__()
        self.definition = ToolDefinition(
            name="notification_send",
            description="Send a push notification to phone via ntfy or Gotify",
            input_model=NotificationInput,
            output_model=NotificationResult,
            risk=RiskLevel.REVERSIBLE,
            tags=("notifications", "ntfy", "gotify", "mobile"),
            read_only=False,
        )

    def run(self, arguments: NotificationInput) -> dict:
        arguments = _coerce_args(NotificationInput, arguments)
        mgr = get_connector_manager()
        c = mgr.get_connector("notifications")
        if not c:
            return {"success": False, "message": "Notification connector disabled"}

        res = c.execute(
            "send",
            title=arguments.title,
            message=arguments.message,
            priority=arguments.priority,
        )
        return {
            "success": res.get("success", False),
            "message": res.get("message", "Notification processed"),
        }


# ---------------------------------------------------------------------
# Memos Tools
# ---------------------------------------------------------------------

class MemosCreateTool(Tool):
    def __init__(self, working_memory=None):
        super().__init__()
        self.working_memory = working_memory
        self.definition = ToolDefinition(
            name="memos_create",
            description="Save a human-readable note or reminder into Memos inbox",
            input_model=MemosCreateInput,
            output_model=MemosResult,
            risk=RiskLevel.REVERSIBLE,
            tags=("memos", "notes", "inbox"),
            read_only=False,
        )

    def run(self, arguments: MemosCreateInput) -> dict:
        arguments = _coerce_args(MemosCreateInput, arguments)
        content = arguments.content.strip()
        # If user says "make a note about this", append active reference context if available
        if ("about this" in content.lower() or content == "note this") and self.working_memory:
            ref = getattr(self.working_memory, "active_resource", None)
            if ref and getattr(ref, "uri", None):
                content += f" (Ref: {ref.uri})"

        mgr = get_connector_manager()
        c = mgr.get_connector("memos")
        if not c:
            return {"notes": [], "count": 0, "message": "Memos connector disabled"}

        res = c.execute("create", content=content, tags=arguments.tags)
        return {
            "notes": [res.get("memo")] if res.get("memo") else [],
            "count": 1 if res.get("success") else 0,
            "message": res.get("message", "Note saved"),
        }


class MemosRecentTool(Tool):
    def __init__(self):
        super().__init__()
        self.definition = ToolDefinition(
            name="memos_recent",
            description="List recent human-readable notes from Memos",
            input_model=MemosQueryInput,
            output_model=MemosResult,
            risk=RiskLevel.READ_ONLY,
            tags=("memos", "notes"),
            read_only=True,
        )

    def run(self, arguments: MemosQueryInput) -> dict:
        arguments = _coerce_args(MemosQueryInput, arguments)
        mgr = get_connector_manager()
        c = mgr.get_connector("memos")
        if not c:
            return {"notes": [], "count": 0, "message": "Memos connector disabled"}

        if arguments.query:
            res = c.execute("search", query=arguments.query, limit=arguments.limit)
        else:
            res = c.execute("recent", limit=arguments.limit)

        items = res.get("notes", [])
        return {
            "notes": items,
            "count": len(items),
            "message": f"Retrieved {len(items)} notes",
        }


# ---------------------------------------------------------------------
# Browser Connector Tools
# ---------------------------------------------------------------------

class BrowserOpenUrlTool(Tool):
    def __init__(self, working_memory=None):
        super().__init__()
        self.working_memory = working_memory
        self.definition = ToolDefinition(
            name="browser_open_url",
            description="Open a web URL using the existing Playwright browser manager with semantic wait",
            input_model=BrowserOpenInput,
            output_model=BrowserExtractResult,
            risk=RiskLevel.REVERSIBLE,
            tags=("browser", "playwright", "web"),
            read_only=False,
        )

    def run(self, arguments: BrowserOpenInput) -> dict:
        arguments = _coerce_args(BrowserOpenInput, arguments)
        url = arguments.url.strip()
        if (not url or any(k in url.lower() for k in ("second", "first", "third", "last", "that", "one", "story", "article"))) and self.working_memory:
            resolved = self.working_memory.resolve_reference(url or "that article")
            if isinstance(resolved, dict) and "url" in resolved:
                url = resolved["url"]
            elif isinstance(resolved, str) and resolved.startswith("http"):
                url = resolved

        if not url:
            return {"title": "", "url": "", "content": "No URL provided or resolved from context", "success": False}

        mgr = get_connector_manager()
        c = mgr.get_connector("browser")
        if not c:
            return {"title": "", "url": url, "content": "Browser connector disabled", "success": False}

        res = c.execute("open", url=url)
        return {
            "title": res.get("title", ""),
            "url": res.get("url", url),
            "content": f"Opened {url}",
            "success": res.get("success", False),
        }


class MorningBriefingResult(Contract):
    status: str
    spoken_text: str
    duration_ms: float = 0.0
    sections: dict = Field(default_factory=dict)


class MorningBriefingTool(Tool):
    def __init__(self, working_memory=None):
        super().__init__()
        self.working_memory = working_memory
        self.definition = ToolDefinition(
            name="morning_briefing",
            description="Execute morning briefing: parallel gathering of RSS, Memos, system health, and downloads",
            input_model=EmptyInput,
            output_model=MorningBriefingResult,
            risk=RiskLevel.READ_ONLY,
            tags=("morning", "briefing", "orchestration"),
            read_only=True,
        )

    def run(self, arguments: EmptyInput) -> dict:
        import asyncio
        from jarvis.workflows.morning_briefing import run_morning_briefing
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(lambda: asyncio.run(run_morning_briefing(working_memory=self.working_memory))).result()
            else:
                return asyncio.run(run_morning_briefing(working_memory=self.working_memory))
        except Exception as exc:
            return {"status": "error", "spoken_text": f"Error during briefing: {exc}", "duration_ms": 0.0, "sections": {}}


# ---------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------

def create_connector_tools(working_memory=None) -> list[Tool]:
    """Instantiate and return all connector tools."""
    return [
        AndroidStatusTool(),
        AndroidOpenControlTool(),
        AndroidCloseControlTool(),
        AndroidOpenAppTool(),
        AndroidHomeTool(),
        AndroidBackTool(),
        LocalSendFileTool(working_memory=working_memory),
        LocalSendTextTool(),
        RssLatestTool(working_memory=working_memory),
        NotificationSendTool(),
        MemosCreateTool(working_memory=working_memory),
        MemosRecentTool(),
        BrowserOpenUrlTool(working_memory=working_memory),
        MorningBriefingTool(working_memory=working_memory),
    ]

