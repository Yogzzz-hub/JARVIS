"""Capability Context and RAG Knowledge Builder for Ollama and JARVIS Routing.

Provides connected integrations knowledge, dynamic semantic capability retrieval (RAG),
and prompt engineering so local LLMs and routers understand what integrations and tools
are connected (WhatsApp, Google automations, Android phone, desktop apps, system tools).
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

logger = logging.getLogger("jarvis.core.capabilities.context")

# Canonical summary of all connected integrations and system capabilities
CONNECTED_INTEGRATIONS_SUMMARY = """
### CONNECTED INTEGRATIONS & CAPABILITIES:

1. **WHATSAPP (Omnichannel Messaging)**:
   - Tool: `send_whatsapp_message` (required slots: `recipient`, `message`)
     - Purpose: Send WhatsApp message to any contact name or phone number.
     - Examples: "say hi to yoga in whatsapp", "send hello to Mom on whatsapp", "tell Rahul meeting at 5", "text Priya on whatsapp".
   - Tool: `read_whatsapp_messages` (slots: `limit`, `unread_only`)
     - Purpose: Read recent or unread incoming WhatsApp chats from the bridge.
   - Tool: `summarize_whatsapp_messages`
     - Purpose: Summarize pending WhatsApp messages and highlight urgent items.
   - Tool: `whatsapp_action` (slots: `action`: "pair", "connect", "disconnect")
     - Purpose: Manage Baileys bridge connection and show pairing QR code.

2. **GOOGLE AUTOMATIONS & SERVICES**:
   - Tool: `gmail_create_draft` / `gmail_send` (slots: `to`, `subject`, `body`)
     - Purpose: Compose and send emails via connected Gmail account.
     - Examples: "send email to boss@company.com", "draft email to team", "compose mail".
   - Tool: `gmail_list_recent` / `read_emails` (slots: `limit`)
     - Purpose: Check and read recent or unread emails from Gmail inbox.
   - Tool: `calendar_create_event` (slots: `title`, `start_time`, `end_time`)
     - Purpose: Create Google Calendar appointments and schedule meetings.
   - Tool: `calendar_list_events` (slots: `days`)
     - Purpose: List upcoming Google Calendar events and today's schedule.

3. **ANDROID PHONE & MOBILE CONNECTORS**:
   - Tool: `android_status`
     - Purpose: Check Android phone connection, USB/ADB status, WhatsApp phone link, and battery.
     - Examples: "is my phone connected?", "check phone status", "android battery".
   - Tool: `android_open_control` (scrcpy)
     - Purpose: Mirror Android phone screen directly onto PC desktop with interactive mouse/keyboard control.
     - Examples: "mirror my phone", "show phone screen", "open phone control".
   - Tool: `android_close_control`
     - Purpose: Close the active phone screen mirror window.
   - Tool: `android_open_app` (slots: `app_name`)
     - Purpose: Launch an application on the connected Android phone (e.g. Spotify, Camera, Settings).
   - Tool: `localsend_file` (slots: `path`, `target_alias`)
     - Purpose: Send local files, photos, or documents to Android phone over Wi-Fi via LocalSend.
   - Tool: `localsend_text` (slots: `text`)
     - Purpose: Send text, URL, or clipboard content to phone via LocalSend.
   - Tool: `notification_send` (slots: `title`, `message`, `priority`)
     - Purpose: Push alert notifications to mobile phone via ntfy/Gotify.

4. **WINDOWS APPLICATIONS & DESKTOP MANAGEMENT**:
   - Tool: `open_app` (required slot: `name`)
     - Purpose: Launch any Windows desktop application or web service (e.g. "chrome", "notepad", "calculator", "spotify").
   - Tool: `close_app` (required slot: `name`)
     - Purpose: Gracefully close or terminate a running desktop application.
   - Tool: `list_installed_applications`
     - Purpose: List all installed Windows applications, Start Menu apps, and software.
   - Tool: `refresh_applications`
     - Purpose: Rescan and update the local application catalog.
   - Tool: `install_software` (required slot: `name`)
     - Purpose: Install applications silently via Windows Package Manager (`winget`).

5. **SYSTEM HARDWARE, VOLUME & DIAGNOSTICS**:
   - Tool: `volume_set` (required slot: `percent`) / `volume_mute` / `volume_unmute`
     - Purpose: Adjust master audio volume (0-100%) or mute/unmute speakers.
   - Tool: `system_info`
     - Purpose: Display CPU, RAM, disk, OS version, and hardware specifications.
   - Tool: `system_diagnostics`
     - Purpose: Run end-to-end subsystem audit (Ollama, Event Loop, Audio, Connectors).
   - Tool: `take_screenshot`
     - Purpose: Capture full desktop or active screen and save as PNG.
   - Tool: `wifi_status`
     - Purpose: Check current Wi-Fi network connection and signal strength.
   - Tool: `get_time`
     - Purpose: Return current local time, date, and timezone.
   - Tool: `microphone_status`
     - Purpose: Verify default recording microphone and sound input levels.

6. **FILE INTELLIGENCE & PRODUCTIVITY**:
   - Tool: `find_files` / `search_files` (slots: `query`, `extension`, `folder`)
     - Purpose: Fast indexed search across files, documents, code, and downloads.
   - Tool: `list_directory` (required slot: `path`)
     - Purpose: Open and list files inside a directory or reveal in File Explorer.
   - Tool: `organize_downloads`
     - Purpose: Group and clean up Downloads directory by file type and date.
   - Tool: `find_duplicate_files`
     - Purpose: Identify duplicate files using cryptographic hash comparisons.

7. **KNOWLEDGE, WEB & RAG NOTES**:
   - Tool: `search_web` (required slot: `query`)
     - Purpose: Search Google / DuckDuckGo for live real-time web information.
   - Tool: `document_qa` (slots: `query`, `file_path`)
     - Purpose: Query, summarize, or extract facts from indexed local documents.
   - Tool: `rss_latest` (slots: `query`, `limit`)
     - Purpose: Fetch latest headlines from FreshRSS news feeds.
   - Tool: `memos_create` (slots: `content`)
     - Purpose: Save a quick note, memo, or reminder into Memos.
   - Tool: `memos_recent`
     - Purpose: Retrieve recent notes and ideas.
   - Tool: `morning_briefing`
     - Purpose: Deliver spoken morning audio briefing covering news, weather, and schedule.
""".strip()


class CapabilityContextBuilder:
    """Builds dynamic RAG prompts containing system capabilities and connected integrations."""

    @staticmethod
    def build_connected_overview() -> str:
        """Returns static summary of all connected integrations."""
        return CONNECTED_INTEGRATIONS_SUMMARY

    @staticmethod
    def retrieve_relevant_context(
        query: str,
        retriever: Optional[Any] = None,
        top_k: int = 5,
        min_score: float = 4.0,
    ) -> str:
        """
        Dynamically retrieves top matching capabilities for the query using RAG.
        Returns a formatted markdown snippet of the most relevant tools.
        """
        if not retriever:
            return ""

        try:
            results = retriever.retrieve(query, top_k=top_k, min_score=min_score)
            if not results:
                return ""

            lines = ["### DYNAMICALLY RETRIEVED RELEVANT TOOLS (RAG):"]
            for cap, score in results:
                req_str = f" [required slots: {', '.join(cap.required_slots)}]" if cap.required_slots else ""
                lines.append(f"- **{cap.target_tool}** (id: `{cap.id}`, score: {score:.1f}){req_str}: {cap.description}")
                if cap.examples:
                    ex_snippet = '", "'.join(cap.examples[:2])
                    lines.append(f'  - Examples: "{ex_snippet}"')

            return "\n".join(lines)
        except Exception as exc:
            logger.debug("Capability retrieval error in context builder: %s", exc)
            return ""

    @staticmethod
    def build_classifier_prompt(
        query: str,
        candidates: Optional[List[Any]] = None,
        retriever: Optional[Any] = None,
    ) -> str:
        """
        Constructs the comprehensive RAG classifier prompt for Ollama.
        """
        rag_context = CapabilityContextBuilder.retrieve_relevant_context(query, retriever=retriever, top_k=5)

        candidate_lines = []
        if candidates:
            for c in candidates:
                req = f" required_slots: {list(getattr(c, 'required_slots', []))}" if getattr(c, "required_slots", None) else ""
                exs = getattr(c, "examples", [])[:2]
                candidate_lines.append(f"- {c.name}: {exs}{req}")

        candidates_block = "\n".join(candidate_lines) if candidate_lines else "None explicitly listed."

        return (
            "You are JARVIS's command classifier for Windows.\n"
            "Your job is to classify the user's utterance into the single most accurate command tool and extract all slot values.\n\n"
            f"{CONNECTED_INTEGRATIONS_SUMMARY}\n\n"
            f"{rag_context}\n\n"
            f"Candidate Intents:\n{candidates_block}\n\n"
            f'User Text: "{query}"\n\n'
            "Rules:\n"
            "1. If user text is requesting to send a message (e.g. 'say hi to yoga in whatsapp', 'tell yoga hi', 'message mom'), "
            "select intent 'send_whatsapp_message' with slots {'recipient': '<name>', 'message': '<text>'}.\n"
            "2. If user text mentions phone screen, mirroring, or scrcpy, select 'android_open_control'.\n"
            "3. If user asks if phone is connected, select 'android_status'.\n"
            "4. If user text asks to open/launch an app, select 'open_app' with slot {'name': '<app>'}.\n"
            "5. If user text is not an imperative action or tool invocation, set unknown=true.\n"
        )

    @staticmethod
    def build_chat_system_prompt() -> str:
        """Constructs system prompt for general Ollama chat tool."""
        return (
            "You are JARVIS, an advanced, concise AI assistant for Windows.\n"
            "You have direct control over the following connected integrations:\n"
            "- WhatsApp: Can send messages, read chats, and summarize messages via local Baileys bridge.\n"
            "- Google Automations: Can send/draft emails via Gmail and manage Google Calendar events.\n"
            "- Android Phone: Can mirror phone screen (scrcpy), check battery/connection status, launch phone apps, and transfer files/text via LocalSend.\n"
            "- Windows Desktop: Can open/close apps, list installed programs, install software via winget, set volume, capture screenshots, and search files.\n\n"
            "Answer the user clearly, concisely, and informatively in 1-3 sentences. When the user asks about connected features or wants to perform an action, acknowledge your connected capabilities directly."
        )
