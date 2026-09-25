# Memos — Human-Readable Notes & Inbox

## Overview
**Memos** provides a lightweight human note-taking and inbox service.

## CRITICAL: Memos vs. JARVIS Internal Working Memory
- **JARVIS Working Memory (Phase 12)**: Internal context, recent files, resolved pronouns, active execution graphs. Never dumped to Memos.
- **Memos**: Explicit user notes, reminders, and journal entries.

## Supported Commands
- "Jarvis, make a note: test streaming STT tomorrow."
- "Take a note: review pull request #42."
- "Read my recent notes."
- "Show my notes."

## Security & Privacy
- **Untrusted Input**: Memos read back into context are treated as `UNTRUSTED_DATA`. Instructions in notes are never blindly executed.
- **Secret Redaction**: Auth tokens, API keys, and passwords are automatically redacted prior to saving.
