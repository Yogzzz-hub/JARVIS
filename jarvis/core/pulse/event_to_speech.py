from __future__ import annotations

from typing import Any, Dict, Optional


EVENT_SPEECH_TEMPLATES = {
    "APP_LAUNCH_STARTED": "Opening {name}.",
    "FILE_SEARCH_STARTED": "I'm looking for it.",
    "DOWNLOAD_STARTED": "Downloading it.",
    "INSTALL_WAITING_FOR_USER": "Windows needs your approval to continue.",
    "BROWSER_NAVIGATION_STARTED": "Checking that now.",
    "TASK_RETRYING_SAFE_METHOD": "That didn't respond. I'm trying another method.",
    "TASK_VERIFIED": "Done.",
    "TASK_UNCERTAIN": "I couldn't verify that it completed.",
    "CONFIRMATION_REQUIRED": "This action requires your confirmation.",
    "TOOL_STARTED": "Working on that.",
    "PLANNING_STARTED": "Planning your task.",
}

# Contextual Micro-ACKs selected by tool intent category
INTENT_MICRO_ACKS = {
    "open_app": "Opening it.",
    "close_app": "Closing it.",
    "switch_app": "Switching to it.",
    "find_file": "Looking.",
    "open_file": "Opening the file.",
    "list_dir": "Checking files.",
    "list_files": "Checking files.",
    "search_notes": "Searching your notes.",
    "create_note": "Taking note.",
    "quick_notes": "Taking note.",
    "meeting_notes": "Recording meeting notes.",
    "document_qa": "Checking the document.",
    "doc_qa": "Checking the document.",
    "organize_downloads": "Organizing downloads.",
    "batch_rename": "Renaming files.",
    "find_duplicates": "Scanning for duplicates.",
    "extract_audio": "Extracting audio.",
    "trim_media_clip": "Trimming clip.",
    "git_status": "Checking Git status.",
    "git_commit": "Committing changes.",
    "run_project_tests": "Running tests.",
    "dag_scheduler": "On it.",
    "planner": "I'll plan and handle that.",
    "send_whatsapp_message": "Sending WhatsApp message.",
    "send_whatsapp": "Sending WhatsApp message.",
    "read_whatsapp_messages": "Checking your WhatsApp messages.",
    "read_whatsapp": "Checking your WhatsApp messages.",
    "summarize_whatsapp_messages": "Summarizing your WhatsApp messages.",
    "unread_whatsapp_messages": "Checking unread WhatsApp messages.",
    "send_email": "Sending your email.",
    "gmail_send": "Sending your email.",
    "read_emails": "Checking your emails.",
    "unread_emails": "Checking your emails.",
    "create_calendar_event": "Scheduling your event.",
    "web_search": "Searching the web.",
    "browse_url": "Opening website.",
    "browser_navigate": "Opening website.",
    "volume_set": "Setting volume.",
    "volume_mute": "Muting audio.",
    "volume_unmute": "Unmuting audio.",
    "take_screenshot": "Taking a screenshot.",
    "lock_screen": "Locking screen.",
    "empty_recycle_bin": "Emptying recycle bin.",
    "system_info": "Checking system status.",
    "workspace": "Setting up workspace.",
    "briefing": "Getting your briefing.",
    "dictation": "Listening.",
    "ollama_chat": "Looking into that.",
    "ask_question": "Checking on that.",
}


class EventToSpeechMapper:
    """Zero-LLM deterministic event-to-speech converter.
    Translates verified execution states into concise, truthful spoken feedback.
    """

    @classmethod
    def format_event(cls, event_name: str, payload: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Translates an internal event to a truthful natural speech string."""
        template = EVENT_SPEECH_TEMPLATES.get(event_name)
        if not template:
            return None
        safe_payload = payload or {}
        try:
            return template.format(**safe_payload)
        except (KeyError, IndexError):
            # Fallback to general template without format fields
            if "{name}" in template:
                return "Opening it."
            return template

    @classmethod
    def get_contextual_ack(cls, intent: str, slots: Optional[Dict[str, Any]] = None) -> str:
        """Returns the appropriate contextual micro-ACK for an action category."""
        safe_slots = slots or {}
        intent_lower = intent.lower()

        # Dynamic app name for open_app / close_app / switch_app
        if intent_lower in ("open_app", "launch_app"):
            app_name = safe_slots.get("name") or safe_slots.get("app")
            if app_name:
                return f"Opening {str(app_name).strip().capitalize()}."
            return "Opening it."

        if intent_lower == "close_app":
            app_name = safe_slots.get("name") or safe_slots.get("app")
            if app_name:
                return f"Closing {str(app_name).strip().capitalize()}."
            return "Closing it."

        if intent_lower == "switch_app":
            app_name = safe_slots.get("name") or safe_slots.get("app")
            if app_name:
                return f"Switching to {str(app_name).strip().capitalize()}."
            return "Switching to it."

        # Messaging & Communication
        if intent_lower in ("read_whatsapp_messages", "read_whatsapp", "unread_whatsapp_messages"):
            return "Checking your WhatsApp messages."

        if intent_lower in ("summarize_whatsapp_messages", "summarize_whatsapp"):
            return "Summarizing your WhatsApp messages."

        if intent_lower in ("send_whatsapp_message", "send_whatsapp"):
            recipient = safe_slots.get("recipient")
            if recipient:
                return f"Sending message to {str(recipient).strip().capitalize()}."
            return "Sending WhatsApp message."

        if intent_lower in ("send_email", "gmail_send"):
            recipient = safe_slots.get("to") or safe_slots.get("recipient")
            if recipient:
                return f"Sending email to {str(recipient).strip()}."
            return "Sending your email."

        if intent_lower in ("read_emails", "unread_emails"):
            return "Checking your emails."

        # Web & Search
        if intent_lower in ("web_search", "google_search"):
            query = safe_slots.get("query")
            if query and len(str(query)) < 30:
                return f"Searching for {str(query).strip()}."
            return "Searching the web."

        if intent_lower in ("browse_url", "browser_navigate"):
            return "Opening website."

        # System & Volume
        if intent_lower == "volume_set":
            pct = safe_slots.get("percent")
            if pct is not None:
                return f"Setting volume to {pct} percent."
            return "Setting volume."

        if intent_lower == "volume_mute":
            return "Muting audio."

        if intent_lower == "volume_unmute":
            return "Unmuting audio."

        if intent_lower in ("find_file",):
            name = safe_slots.get("name") or safe_slots.get("query")
            if name:
                return f"Looking for {str(name).strip()}."
            return "Looking."

        if intent_lower in ("open_file",):
            name = safe_slots.get("name") or safe_slots.get("path")
            if name:
                return f"Opening {str(name).strip()}."
            return "Opening the file."

        if intent_lower in ("search_notes", "search_documents"):
            return "Searching your notes."

        if intent_lower in ("create_note", "quick_notes"):
            return "Taking note."

        if intent_lower in ("meeting_notes",):
            return "Recording meeting notes."

        if intent_lower == "take_screenshot":
            return "Taking a screenshot."

        if intent_lower in ("lock_screen",):
            return "Locking screen."

        if intent_lower in ("empty_recycle_bin",):
            return "Emptying recycle bin."

        if intent_lower in ("git_status",):
            return "Checking Git status."

        if intent_lower in ("git_commit",):
            return "Committing changes."

        if intent_lower in ("run_project_tests",):
            return "Running tests."

        if intent_lower in ("planner", "dag_scheduler"):
            return "I'll plan and handle that."

        if intent_lower in ("ollama_chat", "ask_question", "general_question"):
            return "Looking into that."

        return INTENT_MICRO_ACKS.get(intent_lower, "On it.")
