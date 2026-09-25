# JDE route matrix

The JARVIS Decision Engine (JDE) chooses a **route family**, never a tool. The table below is generated from the live
capability registry by `jarvis.decision.catalog.RouteCatalog` (catalog `cat-04368ff93d`). The family's risk class is the
highest risk of any tool in it, and it selects the confidence gate (see `docs/JDE_TRAINING_AND_CALIBRATION.md`).

The planner/agent only ever sees the tools of the families JDE shortlists (top-k with cumulative coverage),
never the whole registry. JDE cannot invent a tool: a family maps only to tools that already exist in the registry.

| Family | Risk class (gate) | Tools the family may shortlist |
|---|---|---|
| APP | REVERSIBLE | `close_app`, `open_app` |
| SYSTEM | DESTRUCTIVE (power control) | `brightness_get`, `brightness_set`, `clipboard_intelligence`, `connected_devices`, `get_time`, `microphone_status`, `notification_send`, `open_system_settings`, `set_voice`, `show_dashboard`, `speech_recognition_status`, `system_diagnostics`, `system_info`, `system_power_control`, `take_screenshot`, `top_memory_processes`, `volume_get`, `volume_set`, `wake_word_status` |
| FILE | REVERSIBLE (delete goes to the trash) | `batch_rename`, `copy_file`, `create_folder`, `delete_file`, `extract_audio`, `find_duplicates`, `find_file`, `list_directory`, `move_file`, `open_file`, `open_known_folder`, `organize_downloads`, `read_file_metadata`, `rename_file`, `trim_media_clip` |
| RAG | REVERSIBLE | `document_qa`, `generate_meeting_notes`, `knowledge_ingest`, `knowledge_search`, `memos_recent`, `search_notes` |
| KNOWLEDGE | READ_ONLY | `ollama_chat` (grounded chat) |
| WEB | READ_ONLY | `rss_latest`, `search_news`, `search_web` |
| BROWSER | REVERSIBLE | `browser_click`, `browser_navigate`, `browser_open_url`, `browser_snapshot`, `browser_type`, `open_website`, `play_youtube`, `web_task` |
| DESKTOP | REVERSIBLE | `arrange_windows`, `close_window`, `computer_task`, `describe_screen`, `desktop_ui_click`, `desktop_ui_snapshot`, `dialog_interaction`, `dictate_text`, `keyboard_shortcut`, `maximize_window`, `minimize_window`, `move_resize_window`, `screen_click`, `show_desktop`, `snap_window`, `switch_window` |
| MEDIA | REVERSIBLE | `media_control` |
| PHONE | REVERSIBLE | `android_*` control tools (back, home, dial, input, key, notifications, open app/url, screenshot, status, tap text, toggle, scrcpy open/close) |
| TRANSFER | REVERSIBLE | `android_pull_file`, `android_push_file`, `localsend_file`, `localsend_text` |
| WHATSAPP | EXTERNAL_EFFECT | `read_whatsapp_messages`, `reply_whatsapp_all`, `reply_whatsapp_message`, `send_whatsapp_message`, `summarize_whatsapp_messages`, `whatsapp_action` |
| GOOGLE | EXTERNAL_EFFECT | `calendar_create_event`, `calendar_list_events`, `gmail_create_draft`, `gmail_list_recent` |
| REMINDER | REVERSIBLE | `capture_note`, `list_reminders`, `memos_create`, `set_reminder` |
| PACKAGE | DESTRUCTIVE (uninstall) | `check_app_installed`, `get_app_location`, `install_software`, `list_installed_applications`, `refresh_applications`, `uninstall_software`, `update_software` |
| DEVELOPMENT | REVERSIBLE | `antigravity_ide_control`, `diagnose_error`, `git_status`, `powershell_command`, `run_project_tests` |
| WORKFLOW | REVERSIBLE | `dictation_mode_control`, `launch_workspace`, `morning_briefing`, `personal_briefing`, `save_workspace`, `start_study_focus`, `voice_edit`, `wake_greeting` |
| PLANNER | READ_ONLY (the plan's steps are gated one by one) | the union of the other shortlisted families |
| CLARIFY | READ_ONLY | none; ask the user |
| UNKNOWN | READ_ONLY | none; unsupported request |

## How the spec's families map onto these

| Spec family | JDE families |
|---|---|
| DIRECT_COMMAND | APP, SYSTEM, MEDIA, REMINDER, PACKAGE (L0 rules decide almost all of these first) |
| FILE, RAG, BROWSER, DESKTOP, PHONE, WHATSAPP, GOOGLE, DEVELOPMENT, WORKFLOW, PLANNER, CLARIFY, UNKNOWN | same name |
| KNOWLEDGE | KNOWLEDGE (no fresh data needed) and WEB (fresh or live data) |
| (not in the spec) | TRANSFER (phone ↔ PC files), split out because it is often confused with PHONE and FILE |

## Gate actions

| Gate | Meaning | What the caller does |
|---|---|---|
| EXECUTE | calibrated confidence ≥ the family's risk threshold, no incoherence or disagreement | map to the family's tools; **policy and confirmation still decide** |
| FALLBACK | not confident enough, or not an action request | the existing router / LLM path handles the request exactly as before |
| CLARIFY | ambiguous, a missing referent, heads that contradict each other, or a high-risk disagreement between the classifier and the semantic router | ask the user |
| ABSTAIN | confidence below `fallback_min` | the existing router handles the request |
| UNSUPPORTED | UNKNOWN route or low `supported` probability | say it is not supported |

A gate is advice about routing only. It is **never** authorization: `PolicyEvaluator`, `ConfirmationManager`, the
ledger and the verifier are unchanged and remain the final authority for every tool call.
