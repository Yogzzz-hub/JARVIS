# JARVIS EDGE — REAL PRODUCTION COMMAND INVENTORY

This document enumerates every user-accessible capability from ToolRegistry, CapabilityRegistry, router grammar, AppCatalog, file tools, browser tools, UIA tools, planner capabilities, memory commands, workflows, connectors, and system controls.

**Source of Truth**: Live Gateway ToolRegistry (`71 tools`) and Router Intent Catalog (`41 intents`).

| ID | Capability | User-Facing Example | Routing Lane | Tool | Risk Class | Verifier | Dependencies | Manual Test Req | Status |
|---|---|---|---|---|---|---|---|---|---|
| C001 | `android_back` | "Go back on phone" | LANE1/2 | `android_back` | REVERSIBLE | Native / Process Verifier | ADB / scrcpy | YES | NOT_TESTED |
| C002 | `android_close_control` | "close my phone" | LANE0 | `android_close_control` | REVERSIBLE | Native / Process Verifier | ADB / scrcpy | YES | NOT_TESTED |
| C003 | `android_home` | "Press home on phone" | LANE1/2 | `android_home` | REVERSIBLE | Native / Process Verifier | ADB / scrcpy | YES | NOT_TESTED |
| C004 | `android_open_app` | "Open WhatsApp on phone" | LANE1/2 | `android_open_app` | REVERSIBLE | UIA / Process Window Verifier | AppCatalog / Win32 | YES | NOT_TESTED |
| C005 | `android_open_control` | "show my phone" | LANE0 | `android_open_control` | REVERSIBLE | Native / Process Verifier | ADB / scrcpy | YES | NOT_TESTED |
| C006 | `android_status` | "Check phone battery status" | LANE1/2 | `android_status` | READ_ONLY | Native / Process Verifier | ADB / scrcpy | YES | NOT_TESTED |
| C007 | `batch_rename` | "Batch rename files in folder" | LANE1/2 | `batch_rename` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C008 | `browser_click` | "Click the login button on the page" | LANE1/2 | `browser_click` | REVERSIBLE | Playwright DOM / Page Verifier | Playwright / Chromium | YES | NOT_TESTED |
| C009 | `browser_navigate` | "Execute browser navigate" | LANE1/2 | `browser_navigate` | REVERSIBLE | Playwright DOM / Page Verifier | Playwright / Chromium | YES | NOT_TESTED |
| C010 | `browser_open_url` | "Open example.com in browser" | LANE1/2 | `browser_open_url` | REVERSIBLE | Playwright DOM / Page Verifier | Playwright / Chromium | YES | NOT_TESTED |
| C011 | `browser_snapshot` | "Take a snapshot of current browser page" | LANE1/2 | `browser_snapshot` | READ_ONLY | Playwright DOM / Page Verifier | Playwright / Chromium | YES | NOT_TESTED |
| C012 | `browser_type` | "Type hello into search input" | LANE1/2 | `browser_type` | REVERSIBLE | Playwright DOM / Page Verifier | Playwright / Chromium | YES | NOT_TESTED |
| C013 | `capture_note` | "Capture quick note" | LANE1/2 | `capture_note` | REVERSIBLE | Memos DB / REST Verifier | None | YES | NOT_TESTED |
| C014 | `close_app` | "close chrome" | LANE0 | `close_app` | REVERSIBLE | UIA / Process Window Verifier | AppCatalog / Win32 | YES | NOT_TESTED |
| C015 | `close_window` | "close" | LANE0 | `close_window` | REVERSIBLE | UIA / Process Window Verifier | AppCatalog / Win32 | YES | NOT_TESTED |
| C016 | `copy_file` | "Copy report.pdf to DemoFolder" | LANE1/2 | `copy_file` | REVERSIBLE | Filesystem / ResourceRef Verifier | File Search Indexer | YES | NOT_TESTED |
| C017 | `create_folder` | "Create a folder called TestFolder" | LANE1/2 | `create_folder` | REVERSIBLE | Filesystem / ResourceRef Verifier | None | YES | NOT_TESTED |
| C018 | `delete_file` | "Delete disposable-test.txt" | LANE1/2 | `delete_file` | DESTRUCTIVE | Filesystem / ResourceRef Verifier | File Search Indexer | YES | NOT_TESTED |
| C019 | `desktop_ui_click` | "Click button with UIA" | LANE1/2 | `desktop_ui_click` | REVERSIBLE | UIA / Process Window Verifier | None | YES | NOT_TESTED |
| C020 | `desktop_ui_snapshot` | "Inspect active window UI tree" | LANE1/2 | `desktop_ui_snapshot` | READ_ONLY | UIA / Process Window Verifier | None | YES | NOT_TESTED |
| C021 | `diagnose_error` | "Execute diagnose error" | LANE2 | `diagnose_error` | READ_ONLY | Native / Process Verifier | None | YES | NOT_TESTED |
| C022 | `dictate_text` | "dictate hello world" | LANE0 | `dictate_text` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C023 | `document_qa` | "Ask a question about document" | LANE1/2 | `document_qa` | READ_ONLY | Native / Process Verifier | None | YES | NOT_TESTED |
| C024 | `extract_audio` | "Extract audio from video file" | LANE1/2 | `extract_audio` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C025 | `find_duplicates` | "Find duplicate files in downloads" | LANE1/2 | `find_duplicates` | READ_ONLY | Native / Process Verifier | None | YES | NOT_TESTED |
| C026 | `find_file` | "find nlp pdf" | LANE0 | `find_file` | READ_ONLY | Filesystem / ResourceRef Verifier | File Search Indexer | YES | NOT_TESTED |
| C027 | `generate_meeting_notes` | "Generate meeting notes" | LANE1/2 | `generate_meeting_notes` | REVERSIBLE | Memos DB / REST Verifier | None | YES | NOT_TESTED |
| C028 | `get_time` | "time" | LANE0 | `get_time` | READ_ONLY | System Telemetry / Response Verifier | None | YES | NOT_TESTED |
| C029 | `git_status` | "Check git status of repository" | LANE1/2 | `git_status` | READ_ONLY | Native / Process Verifier | None | YES | NOT_TESTED |
| C030 | `launch_workspace` | "Launch dev workspace" | LANE1/2 | `launch_workspace` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C031 | `list_directory` | "list desktop" | LANE0 | `list_directory` | READ_ONLY | Filesystem / ResourceRef Verifier | File Search Indexer | YES | NOT_TESTED |
| C032 | `localsend_file` | "send this file to my phone" | LANE0 | `localsend_file` | REVERSIBLE | Filesystem / ResourceRef Verifier | File Search Indexer | YES | NOT_TESTED |
| C033 | `localsend_text` | "Send text message to phone" | LANE1/2 | `localsend_text` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C034 | `maximize_window` | "max" | LANE0 | `maximize_window` | REVERSIBLE | UIA / Process Window Verifier | AppCatalog / Win32 | YES | NOT_TESTED |
| C035 | `media_control` | "play" | LANE0 | `media_control` | REVERSIBLE | Hardware Key / Audio Endpoint Verifier | None | YES | NOT_TESTED |
| C036 | `memos_create` | "make a note: test streaming STT tomorrow" | LANE0 | `memos_create` | REVERSIBLE | Memos DB / REST Verifier | Memos SQLite / REST | YES | NOT_TESTED |
| C037 | `memos_recent` | "read my notes" | LANE0 | `memos_recent` | READ_ONLY | Memos DB / REST Verifier | Memos SQLite / REST | YES | NOT_TESTED |
| C038 | `minimize_window` | "min" | LANE0 | `minimize_window` | REVERSIBLE | UIA / Process Window Verifier | AppCatalog / Win32 | YES | NOT_TESTED |
| C039 | `morning_briefing` | "good morning jarvis" | LANE0 | `morning_briefing` | READ_ONLY | Native / Process Verifier | None | YES | NOT_TESTED |
| C040 | `move_file` | "Move notes.txt to DemoFolder" | LANE1/2 | `move_file` | REVERSIBLE | Filesystem / ResourceRef Verifier | File Search Indexer | YES | NOT_TESTED |
| C041 | `notification_send` | "Send desktop notification" | LANE1/2 | `notification_send` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C042 | `ollama_chat` | "Ask general question to Ollama" | LANE1/2 | `ollama_chat` | READ_ONLY | Native / Process Verifier | Ollama Daemon (Port 11434) | YES | NOT_TESTED |
| C043 | `open_app` | "open chrome" | LANE0 | `open_app` | REVERSIBLE | UIA / Process Window Verifier | AppCatalog / Win32 | YES | NOT_TESTED |
| C044 | `open_file` | "open file notes.txt" | LANE0 | `open_file` | REVERSIBLE | Filesystem / ResourceRef Verifier | File Search Indexer | YES | NOT_TESTED |
| C045 | `organize_downloads` | "Organize files in downloads" | LANE2 | `organize_downloads` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C046 | `personal_briefing` | "Give me personal briefing" | LANE1/2 | `personal_briefing` | READ_ONLY | Native / Process Verifier | None | YES | NOT_TESTED |
| C047 | `play_youtube` | "open youtube and play believer" | LANE0 | `play_youtube` | REVERSIBLE | Native / Process Verifier | Web Browser / YouTube | YES | NOT_TESTED |
| C048 | `powershell_command` | "Run powershell command" | LANE2 | `powershell_command` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C049 | `read_file_metadata` | "Read metadata for report.pdf" | LANE1/2 | `read_file_metadata` | READ_ONLY | Filesystem / ResourceRef Verifier | File Search Indexer | YES | NOT_TESTED |
| C050 | `read_whatsapp_messages` | "read my whatsapp messages" | LANE0 | `read_whatsapp_messages` | READ_ONLY | UIA / Process Window Verifier | AppCatalog / Win32 | YES | NOT_TESTED |
| C051 | `rename_file` | "Rename alpha.txt to beta.txt" | LANE1/2 | `rename_file` | REVERSIBLE | Filesystem / ResourceRef Verifier | File Search Indexer | YES | NOT_TESTED |
| C052 | `rss_latest` | "what's new in AI?" | LANE0 | `rss_latest` | READ_ONLY | Native / Process Verifier | None | YES | NOT_TESTED |
| C053 | `run_project_tests` | "Run test suite for project" | LANE1/2 | `run_project_tests` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C054 | `save_workspace` | "Save current workspace" | LANE1/2 | `save_workspace` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C055 | `search_news` | "search news in india" | LANE0 | `search_news` | REVERSIBLE | Native / Process Verifier | Google News RSS / Network | YES | NOT_TESTED |
| C056 | `search_notes` | "Search notes for python" | LANE1/2 | `search_notes` | READ_ONLY | Memos DB / REST Verifier | None | YES | NOT_TESTED |
| C057 | `search_web` | "search web for latest AI models" | LANE0 | `search_web` | READ_ONLY | Native / Process Verifier | None | YES | NOT_TESTED |
| C058 | `send_whatsapp_message` | "send whatsapp message to Mom: I will be home soon" | LANE0 | `send_whatsapp_message` | EXTERNAL_EFFECT | UIA / Process Window Verifier | AppCatalog / Win32 | YES | NOT_TESTED |
| C059 | `set_voice` | "change your voice to female" | LANE0 | `set_voice` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C060 | `show_dashboard` | "open dashboard" | LANE0 | `show_dashboard` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C061 | `show_desktop` | "desktop" | LANE0 | `show_desktop` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C062 | `start_study_focus` | "Start study focus session" | LANE1/2 | `start_study_focus` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C063 | `summarize_whatsapp_messages` | "summarize my whatsapp messages" | LANE0 | `summarize_whatsapp_messages` | READ_ONLY | UIA / Process Window Verifier | AppCatalog / Win32 | YES | NOT_TESTED |
| C064 | `system_diagnostics` | "Run system diagnostics" | LANE1/2 | `system_diagnostics` | READ_ONLY | Native / Process Verifier | None | YES | NOT_TESTED |
| C065 | `system_info` | "system info" | LANE0 | `system_info` | READ_ONLY | System Telemetry / Response Verifier | None | YES | NOT_TESTED |
| C066 | `take_screenshot` | "screenshot" | LANE0 | `take_screenshot` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C067 | `trim_media_clip` | "Trim video clip" | LANE1/2 | `trim_media_clip` | REVERSIBLE | Hardware Key / Audio Endpoint Verifier | None | YES | NOT_TESTED |
| C068 | `volume_get` | "volume" | LANE0 | `volume_get` | READ_ONLY | Hardware Key / Audio Endpoint Verifier | None | YES | NOT_TESTED |
| C069 | `volume_set` | "volume 30" | LANE0 | `volume_set` | REVERSIBLE | Hardware Key / Audio Endpoint Verifier | None | YES | NOT_TESTED |
| C070 | `wake_greeting` | "hello" | LANE0 | `wake_greeting` | REVERSIBLE | Native / Process Verifier | None | YES | NOT_TESTED |
| C071 | `whatsapp_action` | "Connect WhatsApp" | LANE1/2 | `whatsapp_action` | REVERSIBLE | UIA / Process Window Verifier | AppCatalog / Win32 | YES | NOT_TESTED |