"""Canonical Capability and Intent Mapping.

Maps legacy, alternative, or external dataset capability identifiers
to the authoritative CapabilityRegistry IDs.
"""

from typing import Dict, List, Optional

CANONICAL_MAP: Dict[str, str] = {
    # App Management
    "open_app": "app.open",
    "app.open": "app.open",
    "close_app": "app.close",
    "app.close": "app.close",
    "app.location": "app.get_location",
    "get_app_location": "app.get_location",
    "app.get_location": "app.get_location",
    "app.list": "app.list_installed",
    "app.list_installed": "app.list_installed",
    "list_installed_applications": "app.list_installed",
    "app.refresh": "app.refresh_catalog",
    "app.refresh_catalog": "app.refresh_catalog",
    "refresh_applications": "app.refresh_catalog",
    "app.check_installed": "app.check_installed",
    "check_app_installed": "app.check_installed",
    "app.install": "app.install_software",
    "app.install_software": "app.install_software",
    "app.paste": "terminal.powershell",


    # Window Management
    "close_window": "windows.close_window",
    "window.close": "windows.close_window",
    "minimize_window": "windows.minimize_window",
    "window.minimize": "windows.minimize_window",
    "maximize_window": "windows.maximize_window",
    "window.maximize": "windows.maximize_window",
    "restore_window": "windows.maximize_window",
    "window.restore": "windows.maximize_window",
    "show_desktop": "windows.show_desktop",
    "window.show_desktop": "windows.show_desktop",

    # Audio & System Volume
    "volume_set": "windows.volume_set",
    "system.volume_set": "windows.volume_set",
    "volume_up": "windows.volume_set",
    "system.volume_up": "windows.volume_set",
    "volume_down": "windows.volume_set",
    "system.volume_down": "windows.volume_set",
    "volume_get": "windows.volume_get",
    "system.volume_get": "windows.volume_get",
    "volume_mute": "windows.volume_mute",
    "system.volume_mute": "windows.volume_mute",
    "mute": "windows.volume_mute",
    "volume_unmute": "windows.volume_unmute",
    "system.volume_unmute": "windows.volume_unmute",
    "unmute": "windows.volume_unmute",

    # Display & Hardware & Diagnostics
    "take_screenshot": "windows.screenshot",
    "system.screenshot": "windows.screenshot",
    "screen.record": "windows.screenshot",
    "desktop_ui_snapshot": "windows.screenshot",
    "system.brightness": "windows.brightness_set",
    "windows.brightness": "windows.brightness_set",
    "system.battery": "system.diagnostics",
    "battery_status": "system.diagnostics",
    "system.power": "system.diagnostics",
    "system.cpu": "system.diagnostics",
    "system.processes": "windows.top_memory_processes",
    "system.disk_info": "system.diagnostics",
    "system.clipboard": "terminal.powershell",
    "system.notify": "system.dashboard",
    "system.set_wallpaper": "windows.desktop_ui_click",
    "system.time": "system.time",
    "get_time": "system.time",
    "system.diagnostics": "system.diagnostics",
    "system_diagnostics": "system.diagnostics",
    "system.info": "system.diagnostics",
    "system_info": "system.diagnostics",
    "system.devices": "system.devices",
    "system.services": "system.diagnostics",
    "system.lock": "windows.close_window",
    "system.sleep": "windows.close_window",
    "media_control": "windows.media_control",
    "save_workspace": "workflow.save_workspace",


    # File Operations
    "find_file": "file.find",
    "find_files": "file.find",
    "file.search": "file.find",
    "file.find": "file.find",
    "file.open": "file.open",
    "file.open_parent": "file.list_directory",
    "file.list": "file.list_directory",
    "file.list_directory": "file.list_directory",
    "list_directory": "file.list_directory",
    "file.organize": "file.organize_downloads",
    "file.organize_downloads": "file.organize_downloads",
    "file.find_duplicates": "file.find_duplicates",
    "find_duplicates": "file.find_duplicates",
    "file.batch_rename": "file.batch_rename",
    "file.copy": "file.copy",
    "file.move": "file.move",
    "file.delete": "file.delete",
    "file.create_folder": "file.create_folder",
    "file.read_metadata": "file.read_metadata",
    "file.save": "file.create_folder",
    "file.checksum": "file.read_metadata",
    "file.hash": "file.read_metadata",
    "file.group": "file.organize_downloads",
    "file.compress": "file.batch_rename",
    "file.extract": "file.batch_rename",
    "file.convert": "workflow.extract_audio",
    "file.export": "file.copy",
    "file.empty_recycle_bin": "file.delete",

    # Phone / Android / LocalSend
    "phone.transfer": "phone.send_file",
    "phone.send_file": "phone.send_file",
    "localsend_file": "phone.send_file",
    "localsend_text": "phone.send_text",
    "phone.send_text": "phone.send_text",
    "phone.send_notification": "phone.send_notification",
    "phone.status": "phone.status",
    "android_status": "phone.status",
    "phone.screen_mirror": "phone.mirror_open",
    "phone.mirror_open": "phone.mirror_open",
    "phone.mirror_close": "phone.mirror_close",
    "android_open_control": "phone.mirror_open",
    "android_close_control": "phone.mirror_close",
    "phone.open_app": "phone.open_app",
    "phone.get_photo": "phone.mirror_open",

    # WhatsApp
    "send_whatsapp_message": "whatsapp.send",
    "whatsapp.send": "whatsapp.send",
    "whatsapp.action": "whatsapp.action",
    "whatsapp.read": "whatsapp.read",
    "read_whatsapp_messages": "whatsapp.read",
    "whatsapp_status": "whatsapp.status",
    "whatsapp.status": "whatsapp.status",
    "whatsapp.draft": "whatsapp.action",
    "whatsapp.summarize": "whatsapp.summarize",
    "whatsapp.search_messages": "whatsapp.read",
    "whatsapp.read_thread": "whatsapp.read",
    "whatsapp.draft_message": "whatsapp.action",
    "whatsapp.send_message": "whatsapp.send",

    # RAG / Knowledge / Notes / RSS
    "news.search": "rag.search_news",
    "search_news": "rag.search_news",
    "rag.search_news": "rag.search_news",
    "rss.latest": "rag.rss_latest",
    "rss_latest": "rag.rss_latest",
    "rag.rss_latest": "rag.rss_latest",
    "rag.search_notes": "rag.search_notes",
    "search_notes": "rag.search_notes",
    "rag.capture_note": "rag.capture_note",
    "capture_note": "rag.capture_note",
    "quick_note": "rag.capture_note",
    "dictate_text": "rag.capture_note",
    "rag.memos_create": "rag.memos_create",
    "rag.memos_recent": "rag.memos_recent",
    "memos_recent": "rag.memos_recent",
    "knowledge.note": "rag.capture_note",

    "knowledge.summarize": "rag.document_qa",
    "knowledge.extract": "rag.document_qa",
    "knowledge.qa": "rag.document_qa",
    "knowledge.format": "rag.document_qa",
    "knowledge.compare": "rag.document_qa",
    "knowledge.recommend": "rag.document_qa",
    "document_qa": "rag.document_qa",
    "rag.document_qa": "rag.document_qa",
    "rag.search_web": "rag.search_web",

    # Browser
    "browser.open_url": "browser.open_url",
    "browser.search": "rag.search_web",
    "browser.navigate": "browser.navigate",
    "browser.play_youtube": "browser.play_youtube",
    "browser.maps": "browser.open_url",

    # Workflows / Developer Tools
    "workflow.git_status": "workflow.git_status",
    "workflow.trim_audio": "workflow.trim_clip",
    "workflow.lint": "workflow.diagnose_error",
    "workflow.run_tests": "workflow.run_tests",
    "workflow.coverage": "workflow.run_tests",
    "terminal.powershell": "terminal.powershell",
    "email.draft": "google.gmail_send",
    "email.search": "rag.document_qa",
    "calendar.read": "google.calendar_list",
    "drive.search": "google.drive_search",
    "image.optimize": "windows.desktop_ui_click",
    "media.convert": "workflow.extract_audio",
    "user.confirm": "system.dashboard",
}


def to_canonical(cap_or_intent: Optional[str]) -> str:
    """Returns canonical registry capability ID for a given label or intent."""
    if not cap_or_intent:
        return ""
    c = cap_or_intent.strip()
    return CANONICAL_MAP.get(c, c)


def to_canonical_list(caps: List[str]) -> List[str]:
    """Returns list of unique canonical capability IDs in order."""
    res = []
    seen = set()
    for c in caps:
        canon = to_canonical(c)
        if canon and canon not in seen:
            seen.add(canon)
            res.append(canon)
    return res
